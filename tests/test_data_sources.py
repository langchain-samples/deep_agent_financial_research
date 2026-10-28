"""Offline tests for SEC EDGAR and RSS news parsing (no network)."""

from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

import pytest

from finance_research_agent.tools import sec_filings
from finance_research_agent.tools.news import parse_rss
from finance_research_agent.tools.sec_filings import (
    extract_financials,
    find_section,
    html_to_text,
    recent_filings,
)

SUBMISSIONS = {
    "filings": {
        "recent": {
            "form": ["8-K", "10-Q", "10-K"],
            "filingDate": ["2026-10-01", "2026-07-31", "2025-10-31"],
            "reportDate": ["2026-10-01", "2026-06-27", "2025-09-27"],
            "accessionNumber": ["0000320193-26-000030", "0000320193-26-000020", "../../etc"],
            "primaryDocument": ["a8k.htm", "aapl-20260627.htm", "aapl-20250927.htm"],
            "items": ["2.02,9.01", "", ""],
        }
    }
}


def test_recent_filings_filters_and_builds_urls():
    filings = recent_filings(SUBMISSIONS, 320193, None)
    assert [f["form"] for f in filings] == ["8-K", "10-Q", "10-K"]
    assert filings[0]["items"] == "2.02,9.01"
    assert filings[1]["url"] == (
        "https://www.sec.gov/Archives/edgar/data/320193/000032019326000020/aapl-20260627.htm"
    )
    assert recent_filings(SUBMISSIONS, 320193, "10-q")[0]["form"] == "10-Q"


def test_recent_filings_rejects_unsafe_path_parts():
    ten_k = recent_filings(SUBMISSIONS, 320193, "10-K")[0]
    assert ten_k["url"] is None


def test_find_section_skips_table_of_contents():
    text = (
        "Table of Contents\nItem 1. Business 3\nItem 1A. Risk Factors 10\nItem 2. Properties 20\n"
        "Item 1. Business\nWe make phones. " + "x" * 200 + "\n"
        "Item 1A. Risk Factors\nThe Company faces many risks. " + "y" * 500 + "\n"
        "Item 2. Properties\nWe own buildings."
    )
    start = find_section(text, "1A")
    assert text[start:].startswith("Item 1A. Risk Factors\nThe Company faces")
    assert text[find_section(text, "Item 2"):].startswith("Item 2. Properties")
    assert find_section(text, "Item 9") is None


def test_find_section_handles_running_page_headers():
    text = (
        "Item 2. Management's Discussion 5\nItem 3. Market Risk 9\n"
        "Item 2. Management's Discussion\nOverview starts here. " + "a" * 300 + "\n"
        "Item 2\nLiquidity\n" + "b" * 400 + "\n"
        "Item 3. Quantitative Disclosures\nRates."
    )
    assert text[find_section(text, "2"):].startswith("Item 2. Management's Discussion\nOverview")


def test_find_section_ignores_cross_references():
    text = (
        "Item 1A. Risk Factors\nRisks here. " + "r" * 100 + "\n"
        "Item 7. Management's Discussion\nAs described in\n"
        "Item 1A\nof this Form 10-K under the heading Risk Factors, margins may fall. " + "m" * 800 + "\n"
        "Item 8. Financial Statements\nNumbers."
    )
    assert text[find_section(text, "1A"):].startswith("Item 1A. Risk Factors")


def test_html_to_text_strips_markup_and_hidden_xbrl():
    html = b"<html><ix:header>hidden facts</ix:header><style>p{}</style><p>Revenue&nbsp; grew</p><div>10%</div></html>"
    assert html_to_text(html) == "Revenue grew\n10%"


def _fact(val, start, end, form, fy, fp, filed, accn="0000000000-00-000001"):
    fact = {"val": val, "end": end, "form": form, "fy": fy, "fp": fp, "filed": filed, "accn": accn}
    if start:
        fact["start"] = start
    return fact


def test_extract_financials_picks_latest_annual_and_quarter():
    facts = {"facts": {"us-gaap": {
        # Older concept with stale data should lose to the newer one
        "Revenues": {"units": {"USD": [_fact(100, "2017-10-01", "2018-09-29", "10-K", 2018, "FY", "2018-11-05")]}},
        "RevenueFromContractWithCustomerExcludingAssessedTax": {"units": {"USD": [
            _fact(380, "2023-10-01", "2024-09-28", "10-K", 2024, "FY", "2024-11-01"),
            _fact(390, "2024-09-29", "2025-09-27", "10-K", 2025, "FY", "2025-10-31"),
            _fact(95, "2026-03-29", "2026-06-27", "10-Q", 2026, "Q3", "2026-07-31"),
            # Nine-month year-to-date figure must not be picked as the quarter
            _fact(300, "2025-09-28", "2026-06-27", "10-Q", 2026, "Q3", "2026-07-31"),
        ]}},
        # Cash flow is only reported year-to-date in 10-Qs
        "NetCashProvidedByUsedInOperatingActivities": {"units": {"USD": [
            _fact(25, "2025-09-28", "2025-12-27", "10-Q", 2026, "Q1", "2026-01-30"),
            _fact(80, "2025-09-28", "2026-06-27", "10-Q", 2026, "Q3", "2026-07-31"),
        ]}},
        "Assets": {"units": {"USD": [
            _fact(360, None, "2025-09-27", "10-K", 2025, "FY", "2025-10-31"),
            _fact(340, None, "2026-06-27", "10-Q", 2026, "Q3", "2026-07-31"),
        ]}},
    }}}
    metrics = extract_financials(facts)

    revenue = metrics["revenue"]
    assert revenue["concept"] == "RevenueFromContractWithCustomerExcludingAssessedTax"
    assert revenue["annual"]["value"] == 390 and revenue["annual"]["fiscal_year"] == 2025
    assert revenue["latest_quarter"]["value"] == 95
    assert revenue["latest_quarter"]["duration_days"] == 90
    cash_flow = metrics["operating_cash_flow"]["latest_quarter"]
    assert (cash_flow["value"], cash_flow["period_end"], cash_flow["duration_days"]) == (80, "2026-06-27", 272)
    assert metrics["total_assets"]["annual"]["value"] == 360
    assert metrics["total_assets"]["latest_quarter"]["value"] == 340
    assert "net_income" not in metrics


def test_sec_tools_require_user_agent(monkeypatch):
    monkeypatch.delenv("SEC_USER_AGENT", raising=False)
    sec_filings._ticker_map.cache_clear()
    result = sec_filings.search_sec_filings.invoke({"ticker": "AAPL"})
    assert "SEC_USER_AGENT" in result["error"]


def test_sec_tools_validate_inputs():
    assert "Invalid" in sec_filings.get_filing_content.invoke({"ticker": "AAPL", "filing_type": "XYZ"})["error"]
    assert "Invalid" in sec_filings.get_filing_content.invoke(
        {"ticker": "AAPL", "filing_type": "10-K", "date": "last year"}
    )["error"]


def _rss(*items):
    body = "".join(
        f"<item><title>{t}</title><link>https://example.com/{i}</link>"
        f"<pubDate>{format_datetime(d)}</pubDate><description>&lt;b&gt;{t}&lt;/b&gt; details</description>"
        f"<source url='https://example.com'>Example</source></item>"
        for i, (t, d) in enumerate(items)
    )
    return f"<?xml version='1.0'?><rss><channel>{body}</channel></rss>".encode()


def test_parse_rss_filters_by_date_and_strips_html():
    now = datetime.now(timezone.utc)
    xml = _rss(("Old news", now - timedelta(days=10)), ("Fresh news", now - timedelta(hours=2)))
    articles = parse_rss(xml, days=7)
    assert [a["title"] for a in articles] == ["Fresh news"]
    assert articles[0]["description"] == "Fresh news details"
    assert articles[0]["source"] == "Example"


def test_parse_rss_rejects_entity_expansion():
    bomb = b"""<?xml version="1.0"?><!DOCTYPE r [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;&a;">]>
    <rss><channel><item><title>&b;</title></item></channel></rss>"""
    with pytest.raises(Exception):
        parse_rss(bomb, days=7)


def test_statement_to_dict_orients_by_period_and_drops_missing():
    import pandas as pd
    from finance_research_agent.tools.analysis import calculate_financial_ratios
    from finance_research_agent.tools.stock_data import statement_to_dict

    periods = [pd.Timestamp("2025-09-30"), pd.Timestamp("2024-09-30")]
    income = pd.DataFrame(
        {periods[0]: [400.0, 100.0, 7.456, 1.0], periods[1]: [380.0, 90.0, 6.1, float("nan")]},
        index=["Total Revenue", "Net Income", "Diluted EPS", "Obscure Item"],
    )
    balance = pd.DataFrame(
        {periods[0]: [350.0, 280.0, 70.0], periods[1]: [360.0, 300.0, 60.0]},
        index=["Total Assets", "Total Liabilities Net Minority Interest", "Stockholders Equity"],
    )
    result = statement_to_dict(income, ["Total Revenue", "Net Income", "Diluted EPS", "Missing"])
    assert result == {
        "2025-09-30": {"Total Revenue": 400, "Net Income": 100, "Diluted EPS": 7.46},
        "2024-09-30": {"Total Revenue": 380, "Net Income": 90, "Diluted EPS": 6.1},
    }
    assert "Obscure Item" not in statement_to_dict(income, None)["2024-09-30"]

    ratios = calculate_financial_ratios.invoke({"data": {
        "income_statement": result, "balance_sheet": statement_to_dict(balance, None),
    }})["ratios"]
    assert ratios["profit_margin"] == 25.0
    assert ratios["debt_to_equity"] == 4.0


def test_summarize_prices_and_weekly_closes():
    import numpy as np
    import pandas as pd
    from finance_research_agent.tools.stock_data import summarize_prices, weekly_closes

    index = pd.bdate_range("2025-01-01", periods=260)
    close = pd.Series(np.linspace(100, 130, 260), index=index)
    close.iloc[100] = 90  # one-day dip creates a drawdown
    hist = pd.DataFrame({"Close": close, "High": close + 1, "Low": close - 1, "Volume": 1000})

    summary = summarize_prices(hist)
    assert summary["current_price"] == 130.0
    assert summary["price_change_pct"] == 30.0
    assert -20 < summary["max_drawdown_pct"] < -19  # 90 vs prior peak ~111.6
    assert {"return_1m_pct", "return_1y_pct", "sma_50", "sma_200"} <= summary.keys()

    weekly = weekly_closes(hist)
    # 260 business days from Wed 2025-01-01 span 53 Friday-ending weeks
    assert len(weekly["prices"]["close"]) == len(weekly["dates"]) == 53


def test_merge_articles_dedupes_by_title():
    from finance_research_agent.tools.news import merge_articles
    a = [{"title": "Apple beats - Reuters", "published_at": "2026-10-27T10:00:00+00:00"}]
    b = [{"title": "Apple Beats", "published_at": "2026-10-27T11:00:00+00:00"},
         {"title": "Apple guidance", "published_at": "2026-10-28T09:00:00+00:00"}]
    assert [x["title"] for x in merge_articles(a, b)] == ["Apple guidance", "Apple beats - Reuters"]


def test_parse_rss_falls_back_to_link_domain_for_source():
    now = datetime.now(timezone.utc)
    xml = (f"<rss><channel><item><title>T</title><link>https://www.fool.com/a</link>"
           f"<pubDate>{format_datetime(now)}</pubDate></item></channel></rss>").encode()
    assert parse_rss(xml, days=1)[0]["source"] == "www.fool.com"


def _statements():
    fy, prior, oldest = "2025-09-30", "2024-09-30", "2022-09-30"
    income = {
        fy: {"Total Revenue": 400, "Gross Profit": 180, "Operating Income": 120, "EBITDA": 140,
             "Net Income": 100, "Diluted EPS": 6.0},
        prior: {"Total Revenue": 380, "Gross Profit": 170, "Operating Income": 110, "EBITDA": 130,
                "Net Income": 80, "Diluted EPS": 5.0},
        oldest: {"Total Revenue": 320},
    }
    balance = {
        fy: {"Stockholders Equity": 60, "Total Assets": 350, "Total Debt": 90,
             "Cash Cash Equivalents And Short Term Investments": 50,
             "Current Assets": 150, "Current Liabilities": 160},
        prior: {"Stockholders Equity": 40, "Total Assets": 330},
    }
    cashflow = {fy: {"Operating Cash Flow": 110, "Free Cash Flow": 100, "Capital Expenditure": -10,
                     "Repurchase Of Capital Stock": -80, "Cash Dividends Paid": -15}}
    return income, balance, cashflow


def test_compute_financial_metrics():
    from finance_research_agent.tools.analysis import compute_financial_metrics

    income, balance, cashflow = _statements()
    m = compute_financial_metrics(
        income, balance, cashflow, {"market_cap": 4000},
        {"current_price": 110.0, "sma_50": 100.0, "sma_200": 88.0},
    )
    assert m["periods"] == {"fiscal_year_end": "2025-09-30", "prior_fiscal_year_end": "2024-09-30"}
    assert m["growth"]["revenue_yoy_pct"] == 5.26
    assert m["growth"]["net_income_yoy_pct"] == 25.0
    assert (m["growth"]["revenue_cagr_years"], m["growth"]["revenue_cagr_pct"]) == (3, 7.72)
    assert m["margins"]["latest_fy"] == {"gross_pct": 45.0, "operating_pct": 30.0, "ebitda_pct": 35.0, "net_pct": 25.0}
    assert m["returns"]["roe_avg_equity_pct"] == 200.0  # 100 / avg(60, 40)
    assert m["returns"]["roe_ending_equity_pct"] == 166.67
    assert m["cash_flow"]["fcf_conversion_pct"] == 100.0
    assert m["cash_flow"]["capex_pct_revenue"] == 2.5
    assert m["balance_sheet"]["net_debt"] == 40
    assert m["balance_sheet"]["net_debt_to_ebitda"] == 0.29
    assert m["balance_sheet"]["current_ratio"] == 0.94
    assert m["capital_return"] == {"buybacks": 80, "dividends": 15, "total": 95, "pct_of_fcf": 95.0}
    assert m["valuation"]["enterprise_value"] == 4040
    assert m["valuation"]["pe_on_latest_fy"] == 40.0
    assert m["price"]["pct_vs_sma_50"] == 10.0
    assert m["price"]["pct_vs_sma_200"] == 25.0
    assert m["unavailable"] == []


def test_compute_financial_metrics_handles_missing_inputs():
    from finance_research_agent.tools.analysis import compute_financial_metrics

    m = compute_financial_metrics({"2025-09-30": {"Total Revenue": 100, "Net Income": 0}}, {}, {})
    assert m["growth"]["revenue_yoy_pct"] is None
    assert m["returns"]["roe_avg_equity_pct"] is None
    assert m["cash_flow"]["fcf_conversion_pct"] is None  # FCF missing and net income zero
    assert "valuation" not in m and "price" not in m
    assert "growth.revenue_yoy_pct" in m["unavailable"]
    assert compute_financial_metrics({}, {}, {}) == {"error": "No income statement data available"}


def test_calculate_financial_ratios_errors_instead_of_empty_success():
    from finance_research_agent.tools.analysis import calculate_financial_ratios

    result = calculate_financial_ratios.invoke({"data": {"income_statement": {"Net Income": {"2025": 1}}}})
    assert result["status"] == "error" and "get_financial_metrics" in result["error"]
