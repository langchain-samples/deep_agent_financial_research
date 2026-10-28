"""Validation utilities for financial data and inputs."""

import re
from typing import Optional
from datetime import datetime


def validate_ticker(ticker: str) -> bool:
    """Validate a stock ticker symbol."""
    if not ticker or not isinstance(ticker, str):
        return False
    # Ticker should be 1-5 uppercase letters
    pattern = r'^[A-Z]{1,5}$'
    return bool(re.match(pattern, ticker.upper()))


def normalize_ticker(ticker: str) -> str:
    """Normalize ticker symbol to uppercase."""
    return ticker.upper().strip()


def validate_date(date_str: str) -> bool:
    """Validate a date string in YYYY-MM-DD format."""
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except (ValueError, TypeError):
        return False


def validate_period(period: str) -> bool:
    """Validate a time period string (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)."""
    valid_periods = ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"]
    return period.lower() in valid_periods


def validate_filing_type(filing_type: str) -> bool:
    """Validate SEC filing type."""
    valid_types = ["10-K", "10-Q", "8-K", "DEF 14A", "13F", "S-1", "S-3"]
    return filing_type.upper() in [ft.upper() for ft in valid_types]


def validate_output_format(format_str: str) -> bool:
    """Validate output format."""
    valid_formats = ["excel", "pdf", "markdown", "json"]
    return format_str.lower() in valid_formats
