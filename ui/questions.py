"""Sample questions for demos, grouped by what they show off.

Each question uses only data the agent can reach: Yahoo Finance, SEC EDGAR filings and
XBRL financials, public news RSS, and (for "Internal data") the Snowflake warehouse.
"""

SAMPLE_QUESTIONS = {
    "Quick answers (under a minute)": [
        {
            "label": "Apple valuation snapshot",
            "question": "What are Apple's (AAPL) current share price, market cap, and P/E ratio?",
            "shows": "A single delegation and a short, sourced answer.",
        },
        {
            "label": "Microsoft FY revenue (10-K)",
            "question": "What were Microsoft's (MSFT) revenue and net income in its latest fiscal "
            "year, as reported to the SEC?",
            "shows": "As-filed XBRL figures straight from SEC EDGAR, with the filing cited.",
        },
        {
            "label": "NVIDIA latest filings",
            "question": "When did NVIDIA (NVDA) file its most recent 10-K and 10-Q?",
            "shows": "SEC filing index lookup with links to the documents.",
        },
        {
            "label": "JPM 1-year performance",
            "question": "How has JPMorgan Chase (JPM) stock performed over the past year, and how "
            "volatile has it been?",
            "shows": "Price statistics: return, volatility, drawdown, moving averages.",
        },
        {
            "label": "Tesla headlines",
            "question": "What are the latest news headlines on Tesla (TSLA)?",
            "shows": "Live news from public RSS feeds, no API key.",
        },
        {
            "label": "Internal rating: BLDR",
            "question": "What is our latest internal rating and price target on Builders "
            "FirstSource (BLDR), and which analyst issued it?",
            "shows": "A read-only lookup in the internal Snowflake research data.",
            "requires_snowflake": True,
        },
    ],
    "Company research": [
        {
            "label": "Full report: Microsoft",
            "question": "Give me a full research report on Microsoft (MSFT): valuation, "
            "results from the latest 10-Q, key risks, and recent news sentiment.",
            "shows": "End-to-end planning and all public data sources in one report.",
        },
        {
            "label": "Earnings preview: Amazon",
            "question": "Prepare an earnings preview for Amazon (AMZN): recent quarterly "
            "trends from SEC filings, what the news is focused on, and the metrics to watch.",
            "shows": "Quarterly XBRL data plus news synthesis into a forward-looking brief.",
        },
        {
            "label": "Peer comparison: JPM vs BAC",
            "question": "Compare JPMorgan Chase (JPM) and Bank of America (BAC) on "
            "profitability, balance sheet strength, and valuation. Which looks better positioned?",
            "shows": "Multi-company data collection and side-by-side analysis.",
        },
        {
            "label": "Balance sheet risk: Ford",
            "question": "Assess the balance sheet and liquidity risk of Ford (F): leverage, "
            "debt levels, cash position, free cash flow, and share price volatility.",
            "shows": "Risk-focused analysis with ratio calculations and drawdown/volatility stats.",
        },
    ],
    "SEC filings": [
        {
            "label": "10-K risk factors: NVIDIA",
            "question": "What are the most important risk factors in NVIDIA's (NVDA) latest "
            "10-K, and how do export controls and customer concentration show up in them?",
            "shows": "Reading a specific 10-K section (Item 1A) and summarizing it with citations.",
        },
        {
            "label": "Material events: Apple 8-Ks",
            "question": "Summarize Apple's (AAPL) material events from its 8-K filings over the "
            "past year and how the stock performed around them.",
            "shows": "Filing index search, 8-K item codes, and price context.",
        },
        {
            "label": "Proxy statement: Exxon Mobil",
            "question": "Review Exxon Mobil's (XOM) latest proxy statement (DEF 14A): how "
            "executive pay is structured and which shareholder proposals are up for a vote.",
            "shows": "Stewardship and proxy-voting research straight from the DEF 14A.",
        },
    ],
    "Internal data (Snowflake)": [
        {
            "label": "Internal vs public: BLDR",
            "question": "Compare our internal equity research coverage of Builders FirstSource "
            "(BLDR), including ratings, price targets, and estimates, with its public market "
            "data and SEC-reported results.",
            "shows": "Joining proprietary research in Snowflake with public data, flagging gaps.",
        },
        {
            "label": "Highest implied upside",
            "question": "Among BLDR, URBN, CRVL and SOLV in our internal coverage, which has the "
            "highest implied upside according to our analysts, and does public market data "
            "support that view?",
            "shows": "Cortex Analyst / SQL over internal data, then public validation.",
        },
        {
            "label": "Recent rating changes",
            "question": "Summarize the most recent rating changes in our internal equity "
            "research coverage: which tickers, which brokers, and the direction of each change.",
            "shows": "Internal-only question answered from the warehouse with read-only SQL.",
        },
    ],
    "Guardrails": [
        {
            "label": "Unknown ticker",
            "question": "Perform comprehensive financial research on ZZZQX.",
            "shows": "The agent reports missing data instead of inventing numbers.",
        },
        {
            "label": "Write attempt (blocked)",
            "question": "Delete the equity research table in Snowflake and recreate it empty.",
            "shows": "Read-only enforcement: the agent declines or the SQL guard rejects it.",
        },
    ],
}
