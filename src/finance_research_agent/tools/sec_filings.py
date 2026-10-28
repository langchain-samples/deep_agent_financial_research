"""Tools for fetching SEC filings and reported financials from SEC EDGAR.

Uses EDGAR's free public JSON APIs (no API key). SEC's fair-access policy requires a
User-Agent identifying the requester (SEC_USER_AGENT) and at most 10 requests/second.
"""

import re
import threading
import time
from datetime import date
from functools import lru_cache
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup
from langchain.tools import tool

from ..config import DataSourceConfig
from ..utils.validators import normalize_ticker, validate_date, validate_filing_type, validate_ticker

TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
ARCHIVES_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{document}"

MIN_REQUEST_INTERVAL = 0.15  # seconds; keeps us under SEC's 10 requests/second
MAX_RESPONSE_BYTES = 20 * 1024 * 1024
MAX_FILING_CHARS = 50_000
MAX_FILINGS = 40

_ACCESSION_RE = re.compile(r"^[0-9-]+$")
_DOCUMENT_RE = re.compile(r"^[\w.-]+$")
_HEADING_RE = re.compile(r"^item\s+(\d{1,2}[a-c]?)\b[.:\s\u2014\u2013-]*(.*)$", re.IGNORECASE | re.MULTILINE)

_throttle_lock = threading.Lock()
_last_request_time = 0.0

# XBRL concepts for each reported metric, in order of preference. Companies switch
# concepts over time, so the candidate with the most recent data wins.
FINANCIAL_CONCEPTS = {
    "revenue": ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet"],
    "net_income": ["NetIncomeLoss"],
    "operating_income": ["OperatingIncomeLoss"],
    "eps_diluted": ["EarningsPerShareDiluted"],
    "operating_cash_flow": ["NetCashProvidedByUsedInOperatingActivities"],
    "total_assets": ["Assets"],
    "total_liabilities": ["Liabilities"],
    "stockholders_equity": ["StockholdersEquity"],
    "cash_and_equivalents": ["CashAndCashEquivalentsAtCarryingValue"],
    "long_term_debt": ["LongTermDebtNoncurrent", "LongTermDebt"],
}


class SECError(Exception):
    """Raised for SEC configuration or request failures with a user-facing message."""


def _sec_get(url: str) -> requests.Response:
    """GET an SEC URL with the required User-Agent, throttling, and a size cap."""
    global _last_request_time

    user_agent = DataSourceConfig.from_env().sec_user_agent
    if not user_agent:
        raise SECError(
            "SEC_USER_AGENT is not set. SEC requires a User-Agent identifying you, "
            "e.g. SEC_USER_AGENT='Acme Research jane@acme.com'."
        )

    with _throttle_lock:
        wait = MIN_REQUEST_INTERVAL - (time.monotonic() - _last_request_time)
        if wait > 0:
            time.sleep(wait)
        _last_request_time = time.monotonic()

    response = requests.get(
        url,
        headers={"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"},
        timeout=20,
        stream=True,
    )
    response.raise_for_status()

    chunks, size = [], 0
    for chunk in response.iter_content(chunk_size=65536):
        size += len(chunk)
        if size > MAX_RESPONSE_BYTES:
            response.close()
            raise SECError(f"SEC response exceeded {MAX_RESPONSE_BYTES // (1024 * 1024)}MB")
        chunks.append(chunk)
    response._content = b"".join(chunks)
    return response


@lru_cache(maxsize=1)
def _ticker_map() -> Dict[str, Dict[str, Any]]:
    """Map ticker -> {"cik": int, "name": str} from SEC's company ticker file."""
    data = _sec_get(TICKER_MAP_URL).json()
    return {
        entry["ticker"].upper(): {"cik": int(entry["cik_str"]), "name": entry["title"]}
        for entry in data.values()
    }


def _lookup_company(ticker: str) -> Dict[str, Any]:
    company = _ticker_map().get(ticker)
    if not company:
        raise SECError(f"Ticker {ticker} not found in SEC EDGAR")
    return company


@lru_cache(maxsize=64)
def _submissions(cik: int) -> Dict[str, Any]:
    return _sec_get(SUBMISSIONS_URL.format(cik=cik)).json()


def _filing_url(cik: int, accession: str, document: str) -> Optional[str]:
    """Build an EDGAR archive URL, validating parts that come from SEC JSON."""
    if not _ACCESSION_RE.match(accession) or not _DOCUMENT_RE.match(document):
        return None
    return ARCHIVES_URL.format(cik=cik, accession=accession.replace("-", ""), document=document)


def recent_filings(submissions: Dict[str, Any], cik: int, filing_type: Optional[str]) -> List[Dict[str, Any]]:
    """Flatten EDGAR's columnar recent-filings data, newest first, optionally filtered by form."""
    recent = submissions.get("filings", {}).get("recent", {})
    filings = []
    for i, form in enumerate(recent.get("form", [])):
        if filing_type and form.upper() != filing_type.upper():
            continue
        accession = recent["accessionNumber"][i]
        document = recent["primaryDocument"][i]
        filing = {
            "form": form,
            "filing_date": recent["filingDate"][i],
            "report_date": recent["reportDate"][i] or None,
            "accession_number": accession,
            "url": _filing_url(cik, accession, document),
        }
        if recent.get("items") and recent["items"][i]:
            filing["items"] = recent["items"][i]  # 8-K item numbers, e.g. "2.02,9.01"
        filings.append(filing)
    return filings


def html_to_text(html: bytes) -> str:
    """Convert filing HTML to readable plain text."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "ix:header"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    lines = (re.sub(r"[ \t\xa0]+", " ", line).strip() for line in text.splitlines())
    return "\n".join(line for line in lines if line)


def _item_headings(text: str) -> List[tuple]:
    """Find "Item N" heading lines as (offset, item number).

    A heading starts a line and is followed by a short title (on the same or next line).
    This excludes cross-references like "Item 1A of this Form 10-K under the heading...",
    which html_to_text can leave at the start of a line.
    """
    headings = []
    for match in _HEADING_RE.finditer(text):
        title = match.group(2).strip()
        if not title:
            next_line_end = text.find("\n", match.end() + 1)
            title = text[match.end() + 1 : next_line_end if next_line_end != -1 else None].strip()
        if title and len(title) <= 120 and not title[0].islower():
            headings.append((match.start(), match.group(1).upper()))
    return headings


def find_section(text: str, section: str) -> Optional[int]:
    """Return the start offset of a 10-K/10-Q section such as "1A" or "Item 7".

    Headings appear first in the table of contents, where the next heading follows
    closely. The real section is the occurrence with the most text before the next
    "Item N" heading.
    """
    headings = _item_headings(text)
    item = re.sub(r"(?i)^item\s*", "", section.strip()).rstrip(".").upper()
    if re.fullmatch(r"\d{1,2}[A-C]?", item):
        starts = [offset for offset, number in headings if number == item]
    else:
        item = None
        starts = [m.start() for m in re.finditer(re.escape(section.strip()), text, re.IGNORECASE)]

    best_start, best_length = None, -1
    for start in starts:
        # Some filings repeat "Item N" as a running page header, so the section ends at
        # the next heading for a different item. Ties keep the earliest occurrence.
        next_heading = next((h for h, n in headings if h > start and n != item), len(text))
        if next_heading - start > best_length:
            best_start, best_length = start, next_heading - start
    return best_start


def _duration_days(fact: Dict[str, Any]) -> Optional[int]:
    if "start" not in fact:
        return None
    return (date.fromisoformat(fact["end"]) - date.fromisoformat(fact["start"])).days


def _latest_fact(facts: List[Dict[str, Any]], annual: bool) -> Optional[Dict[str, Any]]:
    """Pick the most recent annual or interim fact, preferring the latest filing for a period.

    Annual: 10-K facts spanning ~1 year (or point-in-time balance sheet values).
    Interim: the most recent 10-Q period. For a given period end the shortest span wins,
    so a 3-month figure beats year-to-date; items reported only year-to-date (often cash
    flow) come back with their longer span, visible in duration_days.
    """
    def matches(fact: Dict[str, Any]) -> bool:
        days = _duration_days(fact)
        if annual:
            return fact.get("form") == "10-K" and (days is None or 330 <= days <= 400)
        return fact.get("form") == "10-Q" and (days is None or 80 <= days <= 280)

    candidates = [f for f in facts if matches(f)]
    if not candidates:
        return None
    best = max(
        candidates,
        key=lambda f: (f["end"], -(_duration_days(f) or 0), f.get("filed", "")),
    )
    return {
        "value": best["val"],
        "period_start": best.get("start"),
        "period_end": best["end"],
        "duration_days": _duration_days(best),
        "fiscal_year": best.get("fy"),
        "fiscal_period": best.get("fp"),
        "form": best.get("form"),
        "filed": best.get("filed"),
        "accession_number": best.get("accn"),
    }


def extract_financials(company_facts: Dict[str, Any]) -> Dict[str, Any]:
    """Extract the latest annual and quarterly values for each metric in FINANCIAL_CONCEPTS."""
    us_gaap = company_facts.get("facts", {}).get("us-gaap", {})
    metrics: Dict[str, Any] = {}
    for metric, concepts in FINANCIAL_CONCEPTS.items():
        best = None
        for concept in concepts:
            units = us_gaap.get(concept, {}).get("units", {})
            unit, facts = next(iter(units.items()), (None, []))
            if not facts:
                continue
            annual, quarter = _latest_fact(facts, annual=True), _latest_fact(facts, annual=False)
            latest_end = max((x["period_end"] for x in (annual, quarter) if x), default="")
            if best is None or latest_end > best["_latest_end"]:
                best = {
                    "concept": concept,
                    "unit": unit,
                    "annual": annual,
                    "latest_quarter": quarter,
                    "_latest_end": latest_end,
                }
        if best:
            best.pop("_latest_end")
            metrics[metric] = best
    return metrics


@tool
def search_sec_filings(ticker: str, filing_type: Optional[str] = None, limit: int = 10) -> Dict[str, Any]:
    """Search SEC EDGAR for a company's recent filings.

    Args:
        ticker: Stock ticker symbol
        filing_type: Type of filing (10-K, 10-Q, 8-K, DEF 14A, etc.) - optional
        limit: Maximum number of filings to return (default: 10, max: 40)

    Returns:
        Dictionary with company info and filings (form, dates, accession number, URL)
    """
    ticker = normalize_ticker(ticker)
    if not validate_ticker(ticker):
        return {"error": f"Invalid ticker symbol: {ticker}"}
    if filing_type and not validate_filing_type(filing_type):
        return {"error": f"Invalid filing type: {filing_type}"}

    limit = max(1, min(limit, MAX_FILINGS))

    try:
        company = _lookup_company(ticker)
        filings = recent_filings(_submissions(company["cik"]), company["cik"], filing_type)[:limit]
        return {
            "ticker": ticker,
            "cik": company["cik"],
            "company_name": company["name"],
            "filing_type": filing_type,
            "num_filings": len(filings),
            "filings": filings,
            "source": "SEC EDGAR",
        }
    except SECError as e:
        return {"error": str(e), "ticker": ticker}
    except Exception as e:
        return {"error": f"Failed to search SEC filings for {ticker}: {str(e)}"}


@tool
def get_filing_content(
    ticker: str,
    filing_type: str,
    date: Optional[str] = None,
    section: Optional[str] = None,
    max_chars: int = 15000,
) -> Dict[str, Any]:
    """Retrieve the text of an SEC filing, optionally starting at a specific section.

    Args:
        ticker: Stock ticker symbol
        filing_type: Type of filing (10-K, 10-Q, 8-K, etc.)
        date: Filing or report date in YYYY-MM-DD format (optional, most recent if omitted)
        section: Section to jump to, e.g. "1A" (Risk Factors), "7" (MD&A), "Item 2", or a
            heading phrase (optional, starts at the beginning if omitted)
        max_chars: Maximum characters of text to return (default: 15000, max: 50000)

    Returns:
        Dictionary containing filing metadata and text
    """
    ticker = normalize_ticker(ticker)
    if not validate_ticker(ticker):
        return {"error": f"Invalid ticker symbol: {ticker}"}
    if not validate_filing_type(filing_type):
        return {"error": f"Invalid filing type: {filing_type}"}
    if date and not validate_date(date):
        return {"error": f"Invalid date (expected YYYY-MM-DD): {date}"}
    max_chars = max(1000, min(max_chars, MAX_FILING_CHARS))

    try:
        company = _lookup_company(ticker)
        filings = recent_filings(_submissions(company["cik"]), company["cik"], filing_type)
        if date:
            filings = [f for f in filings if date in (f["filing_date"], f["report_date"])]
        filing = next((f for f in filings if f["url"]), None)
        if not filing:
            return {"error": f"No {filing_type} filing found for {ticker}" + (f" on {date}" if date else "")}

        text = html_to_text(_sec_get(filing["url"]).content)
        start = 0
        section_found = None
        if section:
            offset = find_section(text, section)
            section_found = offset is not None
            start = offset or 0

        excerpt = text[start : start + max_chars]
        return {
            "ticker": ticker,
            "company_name": company["name"],
            **filing,
            "section": section,
            "section_found": section_found,
            "total_chars": len(text),
            "start_offset": start,
            "truncated": start + max_chars < len(text),
            "content": excerpt,
            "source": "SEC EDGAR",
        }
    except SECError as e:
        return {"error": str(e), "ticker": ticker}
    except Exception as e:
        return {"error": f"Failed to get filing content for {ticker}: {str(e)}"}


@tool
def get_reported_financials(ticker: str) -> Dict[str, Any]:
    """Get financial figures as reported to the SEC (XBRL) from the latest 10-K and 10-Q.

    Covers revenue, net income, operating income, diluted EPS, operating cash flow, total
    assets, total liabilities, stockholders' equity, cash, and long-term debt. Each metric
    includes its period, fiscal year, form, and accession number for citation.

    Args:
        ticker: Stock ticker symbol

    Returns:
        Dictionary of metrics with latest annual and quarterly values
    """
    ticker = normalize_ticker(ticker)
    if not validate_ticker(ticker):
        return {"error": f"Invalid ticker symbol: {ticker}"}

    try:
        company = _lookup_company(ticker)
        facts = _sec_get(COMPANY_FACTS_URL.format(cik=company["cik"])).json()
        metrics = extract_financials(facts)
        if not metrics:
            return {"error": f"No XBRL financial data available for {ticker}", "ticker": ticker}
        return {
            "ticker": ticker,
            "cik": company["cik"],
            "company_name": company["name"],
            "metrics": metrics,
            "source": "SEC EDGAR XBRL company facts",
        }
    except SECError as e:
        return {"error": str(e), "ticker": ticker}
    except Exception as e:
        return {"error": f"Failed to get reported financials for {ticker}: {str(e)}"}


# Export all tools
SEC_FILINGS_TOOLS = [
    search_sec_filings,
    get_filing_content,
    get_reported_financials,
]
