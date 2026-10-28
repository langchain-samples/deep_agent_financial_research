"""Structured output schema for the research report."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Metric(BaseModel):
    """A single reported figure with its provenance."""

    name: str = Field(description="Metric name, e.g. 'P/E ratio' or 'Revenue (FY2025)'")
    value: str = Field(description="Value with units, e.g. '28.4x' or '$391.0B'")
    source: str = Field(description="Where the figure came from, e.g. 'Yahoo Finance' or a table name")


class ResearchReport(BaseModel):
    """Final structured research report returned by the main agent."""

    ticker: str = Field(description="Primary ticker symbol researched")
    company_name: str = Field(description="Company name")
    executive_summary: str = Field(
        description="3-6 sentence summary of key findings, or the direct answer to a quick question"
    )
    key_metrics: List[Metric] = Field(
        default_factory=list, description="Important figures, each with a source"
    )
    financial_analysis: str = Field(
        default="", description="Ratio, trend, and peer analysis narrative (empty for quick questions)"
    )
    risks: List[str] = Field(
        default_factory=list, description="Key risks, one per item (empty for quick questions)"
    )
    news_sentiment: str = Field(
        default="", description="Summary of recent news and sentiment (empty if not relevant)"
    )
    internal_data_findings: Optional[str] = Field(
        default=None,
        description="Findings from internal Snowflake data, if it was queried",
    )
    sources: List[str] = Field(default_factory=list, description="Data sources and filings cited")
    limitations: List[str] = Field(
        default_factory=list,
        description="Data that was unavailable or caveats on the analysis",
    )


def report_to_output_dict(report: ResearchReport) -> Dict[str, Any]:
    """Convert a ResearchReport into the dict shape the report renderers expect."""
    sections = {
        "executive_summary": report.executive_summary,
        "financial_analysis": report.financial_analysis,
        "risks": report.risks,
        "news_sentiment": report.news_sentiment,
        "internal_data_findings": report.internal_data_findings,
        "sources": report.sources,
        "limitations": report.limitations,
    }
    # Quick answers leave most sections empty; omit them so renderers don't print blank headings
    output: Dict[str, Any] = {
        "metadata": {
            "ticker": report.ticker,
            "company_name": report.company_name,
            "generated_at": datetime.now().isoformat(),
        },
        "analysis": {key: value for key, value in sections.items() if value},
    }
    if report.key_metrics:
        output["stock_info"] = {m.name: f"{m.value} ({m.source})" for m in report.key_metrics}
    return output
