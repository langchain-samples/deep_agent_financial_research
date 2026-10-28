"""Evaluators for the financial research agent.

Target outputs (see run_evals.target) have the shape:
    {"report": dict | None, "subagents_used": [str], "context": str, "errors": [str]}
"""

import os
from typing import Any, Callable, Dict

from openevals.llm import create_async_llm_as_judge
from openevals.prompts import HALLUCINATION_PROMPT

from finance_research_agent.config import ModelConfig
from finance_research_agent.models import build_model

REQUIRED_REPORT_FIELDS = (
    "executive_summary",
    "key_metrics",
    "financial_analysis",
    "risks",
    "news_sentiment",
    "sources",
)


def report_produced(outputs: Dict[str, Any]) -> Dict[str, Any]:
    """1 if the agent returned a structured report, else 0."""
    errors = outputs.get("errors") or []
    return {
        "key": "report_produced",
        "score": int(outputs.get("report") is not None),
        "comment": "; ".join(errors) or None,
    }


def report_completeness(outputs: Dict[str, Any], reference_outputs: Dict[str, Any]) -> Dict[str, Any]:
    """Fraction of required report sections that are populated.

    For examples that expect missing data, a report that flags limitations is complete
    even when metric sections are empty.
    """
    report = outputs.get("report")
    if not report:
        return {"key": "report_completeness", "score": 0.0}
    if reference_outputs.get("expect_limitations") and report.get("limitations"):
        return {"key": "report_completeness", "score": 1.0}
    missing = [f for f in REQUIRED_REPORT_FIELDS if not report.get(f)]
    min_risks = reference_outputs.get("min_risks", 0)
    if len(report.get("risks") or []) < min_risks:
        missing.append(f"risks (<{min_risks})")
    score = 1 - len(missing) / (len(REQUIRED_REPORT_FIELDS) + bool(min_risks))
    return {
        "key": "report_completeness",
        "score": round(score, 3),
        "comment": f"Missing: {', '.join(missing)}" if missing else None,
    }


def delegated_to_expected_subagents(
    outputs: Dict[str, Any], reference_outputs: Dict[str, Any]
) -> Dict[str, Any]:
    """1 if every expected subagent was called via the task tool."""
    used = set(outputs.get("subagents_used") or [])
    missing = sorted(set(reference_outputs.get("expected_subagents", [])) - used)
    return {
        "key": "delegated_to_expected_subagents",
        "score": int(not missing),
        "comment": (
            f"Missing: {', '.join(missing)}; used: {', '.join(sorted(used)) or 'none'}"
            if missing
            else None
        ),
    }


def mentions_required_entities(
    outputs: Dict[str, Any], reference_outputs: Dict[str, Any]
) -> Dict[str, Any]:
    """1 if the report mentions at least one alias of every required entity."""
    report = outputs.get("report")
    if not report:
        return {"key": "mentions_required_entities", "score": 0}
    text = str(report).lower()
    missing = [
        aliases[0]
        for aliases in reference_outputs.get("must_mention", [])
        if not any(alias.lower() in text for alias in aliases)
    ]
    return {
        "key": "mentions_required_entities",
        "score": int(not missing),
        "comment": f"Missing: {', '.join(missing)}" if missing else None,
    }


def metrics_cite_sources(outputs: Dict[str, Any]) -> Dict[str, Any]:
    """Fraction of key metrics that name a source (vacuously 1 with no metrics)."""
    report = outputs.get("report")
    if not report:
        return {"key": "metrics_cite_sources", "score": 0.0}
    metrics = report.get("key_metrics") or []
    if not metrics:
        return {"key": "metrics_cite_sources", "score": 1.0}
    cited = sum(1 for m in metrics if (m.get("source") or "").strip())
    return {"key": "metrics_cite_sources", "score": round(cited / len(metrics), 3)}


def handles_missing_data(outputs: Dict[str, Any], reference_outputs: Dict[str, Any]) -> Dict[str, Any]:
    """For examples expecting missing data: 1 if limitations are flagged and no metrics invented.

    For examples expecting internal data: 1 if internal_data_findings is populated.
    Returns None (skipped) for other examples.
    """
    report = outputs.get("report") or {}
    if reference_outputs.get("expect_limitations"):
        ok = bool(report.get("limitations")) and not report.get("key_metrics")
        return {"key": "handles_missing_data", "score": int(ok)}
    if reference_outputs.get("expect_internal_data"):
        return {"key": "handles_missing_data", "score": int(bool(report.get("internal_data_findings")))}
    return {"key": "handles_missing_data", "score": None}


def make_groundedness_judge() -> Callable:
    """LLM-as-judge: is the report supported by what the subagents actually returned?

    Uses EVAL_JUDGE_MODEL (e.g. "openai:gpt-4o") if set, else the agent's model.
    """
    judge_model = os.getenv("EVAL_JUDGE_MODEL")
    if judge_model:
        provider, _, model = judge_model.partition(":")
        judge = build_model(ModelConfig(provider=provider, model=model))
    else:
        judge = build_model(ModelConfig.from_env())

    judge_fn = create_async_llm_as_judge(
        prompt=HALLUCINATION_PROMPT,
        feedback_key="groundedness",
        judge=judge,
    )

    async def groundedness(inputs: Dict[str, Any], outputs: Dict[str, Any]) -> Dict[str, Any]:
        if not outputs.get("report"):
            return {"key": "groundedness", "score": None, "comment": "No report produced"}
        return await judge_fn(
            inputs=inputs["query"],
            outputs=outputs["report"],
            context=outputs.get("context") or "(no tool output)",
            reference_outputs="",
        )

    return groundedness


CODE_EVALUATORS = [
    report_produced,
    report_completeness,
    delegated_to_expected_subagents,
    mentions_required_entities,
    metrics_cite_sources,
    handles_missing_data,
]
