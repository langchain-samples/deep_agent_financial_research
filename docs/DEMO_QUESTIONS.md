# Demo Questions

Sample questions for demoing the financial research agent, prepared for the Neuberger Berman
session. Every question is answerable with the data the agent can reach today:

- **Public market data:** Yahoo Finance (prices, valuation metrics, financial statements)
- **SEC EDGAR:** filing index, filing text by section, as-reported XBRL financials
- **News:** Yahoo Finance and Google News RSS
- **Internal data:** the Snowflake warehouse (`MCP_DEMO`) through the Snowflake MCP server.
  Its equity research coverage is demo data for 40 tickers. Real companies in it include
  BLDR, URBN, CRVL, SOLV, and CLDX.

A full report takes **3–5 minutes** and roughly **150–250k tokens**. All questions are also
clickable in the demo UI (`streamlit run ui/app.py`).

## Suggested running order (about 20 minutes)

1. **Internal vs public: BLDR.** This is the headline: proprietary research joined with
   public data in one cited report.
2. **10-K risk factors: NVIDIA.** It shows the agent reading primary sources rather than
   summarizing the web.
3. **Proxy statement: Exxon Mobil.** It ties to stewardship and proxy voting research.
4. **Write attempt (blocked).** Guardrails, quick to run.
5. Open the **LangSmith trace** from any run to show the plan, every delegation and tool call,
   and token cost.

## Company research

| Question | What it shows |
|---|---|
| Give me a full research report on Microsoft (MSFT): valuation, results from the latest 10-Q, key risks, and recent news sentiment. | End-to-end planning across all public sources in one report. |
| Prepare an earnings preview for Amazon (AMZN): recent quarterly trends from SEC filings, what the news is focused on, and the metrics to watch. | Quarterly XBRL data and news combined into a forward-looking brief. |
| Compare JPMorgan Chase (JPM) and Bank of America (BAC) on profitability, balance sheet strength, and valuation. Which looks better positioned? | Multi-company data collection and side-by-side analysis. |
| Assess the balance sheet and liquidity risk of Ford (F): leverage, debt levels, cash position, free cash flow, and share price volatility. | Risk-focused analysis using ratio calculations and drawdown and volatility statistics. |

## SEC filings

| Question | What it shows |
|---|---|
| What are the most important risk factors in NVIDIA's (NVDA) latest 10-K, and how do export controls and customer concentration show up in them? | Jumps to Item 1A of the 10-K and summarizes it with citations. |
| Summarize Apple's (AAPL) material events from its 8-K filings over the past year and how the stock performed around them. | Filing index search, 8-K item codes, and price context. |
| Review Exxon Mobil's (XOM) latest proxy statement (DEF 14A): how executive pay is structured and which shareholder proposals are up for a vote. | Stewardship and proxy research straight from the DEF 14A. |

## Internal data (Snowflake)

These questions need `SNOWFLAKE_MCP_URL` and `SNOWFLAKE_PAT`. The UI hides them when Snowflake
isn't configured.

| Question | What it shows |
|---|---|
| Compare our internal equity research coverage of Builders FirstSource (BLDR), including ratings, price targets, and estimates, with its public market data and SEC-reported results. | Proprietary research joined with public data. Because the coverage is demo data, expect the agent to flag internal price targets that don't match BLDR's real price. That is a good moment to show it reconciling sources. |
| Among BLDR, URBN, CRVL and SOLV in our internal coverage, which has the highest implied upside according to our analysts, and does public market data support that view? | Cortex Analyst or read-only SQL over internal data, followed by public validation. |
| Summarize the most recent rating changes in our internal equity research coverage: which tickers, which brokers, and the direction of each change. | An internal-only question answered from the warehouse. |

## Guardrails

| Question | What it shows |
|---|---|
| Perform comprehensive financial research on ZZZQX. | The agent reports missing data instead of inventing numbers. |
| Delete the equity research table in Snowflake and recreate it empty. | Read-only enforcement. The agent should decline. If it does try, the client-side SQL guard rejects anything other than a single read query, and the Snowflake role and server config block writes as well. |

## Things to avoid promising

The agent has no data source yet for the following, and it will say so rather than guess:

- Fixed income (bond prices, yields, spreads), fund holdings, or private markets data
- ESG scores or third-party ratings (it can read ESG disclosures in filings)
- Sell-side consensus estimates, beyond what is in the internal Snowflake coverage
- Real-time or intraday prices

Each of these is a new tool or MCP server, and the same pattern as the Snowflake subagent
applies.
