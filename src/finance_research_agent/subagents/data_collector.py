"""Data collection subagent for gathering financial data from multiple sources."""

from deepagents import SubAgent

from . import load_prompt
from ..tools.stock_data import STOCK_DATA_TOOLS
from ..tools.sec_filings import SEC_FILINGS_TOOLS
from ..tools.news import NEWS_TOOLS


def create_data_collector_subagent() -> SubAgent:
    """Create the data collection subagent spec.

    The subagent inherits the main agent's model.

    Returns:
        SubAgent spec for data collection
    """
    return {
        "name": "data_collector",
        "description": (
            "Collects public market data for a ticker: company profile, price history, "
            "valuation metrics, financial statements, SEC filings, and recent news. "
            "Give it the ticker and exactly which data you need."
        ),
        "system_prompt": load_prompt(
            "data_collector",
            "You are a specialized data collection agent for financial research. Gather "
            "comprehensive financial data from stock prices, financial statements, SEC "
            "filings, and news articles. Be thorough and collect all data requested.",
        ),
        "tools": STOCK_DATA_TOOLS + SEC_FILINGS_TOOLS + NEWS_TOOLS,
    }
