"""Tests for the demo UI: activity events and an end-to-end Streamlit run with a fake model."""

import queue

from langchain_core.messages import AIMessage
from streamlit.testing.v1 import AppTest

from finance_research_agent.agent import create_main_agent
from ui.activity import ActivityHandler
from ui.questions import SAMPLE_QUESTIONS

from .conftest import report_call, scripted_model, task_call


def scripted_research_run():
    todos = AIMessage(content="", tool_calls=[{
        "name": "write_todos",
        "args": {"todos": [{"content": "Collect AAPL data", "status": "in_progress"}]},
        "id": "todo-1",
    }])
    sub_tool = AIMessage(content="", tool_calls=[{"name": "get_stock_metrics", "args": {"ticker": "ZZZZ"}, "id": "t1"}])
    return scripted_model([
        todos,
        task_call("data_collector", "Get AAPL data", "call-1"),
        sub_tool,
        AIMessage(content="P/E 30x"),
        report_call(),
    ])


async def test_activity_handler_reports_plan_delegation_and_tools(config, use_model):
    use_model(scripted_research_run())
    events = queue.Queue()
    await create_main_agent(config).ainvoke(
        {"messages": [{"role": "user", "content": "Research AAPL"}]},
        config={"callbacks": [ActivityHandler(events)]},
    )
    seen = [events.get() for _ in range(events.qsize())]

    assert seen[0] == {"type": "todos", "agent": "finance-research-agent",
                       "todos": [{"content": "Collect AAPL data", "status": "in_progress"}]}
    assert seen[1]["type"] == "subagent_start" and seen[1]["subagent"] == "data_collector"
    assert seen[2] == {"type": "tool", "agent": "data_collector", "tool": "get_stock_metrics",
                       "args": '{"ticker": "ZZZZ"}'}
    assert seen[3] == {"type": "subagent_end", "subagent": "data_collector", "ok": True}


def test_sample_questions_are_well_formed():
    for group in SAMPLE_QUESTIONS.values():
        for q in group:
            assert q["label"] and q["question"] and q["shows"]


def test_app_runs_sample_question_end_to_end(monkeypatch, use_model):
    monkeypatch.setenv("SNOWFLAKE_MCP_URL", "")
    monkeypatch.setenv("SNOWFLAKE_PAT", "")
    use_model(scripted_research_run())

    app = AppTest.from_file("../ui/app.py", default_timeout=60).run()
    assert not app.exception
    assert app.title[0].value == "Financial Research Agent"
    assert "not configured" in app.sidebar.caption[0].value

    next(b for b in app.sidebar.button if b.label == "Apple valuation snapshot").click().run()

    assert not app.exception
    assert any("Apple remains highly profitable" in m.value for m in app.markdown)
    assert {b.label for b in app.get("download_button")} >= {"⬇ Markdown", "⬇ Excel", "⬇ PDF", "⬇ JSON"}
    assert [m.label for m in app.metric][:3] == ["Time", "Tokens", "Tool calls"]
