"""Formatting utilities for reports, citations, and credibility scoring."""

from typing import Dict, Any, List, Optional
from datetime import datetime


def format_citation(source: str, url: Optional[str] = None, date: Optional[str] = None) -> str:
    """Format a citation for a data source.
    
    Args:
        source: Source name
        url: Optional URL
        date: Optional date
    
    Returns:
        Formatted citation string
    """
    citation = source
    if date:
        citation += f" ({date})"
    if url:
        citation += f" - {url}"
    return citation


def calculate_credibility_score(source: str, data_quality: Dict[str, Any]) -> float:
    """Calculate credibility score for a data source.
    
    Args:
        source: Source name
        data_quality: Dictionary containing data quality metrics
    
    Returns:
        Credibility score (0-100)
    """
    score = 50.0  # Base score
    
    # Known reliable sources get higher base scores
    reliable_sources = ["yahoo_finance", "sec_edgar", "alpha_vantage", "sec.gov"]
    if any(rs in source.lower() for rs in reliable_sources):
        score += 20.0
    
    # Adjust based on data quality
    completeness = data_quality.get("completeness_percentage", 0)
    score += (completeness / 100) * 20.0
    
    # Check for data validation
    if data_quality.get("is_valid", False):
        score += 10.0
    
    return min(100.0, max(0.0, score))


def format_currency(value: Optional[float], currency: str = "USD") -> str:
    """Format a currency value.
    
    Args:
        value: Numeric value
        currency: Currency code
    
    Returns:
        Formatted currency string
    """
    if value is None:
        return "N/A"
    
    if abs(value) >= 1e9:
        return f"${value/1e9:.2f}B {currency}"
    elif abs(value) >= 1e6:
        return f"${value/1e6:.2f}M {currency}"
    elif abs(value) >= 1e3:
        return f"${value/1e3:.2f}K {currency}"
    else:
        return f"${value:.2f} {currency}"


def format_percentage(value: Optional[float], decimals: int = 2) -> str:
    """Format a percentage value.
    
    Args:
        value: Numeric value (as decimal, e.g., 0.15 for 15%)
        decimals: Number of decimal places
    
    Returns:
        Formatted percentage string
    """
    if value is None:
        return "N/A"
    
    return f"{value * 100:.{decimals}f}%"


def format_number(value: Optional[float], decimals: int = 2) -> str:
    """Format a number with appropriate precision.
    
    Args:
        value: Numeric value
        decimals: Number of decimal places
    
    Returns:
        Formatted number string
    """
    if value is None:
        return "N/A"
    
    if abs(value) >= 1e9:
        return f"{value/1e9:.{decimals}f}B"
    elif abs(value) >= 1e6:
        return f"{value/1e6:.{decimals}f}M"
    elif abs(value) >= 1e3:
        return f"{value/1e3:.{decimals}f}K"
    else:
        return f"{value:.{decimals}f}"


def create_report_metadata(ticker: str, report_type: str = "comprehensive") -> Dict[str, Any]:
    """Create metadata for a research report.
    
    Args:
        ticker: Stock ticker symbol
        report_type: Type of report
    
    Returns:
        Metadata dictionary
    """
    return {
        "ticker": ticker.upper(),
        "report_type": report_type,
        "generated_at": datetime.now().isoformat(),
        "version": "1.0",
    }
