"""Financial analysis subagent for performing quantitative and qualitative analysis."""

from deepagents import SubAgent

from . import load_prompt
from ..tools.analysis import ANALYSIS_TOOLS


def create_analyst_subagent() -> SubAgent:
    """Create the financial analysis subagent spec.

    The subagent inherits the main agent's model.

    Returns:
        SubAgent spec for financial analysis
    """
    return {
        "name": "analyst",
        "description": (
            "Performs financial analysis: growth, margins, returns, cash flow, leverage, "
            "valuation, peer comparison, and risk assessment. Give it the ticker(s) and "
            "what to assess; it computes standard metrics itself with its own tools. Pass "
            "qualitative findings (filings, news, internal data) it should weigh, not raw "
            "financial statements."
        ),
        "system_prompt": load_prompt(
            "analyst",
            "You are a specialized financial analyst agent. Calculate ratios, compare "
            "companies, assess risks, and analyze trends. Provide detailed, accurate "
            "analysis based on the financial data provided.",
        ),
        "tools": ANALYSIS_TOOLS,
    }
