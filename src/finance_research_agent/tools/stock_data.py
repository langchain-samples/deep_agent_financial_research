"""Tools for fetching stock data from Yahoo Finance and other sources."""

import numpy as np
import pandas as pd
import yfinance as yf
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from langchain.tools import tool
from ..utils.validators import validate_ticker, normalize_ticker, validate_period
from .news import fetch_ticker_news


@tool
def get_stock_info(ticker: str) -> Dict[str, Any]:
    """Get basic stock information for a given ticker symbol.
    
    Args:
        ticker: Stock ticker symbol (e.g., 'AAPL', 'MSFT')
    
    Returns:
        Dictionary containing basic stock information including company name, sector, industry, etc.
    """
    ticker = normalize_ticker(ticker)
    if not validate_ticker(ticker):
        return {"error": f"Invalid ticker symbol: {ticker}"}
    
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        return {
            "ticker": ticker,
            "name": info.get("longName", info.get("shortName", "N/A")),
            "sector": info.get("sector", "N/A"),
            "industry": info.get("industry", "N/A"),
            "market_cap": info.get("marketCap", "N/A"),
            "current_price": info.get("currentPrice", info.get("regularMarketPrice", "N/A")),
            "currency": info.get("currency", "USD"),
            "exchange": info.get("exchange", "N/A"),
            "website": info.get("website", "N/A"),
            "description": info.get("longBusinessSummary", "N/A"),
        }
    except Exception as e:
        return {"error": f"Failed to fetch stock info for {ticker}: {str(e)}"}


@tool
def get_stock_metrics(ticker: str) -> Dict[str, Any]:
    """Get financial metrics for a stock (P/E ratio, P/B ratio, etc.).
    
    Args:
        ticker: Stock ticker symbol
    
    Returns:
        Dictionary containing financial metrics
    """
    ticker = normalize_ticker(ticker)
    if not validate_ticker(ticker):
        return {"error": f"Invalid ticker symbol: {ticker}"}
    
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        return {
            "ticker": ticker,
            "pe_ratio": info.get("trailingPE", info.get("forwardPE", "N/A")),
            "pb_ratio": info.get("priceToBook", "N/A"),
            "ps_ratio": info.get("priceToSalesTrailing12Months", "N/A"),
            "dividend_yield": info.get("dividendYield", "N/A"),
            "52_week_high": info.get("fiftyTwoWeekHigh", "N/A"),
            "52_week_low": info.get("fiftyTwoWeekLow", "N/A"),
            "beta": info.get("beta", "N/A"),
            "debt_to_equity": info.get("debtToEquity", "N/A"),
            "roe": info.get("returnOnEquity", "N/A"),
            "roa": info.get("returnOnAssets", "N/A"),
            "profit_margin": info.get("profitMargins", "N/A"),
            "revenue_growth": info.get("revenueGrowth", "N/A"),
            "earnings_growth": info.get("earningsGrowth", "N/A"),
        }
    except Exception as e:
        return {"error": f"Failed to fetch metrics for {ticker}: {str(e)}"}


@tool
def get_historical_prices(ticker: str, period: str = "1y") -> Dict[str, Any]:
    """Get historical price performance for a stock.

    Returns summary statistics (returns, volatility, drawdown, moving averages) computed
    from daily prices, plus weekly closing prices for trend analysis.

    Args:
        ticker: Stock ticker symbol
        period: Time period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)

    Returns:
        Dictionary containing price summary and weekly closes
    """
    ticker = normalize_ticker(ticker)
    if not validate_ticker(ticker):
        return {"error": f"Invalid ticker symbol: {ticker}"}

    if not validate_period(period):
        return {"error": f"Invalid period: {period}"}

    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period)

        if hist.empty:
            return {"error": f"No historical data available for {ticker}"}

        return {
            "ticker": ticker,
            "period": period,
            "data_points": len(hist),
            "start_date": hist.index[0].strftime("%Y-%m-%d"),
            "end_date": hist.index[-1].strftime("%Y-%m-%d"),
            "summary": summarize_prices(hist),
            # Weekly closes keep trend analysis possible without hundreds of daily rows
            **weekly_closes(hist),
        }
    except Exception as e:
        return {"error": f"Failed to fetch historical prices for {ticker}: {str(e)}"}


def summarize_prices(hist: pd.DataFrame) -> Dict[str, Any]:
    """Compute return, risk, and trend statistics from a daily OHLCV DataFrame."""
    close = hist["Close"]
    daily_returns = close.pct_change().dropna()
    summary: Dict[str, Any] = {
        "current_price": round(float(close.iloc[-1]), 2),
        "price_change_pct": round(float((close.iloc[-1] / close.iloc[0] - 1) * 100), 2),
        "period_high": round(float(hist["High"].max()), 2),
        "period_low": round(float(hist["Low"].min()), 2),
        "avg_daily_volume": int(hist["Volume"].mean()),
        "annualized_volatility_pct": (
            round(float(daily_returns.std() * np.sqrt(252) * 100), 2) if len(daily_returns) > 1 else None
        ),
        "max_drawdown_pct": round(float((close / close.cummax() - 1).min() * 100), 2),
    }
    for label, days in (("1m", 21), ("3m", 63), ("6m", 126), ("1y", 252)):
        if len(close) > days:
            summary[f"return_{label}_pct"] = round(float((close.iloc[-1] / close.iloc[-days - 1] - 1) * 100), 2)
    for window in (50, 200):
        if len(close) >= window:
            summary[f"sma_{window}"] = round(float(close.iloc[-window:].mean()), 2)
    return summary


def weekly_closes(hist: pd.DataFrame) -> Dict[str, Any]:
    """Downsample daily closes to weekly, in the shape analyze_trends expects."""
    weekly = hist["Close"].resample("W-FRI").last().dropna()
    return {
        "dates": weekly.index.strftime("%Y-%m-%d").tolist(),
        "prices": {"close": [round(float(v), 2) for v in weekly]},
    }


# Line items returned by get_financial_statements unless detail=True
KEY_LINE_ITEMS = {
    "income_statement": [
        "Total Revenue", "Cost Of Revenue", "Gross Profit", "Research And Development",
        "Selling General And Administration", "Operating Income", "EBITDA", "Interest Expense",
        "Pretax Income", "Tax Provision", "Net Income", "Diluted EPS", "Diluted Average Shares",
    ],
    "balance_sheet": [
        "Total Assets", "Current Assets", "Cash And Cash Equivalents",
        "Cash Cash Equivalents And Short Term Investments", "Receivables", "Inventory",
        "Total Liabilities Net Minority Interest", "Current Liabilities", "Total Debt",
        "Long Term Debt", "Net Debt", "Stockholders Equity", "Retained Earnings",
    ],
    "cashflow": [
        "Operating Cash Flow", "Capital Expenditure", "Free Cash Flow",
        "Repurchase Of Capital Stock", "Cash Dividends Paid", "Depreciation And Amortization",
        "Stock Based Compensation",
    ],
}


def statement_to_dict(df: pd.DataFrame, line_items: Optional[List[str]] = None) -> Dict[str, Dict[str, float]]:
    """Convert a yfinance statement (line items x periods) to {period: {line_item: value}}.

    Missing values are dropped. Values are rounded to whole units except per-share figures.
    """
    if df.empty:
        return {}
    if line_items is not None:
        df = df.loc[[item for item in line_items if item in df.index]]
    result = {}
    for period, column in df.items():
        values = {}
        for item, value in column.dropna().items():
            values[str(item)] = round(float(value), 2) if "EPS" in str(item) else int(value)
        result[pd.Timestamp(period).strftime("%Y-%m-%d")] = values
    return result


@tool
def get_financial_statements(ticker: str, detail: bool = False) -> Dict[str, Any]:
    """Get annual financial statements (income statement, balance sheet, cash flow) for a stock.

    Args:
        ticker: Stock ticker symbol
        detail: Return every line item instead of the key items (default: False)

    Returns:
        Dictionary with each statement as {period_end_date: {line_item: value}}
    """
    ticker = normalize_ticker(ticker)
    if not validate_ticker(ticker):
        return {"error": f"Invalid ticker symbol: {ticker}"}

    try:
        stock = yf.Ticker(ticker)
        statements = {
            "income_statement": stock.financials,
            "balance_sheet": stock.balance_sheet,
            "cashflow": stock.cashflow,
        }
        return {
            "ticker": ticker,
            **{
                name: statement_to_dict(df, None if detail else KEY_LINE_ITEMS[name])
                for name, df in statements.items()
            },
            "source": "Yahoo Finance",
        }
    except Exception as e:
        return {"error": f"Failed to fetch financial statements for {ticker}: {str(e)}"}


@tool
def get_company_news(ticker: str, num_articles: int = 10) -> Dict[str, Any]:
    """Get recent news articles about a company.
    
    Args:
        ticker: Stock ticker symbol
        num_articles: Number of articles to retrieve (default: 10)
    
    Returns:
        Dictionary containing news articles
    """
    ticker = normalize_ticker(ticker)
    if not validate_ticker(ticker):
        return {"error": f"Invalid ticker symbol: {ticker}"}
    
    try:
        articles = fetch_ticker_news(ticker, days=30)[:num_articles]
        return {
            "ticker": ticker,
            "num_articles": len(articles),
            "articles": articles,
            "source": "Yahoo Finance RSS",
        }
    except Exception as e:
        return {"error": f"Failed to fetch news for {ticker}: {str(e)}"}


# Export all tools
STOCK_DATA_TOOLS = [
    get_stock_info,
    get_stock_metrics,
    get_historical_prices,
    get_financial_statements,
    get_company_news,
]
