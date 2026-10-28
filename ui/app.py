"""Streamlit demo UI for the financial research agent.

Run from the repo root:
    streamlit run ui/app.py
"""

import asyncio
import os
import queue
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from finance_research_agent.config import AgentConfig, OutputConfig  # noqa: E402
from finance_research_agent.orchestrator import DeepResearchOrchestrator  # noqa: E402
from finance_research_agent.output import save_report  # noqa: E402
from finance_research_agent.schemas import report_to_output_dict  # noqa: E402
from ui.activity import ActivityHandler  # noqa: E402
from ui.questions import SAMPLE_QUESTIONS  # noqa: E402

TODO_ICONS = {"completed": "✅", "in_progress": "🔄", "pending": "⬜"}
DOWNLOADS = {
    "markdown": ("Markdown", "text/markdown"),
    "excel": ("Excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    "pdf": ("PDF", "application/pdf"),
    "json": ("JSON", "application/json"),
}
MAX_FEED_LINES = 14

st.set_page_config(page_title="Financial Research Agent", page_icon="📊", layout="wide")


def render_sidebar(config: AgentConfig) -> None:
    """Configuration status and clickable sample questions."""
    with st.sidebar:
        st.header("📊 Research Agent")
        tracing = os.getenv("LANGSMITH_TRACING", "").lower() == "true"
        st.caption(
            f"**Model:** `{config.model.provider}:{config.model.model}`  \n"
            f"**Internal data (Snowflake):** {'connected' if config.snowflake.enabled else 'not configured'}  \n"
            f"**LangSmith tracing:** {'on · ' + os.getenv('LANGSMITH_PROJECT', 'default') if tracing else 'off'}  \n"
            f"**Budget:** {config.budget.max_tokens:,} tokens · {config.budget.max_time_minutes} min"
        )
        st.divider()
        st.subheader("Sample questions")
        for group, questions in SAMPLE_QUESTIONS.items():
            if group.startswith("Internal") and not config.snowflake.enabled:
                continue
            with st.expander(group, expanded=group.startswith("Quick")):
                for i, q in enumerate(questions):
                    if q.get("requires_snowflake") and not config.snowflake.enabled:
                        continue
                    if st.button(q["label"], key=f"{group}-{i}", help=q["shows"], use_container_width=True):
                        st.session_state.pending_question = q["question"]


def start_research(question: str, events: "queue.Queue[Dict[str, Any]]") -> Dict[str, Any]:
    """Run the agent in a background thread; the returned dict fills in when done."""
    holder: Dict[str, Any] = {}

    def worker() -> None:
        try:
            orchestrator = DeepResearchOrchestrator(AgentConfig.from_env())
            holder["result"] = asyncio.run(
                orchestrator.aexecute_research(question, extra_callbacks=[ActivityHandler(events)])
            )
        except Exception as e:
            holder["error"] = f"{type(e).__name__}: {e}"

    holder["thread"] = threading.Thread(target=worker, daemon=True)
    holder["thread"].start()
    return holder


def render_plan(todos: List[Dict[str, str]]) -> str:
    if not todos:
        return "_Planning…_"
    return "\n".join(f"{TODO_ICONS.get(t['status'], '⬜')} {t['content']}" for t in todos)


def render_subagents(subagents: Dict[str, Dict[str, Any]]) -> str:
    if not subagents:
        return "_No delegations yet_"
    lines = []
    for name, info in subagents.items():
        icon = "🔄" if info["running"] else ("✅" if info["ok"] else "⚠️")
        lines.append(f"{icon} **{name}** · {info['tool_calls']} tool calls")
    return "\n\n".join(lines)


def run_with_live_progress(question: str) -> Dict[str, Any]:
    """Run research while showing the plan, delegations, and tool calls as they happen."""
    events: "queue.Queue[Dict[str, Any]]" = queue.Queue()
    holder = start_research(question, events)
    start = time.monotonic()

    todos: List[Dict[str, str]] = []
    subagents: Dict[str, Dict[str, Any]] = {}
    feed: List[str] = []
    tool_calls = 0

    with st.status("Researching…", expanded=True) as status:
        plan_col, agents_col = st.columns(2)
        with plan_col:
            st.markdown("**Plan**")
            plan_box = st.empty()
        with agents_col:
            st.markdown("**Subagents**")
            agents_box = st.empty()
        st.markdown("**Activity**")
        feed_box = st.empty()

        while holder["thread"].is_alive() or not events.empty():
            while not events.empty():
                event = events.get()
                if event["type"] == "todos" and event["agent"] == "finance-research-agent":
                    todos = event["todos"]
                elif event["type"] == "subagent_start":
                    info = subagents.setdefault(event["subagent"], {"tool_calls": 0})
                    info.update(running=True, ok=True)
                    feed.append(f"→ delegated to {event['subagent']}: {event['description']}")
                elif event["type"] == "subagent_end":
                    subagents[event["subagent"]].update(running=False, ok=event["ok"])
                    feed.append(f"← {event['subagent']} finished")
                elif event["type"] == "tool":
                    tool_calls += 1
                    if event["agent"] in subagents:
                        subagents[event["agent"]]["tool_calls"] += 1
                    feed.append(f"  {event['agent']} · {event['tool']} {event['args']}")
            plan_box.markdown(render_plan(todos))
            agents_box.markdown(render_subagents(subagents))
            feed_box.text("\n".join(feed[-MAX_FEED_LINES:]) or "Starting…")
            status.update(label=f"Researching… {time.monotonic() - start:.0f}s · {tool_calls} tool calls")
            time.sleep(0.4)

        result = holder.get("result")
        ok = result is not None and result["status"] == "completed"
        status.update(
            label=f"{'Research complete' if ok else 'Research incomplete'} in {time.monotonic() - start:.0f}s",
            state="complete" if ok else "error",
            expanded=False,
        )

    return {
        "question": question,
        "result": result,
        "error": holder.get("error"),
        "subagents": list(subagents),
        "tool_calls": tool_calls,
    }


def trace_url(run_id: Optional[str]) -> Optional[str]:
    """Best-effort LangSmith link for a run (traces can take a few seconds to ingest)."""
    if not run_id or os.getenv("LANGSMITH_TRACING", "").lower() != "true":
        return None
    try:
        from langsmith import Client

        client = Client()
        for _ in range(5):
            try:
                return client.get_run_url(run=client.read_run(run_id))
            except Exception:
                time.sleep(1.5)
    except Exception:
        pass
    return None


def build_record(run: Dict[str, Any]) -> Dict[str, Any]:
    """Render report files once so reruns don't regenerate them."""
    result = run["result"]
    structured = result["state"]["structured_response"] if result else None
    record = {**run, "report_md": None, "files": {}, "trace_url": None}
    if result:
        record["trace_url"] = trace_url(result.get("run_id"))
        record["summary"] = result["execution_summary"]
    if structured:
        with tempfile.TemporaryDirectory() as tmp:
            saved = save_report(
                report_to_output_dict(structured), structured.ticker, list(DOWNLOADS),
                OutputConfig(output_dir=tmp),
            )
            for fmt, path in saved["formats"].items():
                if isinstance(path, str):
                    record["files"][fmt] = (Path(path).name, Path(path).read_bytes())
        if "markdown" in record["files"]:
            record["report_md"] = record["files"]["markdown"][1].decode("utf-8")
    return record


def render_record(record: Dict[str, Any], index: int) -> None:
    with st.chat_message("user"):
        st.markdown(record["question"])
    with st.chat_message("assistant", avatar="📊"):
        if record["error"]:
            st.error(f"Run failed: {record['error']}")
            return
        summary = record.get("summary", {})
        cols = st.columns(4)
        cols[0].metric("Time", f"{summary.get('time_elapsed', 0):.0f}s")
        cols[1].metric("Tokens", f"{summary.get('tokens_used', 0):,}")
        cols[2].metric("Tool calls", record["tool_calls"])
        cols[3].metric("Subagents", len(record["subagents"]))
        if record["subagents"]:
            st.caption("Delegated to: " + ", ".join(record["subagents"]))
        for error in summary.get("errors", []):
            st.warning(error)

        if record["report_md"]:
            download_cols = st.columns(len(record["files"]) + 1)
            for col, (fmt, (filename, data)) in zip(download_cols, record["files"].items()):
                label, mime = DOWNLOADS[fmt]
                col.download_button(f"⬇ {label}", data, file_name=filename, mime=mime, key=f"dl-{index}-{fmt}")
            if record["trace_url"]:
                download_cols[-1].link_button("🔍 LangSmith trace", record["trace_url"])
            with st.container(border=True):
                st.markdown(record["report_md"])
        else:
            st.info("No report was produced. See the warnings above or the LangSmith trace.")
            if record["trace_url"]:
                st.link_button("🔍 LangSmith trace", record["trace_url"])


def main() -> None:
    config = AgentConfig.from_env()
    render_sidebar(config)
    st.session_state.setdefault("runs", [])

    st.title("Financial Research Agent")
    st.caption(
        "A Deep Agent that plans research, delegates to specialist subagents (market data, "
        "SEC filings, analysis, internal Snowflake data), and returns a cited report. "
        "Quick questions take under a minute; a full report takes 3-5 minutes."
    )

    for i, record in enumerate(st.session_state.runs):
        render_record(record, i)

    question = st.chat_input("Ask a research question, e.g. “Compare JPM and BAC on profitability”")
    question = question or st.session_state.pop("pending_question", None)
    if question:
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant", avatar="📊"):
            run = run_with_live_progress(question)
            with st.spinner("Rendering report…"):
                record = build_record(run)
        st.session_state.runs.append(record)
        st.rerun()


main()
