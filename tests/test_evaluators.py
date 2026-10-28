"""Tests for the code-based eval evaluators."""

from evals.evaluators import (
    delegated_to_expected_subagents,
    handles_missing_data,
    mentions_required_entities,
    metrics_cite_sources,
    report_completeness,
)

REPORT = {
    "ticker": "AAPL",
    "company_name": "Apple Inc.",
    "executive_summary": "Summary",
    "key_metrics": [{"name": "P/E", "value": "30x", "source": "Yahoo Finance"}],
    "financial_analysis": "Analysis",
    "risks": ["a", "b"],
    "news_sentiment": "Neutral",
    "sources": ["Yahoo Finance"],
    "limitations": [],
}


def test_report_completeness_full_and_min_risks():
    assert report_completeness({"report": REPORT}, {})["score"] == 1.0
    assert report_completeness({"report": REPORT}, {"min_risks": 3})["score"] < 1.0
    assert report_completeness({"report": None}, {})["score"] == 0.0


def test_delegation():
    ref = {"expected_subagents": ["data_collector", "analyst"]}
    assert delegated_to_expected_subagents({"subagents_used": ["analyst", "data_collector"]}, ref)["score"] == 1
    assert delegated_to_expected_subagents({"subagents_used": ["data_collector"]}, ref)["score"] == 0


def test_mentions_aliases():
    ref = {"must_mention": [["AAPL", "Apple"], ["GOOGL", "Alphabet"]]}
    assert mentions_required_entities({"report": REPORT}, ref)["score"] == 0
    assert mentions_required_entities({"report": {**REPORT, "risks": ["Alphabet competition"]}}, ref)["score"] == 1


def test_metrics_cite_sources():
    uncited = {**REPORT, "key_metrics": [{"name": "P/E", "value": "30x", "source": ""}]}
    assert metrics_cite_sources({"report": REPORT})["score"] == 1.0
    assert metrics_cite_sources({"report": uncited})["score"] == 0.0


def test_handles_missing_data():
    ref = {"expect_limitations": True}
    flagged = {**REPORT, "key_metrics": [], "limitations": ["Ticker not found"]}
    assert handles_missing_data({"report": flagged}, ref)["score"] == 1
    assert handles_missing_data({"report": REPORT}, ref)["score"] == 0
    assert handles_missing_data({"report": REPORT}, {})["score"] is None
