"""Tools for financial analysis including ratios, comparisons, and risk assessment."""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
from langchain.tools import tool
from ..utils.validators import validate_ticker, normalize_ticker


@tool
def calculate_financial_ratios(data: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate financial ratios from provided financial data.
    
    Args:
        data: Dictionary containing financial statement data
    
    Returns:
        Dictionary containing calculated financial ratios
    """
    try:
        ratios = {}
        
        # Extract key values (these would come from financial statements)
        income_stmt = data.get("income_statement", {})
        balance_sheet = data.get("balance_sheet", {})
        cashflow = data.get("cashflow", {})
        
        # Get most recent period (assuming data is structured with dates as keys)
        if income_stmt:
            latest_period = max(income_stmt.keys()) if isinstance(income_stmt, dict) else None
            if latest_period:
                income_data = income_stmt[latest_period]
                balance_data = balance_sheet.get(latest_period, {}) if balance_sheet else {}
                
                revenue = income_data.get("Total Revenue", income_data.get("Revenue", 0))
                net_income = income_data.get("Net Income", 0)
                total_assets = balance_data.get("Total Assets", 0)
                total_equity = balance_data.get("Total Stockholders Equity", balance_data.get("Stockholders Equity", 0))
                total_liabilities = balance_data.get("Total Liabilities", balance_data.get("Total Liabilities Net Minority Interest", 0))
                
                # Profitability ratios
                if revenue and revenue != 0:
                    ratios["profit_margin"] = (net_income / revenue) * 100 if net_income else 0
                    ratios["gross_margin"] = income_data.get("Gross Profit", 0) / revenue * 100 if income_data.get("Gross Profit") else 0
                
                # Efficiency ratios
                if total_assets and total_assets != 0:
                    ratios["roa"] = (net_income / total_assets) * 100 if net_income else 0
                    ratios["asset_turnover"] = revenue / total_assets if revenue else 0
                
                # Leverage ratios
                if total_equity and total_equity != 0:
                    ratios["roe"] = (net_income / total_equity) * 100 if net_income else 0
                    ratios["debt_to_equity"] = total_liabilities / total_equity if total_liabilities else 0
                
                # Liquidity ratios (if available)
                current_assets = balance_data.get("Current Assets", 0)
                current_liabilities = balance_data.get("Current Liabilities", 0)
                if current_liabilities and current_liabilities != 0:
                    ratios["current_ratio"] = current_assets / current_liabilities if current_assets else 0
        
        if not ratios:
            return {
                "status": "error",
                "error": "No ratios could be calculated: expected income_statement and "
                "balance_sheet shaped {period_end: {line_item: value}}. Use "
                "get_financial_metrics(ticker) to compute metrics directly.",
            }
        return {
            "status": "success",
            "ratios": ratios,
            "note": "Ratios calculated from provided financial data.",
        }
    except Exception as e:
        return {"error": f"Failed to calculate financial ratios: {str(e)}"}


@tool
def compare_companies(tickers: List[str], metrics: Optional[List[str]] = None) -> Dict[str, Any]:
    """Compare multiple companies across specified metrics.
    
    Args:
        tickers: List of stock ticker symbols to compare
        metrics: List of metrics to compare (optional, uses default metrics if not provided)
    
    Returns:
        Dictionary containing comparison data
    """
    try:
        tickers = [normalize_ticker(t) for t in tickers]
        for ticker in tickers:
            if not validate_ticker(ticker):
                return {"error": f"Invalid ticker symbol: {ticker}"}
        
        if metrics is None:
            metrics = ["current_price", "pe_ratio", "market_cap", "revenue", "profit_margin", "roe"]
        
        import yfinance as yf
        
        comparison = {}
        for ticker in tickers:
            stock = yf.Ticker(ticker)
            info = stock.info
            
            comparison[ticker] = {}
            for metric in metrics:
                if metric == "current_price":
                    comparison[ticker][metric] = info.get("currentPrice", info.get("regularMarketPrice", "N/A"))
                elif metric == "pe_ratio":
                    comparison[ticker][metric] = info.get("trailingPE", info.get("forwardPE", "N/A"))
                elif metric == "market_cap":
                    comparison[ticker][metric] = info.get("marketCap", "N/A")
                elif metric == "revenue":
                    comparison[ticker][metric] = info.get("totalRevenue", "N/A")
                elif metric == "profit_margin":
                    comparison[ticker][metric] = info.get("profitMargins", "N/A")
                elif metric == "roe":
                    comparison[ticker][metric] = info.get("returnOnEquity", "N/A")
                else:
                    comparison[ticker][metric] = info.get(metric, "N/A")
        
        return {
            "status": "success",
            "tickers": tickers,
            "metrics": metrics,
            "comparison": comparison,
        }
    except Exception as e:
        return {"error": f"Failed to compare companies: {str(e)}"}


@tool
def assess_risk_profile(ticker: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Assess the risk profile of a company.
    
    Args:
        ticker: Stock ticker symbol
        data: Optional financial data dictionary (if not provided, will fetch)
    
    Returns:
        Dictionary containing risk assessment
    """
    try:
        ticker = normalize_ticker(ticker)
        if not validate_ticker(ticker):
            return {"error": f"Invalid ticker symbol: {ticker}"}
        
        import yfinance as yf
        stock = yf.Ticker(ticker)
        info = stock.info
        
        risk_factors = []
        risk_score = 0
        max_score = 0
        
        # Beta analysis
        beta = info.get("beta", None)
        if beta:
            max_score += 10
            if beta > 1.5:
                risk_factors.append({"factor": "High Beta", "severity": "high", "score": 10})
                risk_score += 10
            elif beta > 1.2:
                risk_factors.append({"factor": "Moderate-High Beta", "severity": "medium", "score": 5})
                risk_score += 5
        
        # Debt to equity
        debt_to_equity = info.get("debtToEquity", None)
        if debt_to_equity:
            max_score += 10
            if debt_to_equity > 2.0:
                risk_factors.append({"factor": "High Debt-to-Equity", "severity": "high", "score": 10})
                risk_score += 10
            elif debt_to_equity > 1.0:
                risk_factors.append({"factor": "Moderate Debt-to-Equity", "severity": "medium", "score": 5})
                risk_score += 5
        
        # Profit margin
        profit_margin = info.get("profitMargins", None)
        if profit_margin:
            max_score += 10
            if profit_margin < 0:
                risk_factors.append({"factor": "Negative Profit Margin", "severity": "high", "score": 10})
                risk_score += 10
            elif profit_margin < 0.05:
                risk_factors.append({"factor": "Low Profit Margin", "severity": "medium", "score": 5})
                risk_score += 5
        
        # Revenue growth
        revenue_growth = info.get("revenueGrowth", None)
        if revenue_growth:
            max_score += 10
            if revenue_growth < -0.1:
                risk_factors.append({"factor": "Declining Revenue", "severity": "high", "score": 10})
                risk_score += 10
            elif revenue_growth < 0:
                risk_factors.append({"factor": "Negative Revenue Growth", "severity": "medium", "score": 5})
                risk_score += 5
        
        # Calculate risk level
        if max_score > 0:
            risk_percentage = (risk_score / max_score) * 100
            if risk_percentage >= 70:
                risk_level = "high"
            elif risk_percentage >= 40:
                risk_level = "medium"
            else:
                risk_level = "low"
        else:
            risk_percentage = 0
            risk_level = "unknown"
        
        return {
            "ticker": ticker,
            "risk_level": risk_level,
            "risk_score": risk_score,
            "max_score": max_score,
            "risk_percentage": risk_percentage,
            "risk_factors": risk_factors,
            "beta": beta,
            "debt_to_equity": debt_to_equity,
            "profit_margin": profit_margin,
            "revenue_growth": revenue_growth,
        }
    except Exception as e:
        return {"error": f"Failed to assess risk profile for {ticker}: {str(e)}"}


@tool
def analyze_trends(data: Dict[str, Any], period: str = "1y") -> Dict[str, Any]:
    """Analyze trends in financial data over time.
    
    Args:
        data: Dictionary containing time series financial data
        period: Time period for analysis
    
    Returns:
        Dictionary containing trend analysis
    """
    try:
        trends = {}
        
        # Analyze price trends if available
        if "prices" in data:
            prices = data["prices"].get("close", [])
            if prices and len(prices) > 1:
                prices_array = np.array(prices)
                
                # Calculate trend
                x = np.arange(len(prices_array))
                slope = np.polyfit(x, prices_array, 1)[0]
                
                trends["price_trend"] = {
                    "direction": "upward" if slope > 0 else "downward",
                    "slope": float(slope),
                    "volatility": float(np.std(prices_array)),
                    "min_price": float(np.min(prices_array)),
                    "max_price": float(np.max(prices_array)),
                    "avg_price": float(np.mean(prices_array)),
                }
        
        # Analyze revenue trends if available
        if "income_statement" in data:
            income_stmt = data["income_statement"]
            if isinstance(income_stmt, dict) and len(income_stmt) > 1:
                revenues = []
                dates = sorted(income_stmt.keys())
                for date in dates:
                    revenue = income_stmt[date].get("Total Revenue", income_stmt[date].get("Revenue", 0))
                    if revenue:
                        revenues.append(revenue)
                
                if len(revenues) > 1:
                    revenues_array = np.array(revenues)
                    x = np.arange(len(revenues_array))
                    slope = np.polyfit(x, revenues_array, 1)[0]
                    
                    trends["revenue_trend"] = {
                        "direction": "upward" if slope > 0 else "downward",
                        "growth_rate": float((revenues[-1] / revenues[0] - 1) * 100) if revenues[0] != 0 else 0,
                        "slope": float(slope),
                    }
        
        return {
            "status": "success",
            "period": period,
            "trends": trends,
        }
    except Exception as e:
        return {"error": f"Failed to analyze trends: {str(e)}"}


def _ratio(numerator: Optional[float], denominator: Optional[float], pct: bool = False) -> Optional[float]:
    """Divide, returning None when either input is missing or the denominator is zero."""
    if numerator is None or denominator in (None, 0):
        return None
    return round(numerator / denominator * (100 if pct else 1), 2)


def _growth_pct(current: Optional[float], prior: Optional[float]) -> Optional[float]:
    if current is None or prior in (None, 0):
        return None
    return round((current - prior) / abs(prior) * 100, 2)


def _flatten_missing(section: Dict[str, Any], prefix: str = "") -> List[str]:
    missing = []
    for key, value in section.items():
        if isinstance(value, dict):
            missing += _flatten_missing(value, f"{prefix}{key}.")
        elif value is None:
            missing.append(f"{prefix}{key}")
    return missing


def compute_financial_metrics(
    income: Dict[str, Dict[str, float]],
    balance: Dict[str, Dict[str, float]],
    cashflow: Dict[str, Dict[str, float]],
    market: Optional[Dict[str, Any]] = None,
    price_summary: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Compute standard metrics from annual statements shaped {period_end: {line_item: value}}.

    Uses the latest fiscal year, with the prior year for growth and averages. Returns None for
    any metric whose inputs are missing, and lists those under "unavailable".
    """
    periods = sorted(income, reverse=True)
    if not periods:
        return {"error": "No income statement data available"}
    fy = periods[0]
    prior = periods[1] if len(periods) > 1 else None

    def get(statement: Dict[str, Dict[str, float]], period: Optional[str], item: str) -> Optional[float]:
        return statement.get(period, {}).get(item) if period else None

    def average(statement: Dict[str, Dict[str, float]], item: str) -> Optional[float]:
        current, previous = get(statement, fy, item), get(statement, prior, item)
        if current is None or previous is None:
            return current
        return (current + previous) / 2

    revenue, prior_revenue = get(income, fy, "Total Revenue"), get(income, prior, "Total Revenue")
    net_income = get(income, fy, "Net Income")
    ebitda = get(income, fy, "EBITDA")
    fcf = get(cashflow, fy, "Free Cash Flow")
    total_debt = get(balance, fy, "Total Debt")
    cash = get(balance, fy, "Cash Cash Equivalents And Short Term Investments")
    if cash is None:
        cash = get(balance, fy, "Cash And Cash Equivalents")
    net_debt = total_debt - cash if total_debt is not None and cash is not None else None
    buybacks = get(cashflow, fy, "Repurchase Of Capital Stock")
    dividends = get(cashflow, fy, "Cash Dividends Paid")
    capital_returned = (
        abs(buybacks or 0) + abs(dividends or 0) if buybacks is not None or dividends is not None else None
    )
    capex = get(cashflow, fy, "Capital Expenditure")

    oldest = next((p for p in reversed(periods) if get(income, p, "Total Revenue")), None)
    cagr, cagr_years = None, None
    if oldest and oldest != fy and revenue and get(income, oldest, "Total Revenue") and revenue > 0:
        cagr_years = round((pd.Timestamp(fy) - pd.Timestamp(oldest)).days / 365.25)
        oldest_revenue = get(income, oldest, "Total Revenue")
        if cagr_years > 0 and oldest_revenue > 0:
            cagr = round(((revenue / oldest_revenue) ** (1 / cagr_years) - 1) * 100, 2)

    def margins(period: Optional[str]) -> Dict[str, Optional[float]]:
        period_revenue = get(income, period, "Total Revenue")
        return {
            "gross_pct": _ratio(get(income, period, "Gross Profit"), period_revenue, pct=True),
            "operating_pct": _ratio(get(income, period, "Operating Income"), period_revenue, pct=True),
            "ebitda_pct": _ratio(get(income, period, "EBITDA"), period_revenue, pct=True),
            "net_pct": _ratio(get(income, period, "Net Income"), period_revenue, pct=True),
        }

    metrics: Dict[str, Any] = {
        "periods": {"fiscal_year_end": fy, "prior_fiscal_year_end": prior},
        "growth": {
            "revenue_yoy_pct": _growth_pct(revenue, prior_revenue),
            "revenue_cagr_pct": cagr,
            "revenue_cagr_years": cagr_years,
            "operating_income_yoy_pct": _growth_pct(
                get(income, fy, "Operating Income"), get(income, prior, "Operating Income")
            ),
            "net_income_yoy_pct": _growth_pct(net_income, get(income, prior, "Net Income")),
            "eps_diluted_yoy_pct": _growth_pct(get(income, fy, "Diluted EPS"), get(income, prior, "Diluted EPS")),
        },
        "margins": {"latest_fy": margins(fy), "prior_fy": margins(prior)},
        "returns": {
            "roe_avg_equity_pct": _ratio(net_income, average(balance, "Stockholders Equity"), pct=True),
            "roe_ending_equity_pct": _ratio(net_income, get(balance, fy, "Stockholders Equity"), pct=True),
            "roa_avg_assets_pct": _ratio(net_income, average(balance, "Total Assets"), pct=True),
        },
        "cash_flow": {
            "operating_cash_flow": get(cashflow, fy, "Operating Cash Flow"),
            "free_cash_flow": fcf,
            "fcf_margin_pct": _ratio(fcf, revenue, pct=True),
            "fcf_conversion_pct": _ratio(fcf, net_income, pct=True),
            "capex_pct_revenue": _ratio(abs(capex) if capex is not None else None, revenue, pct=True),
        },
        "balance_sheet": {
            "total_debt": total_debt,
            "cash_and_short_term_investments": cash,
            "net_debt": net_debt,
            "net_debt_to_ebitda": _ratio(net_debt, ebitda),
            "debt_to_equity": _ratio(total_debt, get(balance, fy, "Stockholders Equity")),
            "current_ratio": _ratio(get(balance, fy, "Current Assets"), get(balance, fy, "Current Liabilities")),
        },
        "capital_return": {
            "buybacks": abs(buybacks) if buybacks is not None else None,
            "dividends": abs(dividends) if dividends is not None else None,
            "total": capital_returned,
            "pct_of_fcf": _ratio(capital_returned, fcf, pct=True),
        },
    }

    market_cap = (market or {}).get("market_cap")
    if market_cap:
        enterprise_value = market_cap + net_debt if net_debt is not None else None
        metrics["valuation"] = {
            "market_cap": market_cap,
            "enterprise_value": enterprise_value,
            "ev_to_ebitda": _ratio(enterprise_value, ebitda),
            "ev_to_revenue": _ratio(enterprise_value, revenue),
            "pe_on_latest_fy": _ratio(market_cap, net_income),
            "fcf_yield_pct": _ratio(fcf, market_cap, pct=True),
        }

    if price_summary:
        current = price_summary.get("current_price")
        sma_50, sma_200 = price_summary.get("sma_50"), price_summary.get("sma_200")
        metrics["price"] = {
            **price_summary,
            "pct_vs_sma_50": _growth_pct(current, sma_50),
            "pct_vs_sma_200": _growth_pct(current, sma_200),
        }

    metrics["unavailable"] = _flatten_missing({k: v for k, v in metrics.items() if k != "periods"})
    metrics["definitions"] = (
        "Annual figures for the fiscal year ending fiscal_year_end. ROE/ROA use average of "
        "latest and prior year-end balances. Net debt = total debt - cash and short-term "
        "investments at fiscal year end. Valuation uses current market cap with fiscal "
        "year-end debt, cash, and earnings. FCF = operating cash flow - capex."
    )
    return metrics


@tool
def get_financial_metrics(ticker: str) -> Dict[str, Any]:
    """Compute standard financial metrics for a company in one call.

    Returns growth (YoY, CAGR), margins (gross, operating, EBITDA, net) for the latest and
    prior fiscal year, ROE/ROA, free cash flow and conversion, net debt and leverage,
    liquidity, capital returns, valuation multiples (EV/EBITDA, EV/revenue, P/E, FCF yield),
    and price performance versus moving averages. Figures are calculated deterministically
    from Yahoo Finance annual statements and one year of daily prices. Use these numbers
    instead of calculating them by hand.

    Args:
        ticker: Stock ticker symbol

    Returns:
        Dictionary of computed metrics by category, with periods, definitions, and any
        metrics that could not be computed
    """
    ticker = normalize_ticker(ticker)
    if not validate_ticker(ticker):
        return {"error": f"Invalid ticker symbol: {ticker}"}

    try:
        import yfinance as yf
        from .stock_data import statement_to_dict, summarize_prices

        stock = yf.Ticker(ticker)
        income = statement_to_dict(stock.financials)
        if not income:
            return {"error": f"No financial statements available for {ticker}", "ticker": ticker}
        info = stock.info or {}
        history = stock.history(period="1y")

        trading_currency = info.get("currency")
        financial_currency = info.get("financialCurrency") or trading_currency
        # Market cap is in the trading currency; skip valuation if statements use another one
        market = (
            {"market_cap": info.get("marketCap")}
            if trading_currency == financial_currency else None
        )
        metrics = compute_financial_metrics(
            income,
            statement_to_dict(stock.balance_sheet),
            statement_to_dict(stock.cashflow),
            market,
            summarize_prices(history) if not history.empty else None,
        )
        return {
            "ticker": ticker,
            "currency": financial_currency,
            **metrics,
            "source": "Computed from Yahoo Finance annual statements and 1y daily prices",
        }
    except Exception as e:
        return {"error": f"Failed to compute financial metrics for {ticker}: {str(e)}"}


# Export all tools
ANALYSIS_TOOLS = [
    get_financial_metrics,
    compare_companies,
    assess_risk_profile,
]
