"""Tests that reports render to files in every format."""

from finance_research_agent.config import OutputConfig
from finance_research_agent.output import save_report
from finance_research_agent.schemas import Metric, ResearchReport, report_to_output_dict


def test_save_report_writes_all_formats(tmp_path):
    report = report_to_output_dict(ResearchReport(
        ticker="AAPL", company_name="Apple Inc.", executive_summary="Strong margins.",
        key_metrics=[Metric(name="P/E", value="30x", source="Yahoo Finance")],
        financial_analysis="Stable.", risks=["China"], news_sentiment="Neutral",
        sources=["Yahoo Finance"],
    ))
    saved = save_report(report, "AAPL", ["markdown", "json", "excel", "pdf"], OutputConfig(output_dir=str(tmp_path)))

    for fmt, path in saved["formats"].items():
        assert isinstance(path, str), f"{fmt}: {path}"
    assert set(saved["formats"]) == {"markdown", "json", "excel", "pdf"}
    markdown = open(saved["formats"]["markdown"]).read()
    assert "Strong margins." in markdown
    assert "- China" in markdown and "['China']" not in markdown
    assert "**P/E:**" in markdown


def test_quick_answer_omits_empty_sections(tmp_path):
    report = report_to_output_dict(ResearchReport(
        ticker="AAPL", company_name="Apple Inc.", executive_summary="P/E is 39.6x.",
        key_metrics=[Metric(name="P/E", value="39.6x", source="Yahoo Finance")],
        sources=["Yahoo Finance"],
    ))
    assert set(report["analysis"]) == {"executive_summary", "sources"}

    saved = save_report(report, "AAPL", ["markdown"], OutputConfig(output_dir=str(tmp_path)))
    markdown = open(saved["formats"]["markdown"]).read()
    assert "### Risks" not in markdown and "### Financial Analysis" not in markdown
    assert "P/E is 39.6x." in markdown
