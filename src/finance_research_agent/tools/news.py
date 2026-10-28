"""Tools for fetching financial news and analyzing sentiment.

News comes from public RSS feeds (Yahoo Finance per-ticker headlines and Google News
search), so no API key is needed. If NEWS_API_KEY is set, NewsAPI is used instead.
"""

from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from defusedxml import ElementTree
from langchain.tools import tool
from ..utils.validators import validate_ticker, normalize_ticker
from ..config import DataSourceConfig

YAHOO_RSS_URL = "https://feeds.finance.yahoo.com/rss/2.0/headline"
GOOGLE_NEWS_RSS_URL = "https://news.google.com/rss/search"
NEWSAPI_URL = "https://newsapi.org/v2/everything"
RSS_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; finance-research-agent/0.1)"}
MAX_FEED_BYTES = 5 * 1024 * 1024
MAX_ARTICLES = 20


def _get_news_api_key() -> Optional[str]:
    """Get News API key from config."""
    config = DataSourceConfig.from_env()
    return config.news_api_key


def parse_rss(xml: bytes, days: int) -> List[Dict[str, Any]]:
    """Parse RSS items published within the last ``days`` days, newest first."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    articles = []
    for item in ElementTree.fromstring(xml).iter("item"):
        published = None
        pub_date = item.findtext("pubDate")
        if pub_date:
            try:
                published = parsedate_to_datetime(pub_date)
            except (TypeError, ValueError):
                pass
        if published and published < cutoff:
            continue
        description = item.findtext("description") or ""
        url = item.findtext("link") or "N/A"
        articles.append({
            "title": (item.findtext("title") or "N/A").strip(),
            "description": BeautifulSoup(description, "html.parser").get_text(" ", strip=True)[:500],
            # Yahoo items have no <source>; fall back to the article's domain
            "source": item.findtext("source") or urlparse(url).hostname or "N/A",
            "url": url,
            "published_at": published.isoformat() if published else "N/A",
        })
    articles.sort(key=lambda a: a["published_at"], reverse=True)
    return articles[:MAX_ARTICLES]


def _fetch_rss(url: str, params: Dict[str, str], days: int) -> List[Dict[str, Any]]:
    response = requests.get(url, params=params, headers=RSS_HEADERS, timeout=10, stream=True)
    response.raise_for_status()
    content = response.raw.read(MAX_FEED_BYTES + 1, decode_content=True)
    if len(content) > MAX_FEED_BYTES:
        raise ValueError("RSS feed exceeded size limit")
    return parse_rss(content, days)


def fetch_ticker_news(ticker: str, days: int = 7) -> List[Dict[str, Any]]:
    """Recent headlines for a ticker from Yahoo Finance RSS."""
    return _fetch_rss(YAHOO_RSS_URL, {"s": ticker, "region": "US", "lang": "en-US"}, days)


def search_news_rss(query: str, days: int = 7) -> List[Dict[str, Any]]:
    """Search Google News RSS for articles from the last ``days`` days."""
    params = {"q": f"{query} when:{days}d", "hl": "en-US", "gl": "US", "ceid": "US:en"}
    return _fetch_rss(GOOGLE_NEWS_RSS_URL, params, days)


def merge_articles(*feeds: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Combine article lists, dropping duplicate titles, newest first."""
    seen, merged = set(), []
    for article in (a for feed in feeds for a in feed):
        key = article["title"].lower().split(" - ")[0].strip()
        if key not in seen:
            seen.add(key)
            merged.append(article)
    merged.sort(key=lambda a: a["published_at"], reverse=True)
    return merged[:MAX_ARTICLES]


def _search_newsapi(api_key: str, query: str, days: int) -> Optional[List[Dict[str, Any]]]:
    params = {
        "q": query,
        "language": "en",
        "sortBy": "publishedAt",
        "from": (datetime.now() - timedelta(days=days)).isoformat(),
        "apiKey": api_key,
    }
    response = requests.get(NEWSAPI_URL, params=params, timeout=10)
    if response.status_code != 200:
        return None
    return [
        {
            "title": article.get("title", "N/A"),
            "description": article.get("description", "N/A"),
            "source": article.get("source", {}).get("name", "N/A"),
            "url": article.get("url", "N/A"),
            "published_at": article.get("publishedAt", "N/A"),
        }
        for article in response.json().get("articles", [])[:MAX_ARTICLES]
    ]


@tool
def search_financial_news(ticker: str, query: Optional[str] = None, days: int = 7) -> Dict[str, Any]:
    """Search for financial news articles related to a ticker.

    Args:
        ticker: Stock ticker symbol
        query: Optional search terms to narrow results (e.g. "earnings", "antitrust")
        days: Number of days to look back (default: 7, max: 30)

    Returns:
        Dictionary containing news articles
    """
    ticker = normalize_ticker(ticker)
    if not validate_ticker(ticker):
        return {"error": f"Invalid ticker symbol: {ticker}"}
    days = max(1, min(days, 30))

    try:
        api_key = _get_news_api_key()
        articles = _search_newsapi(api_key, f"{ticker} {query or ''}".strip(), days) if api_key else None
        source = "NewsAPI"

        if articles is None:
            if query:
                articles, source = search_news_rss(f"{ticker} {query}", days), "Google News RSS"
            else:
                # Yahoo's feed only holds its latest ~20 items (often a single day), so
                # combine it with Google News to cover the whole window.
                articles = merge_articles(
                    fetch_ticker_news(ticker, days), search_news_rss(f"{ticker} stock", days)
                )
                source = "Yahoo Finance RSS + Google News RSS"

        return {
            "ticker": ticker,
            "query": query,
            "days": days,
            "num_articles": len(articles),
            "articles": articles,
            "source": source,
        }
    except Exception as e:
        return {"error": f"Failed to search news for {ticker}: {str(e)}"}


@tool
def get_news_sentiment(articles: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze sentiment of news articles.
    
    Args:
        articles: List of article dictionaries with 'title' and optionally 'description' fields
    
    Returns:
        Dictionary containing sentiment analysis results
    """
    try:
        if not articles:
            return {"error": "No articles provided for sentiment analysis"}
        
        # Simple sentiment analysis based on keywords
        # In production, you'd use a proper NLP sentiment analysis model
        positive_keywords = ["growth", "profit", "gain", "up", "rise", "increase", "positive", "strong", "beat", "exceed"]
        negative_keywords = ["loss", "decline", "down", "fall", "decrease", "negative", "weak", "miss", "below", "drop"]
        
        sentiments = []
        positive_count = 0
        negative_count = 0
        neutral_count = 0
        
        for article in articles:
            text = f"{article.get('title', '')} {article.get('description', '')}".lower()
            
            positive_score = sum(1 for keyword in positive_keywords if keyword in text)
            negative_score = sum(1 for keyword in negative_keywords if keyword in text)
            
            if positive_score > negative_score:
                sentiment = "positive"
                positive_count += 1
            elif negative_score > positive_score:
                sentiment = "negative"
                negative_count += 1
            else:
                sentiment = "neutral"
                neutral_count += 1
            
            sentiments.append({
                "title": article.get("title", "N/A"),
                "sentiment": sentiment,
                "positive_score": positive_score,
                "negative_score": negative_score,
            })
        
        total = len(articles)
        return {
            "total_articles": total,
            "positive": positive_count,
            "negative": negative_count,
            "neutral": neutral_count,
            "positive_pct": (positive_count / total * 100) if total > 0 else 0,
            "negative_pct": (negative_count / total * 100) if total > 0 else 0,
            "neutral_pct": (neutral_count / total * 100) if total > 0 else 0,
            "overall_sentiment": "positive" if positive_count > negative_count else ("negative" if negative_count > positive_count else "neutral"),
            "article_sentiments": sentiments,
        }
    except Exception as e:
        return {"error": f"Failed to analyze sentiment: {str(e)}"}


@tool
def get_market_news(date_range: Optional[str] = None) -> Dict[str, Any]:
    """Get general stock market and economy news.

    Args:
        date_range: Date range in days (e.g., "7" for last 7 days) - optional

    Returns:
        Dictionary containing market news articles
    """
    try:
        days = max(1, min(int(date_range) if date_range else 7, 30))
        query = "stock market OR financial markets OR economy"

        api_key = _get_news_api_key()
        articles = _search_newsapi(api_key, query, days) if api_key else None
        source = "NewsAPI"
        if articles is None:
            articles, source = search_news_rss(query, days), "Google News RSS"

        return {
            "date_range_days": days,
            "num_articles": len(articles),
            "articles": articles,
            "source": source,
        }
    except Exception as e:
        return {"error": f"Failed to get market news: {str(e)}"}


# Export all tools
NEWS_TOOLS = [
    search_financial_news,
    get_news_sentiment,
    get_market_news,
]
