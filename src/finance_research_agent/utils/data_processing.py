"""Data processing utilities for cleaning, normalizing, and transforming financial data."""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
from datetime import datetime


def clean_financial_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Clean and normalize financial data.
    
    Args:
        data: Raw financial data dictionary
    
    Returns:
        Cleaned financial data dictionary
    """
    cleaned = {}
    
    for key, value in data.items():
        if isinstance(value, dict):
            cleaned[key] = clean_financial_data(value)
        elif isinstance(value, (int, float)):
            # Replace NaN and inf values
            if pd.isna(value) or np.isinf(value):
                cleaned[key] = None
            else:
                cleaned[key] = value
        elif isinstance(value, str):
            # Clean string values
            cleaned[key] = value.strip() if value else None
        else:
            cleaned[key] = value
    
    return cleaned


def normalize_ticker_data(data: Dict[str, Any], ticker: str) -> Dict[str, Any]:
    """Normalize data structure to include ticker information.
    
    Args:
        data: Financial data dictionary
        ticker: Stock ticker symbol
    
    Returns:
        Normalized data with ticker information
    """
    normalized = {
        "ticker": ticker.upper(),
        "timestamp": datetime.now().isoformat(),
        "data": data,
    }
    return normalized


def validate_data_completeness(data: Dict[str, Any], required_fields: List[str]) -> Dict[str, Any]:
    """Validate that required fields are present in data.
    
    Args:
        data: Data dictionary to validate
        required_fields: List of required field names
    
    Returns:
        Dictionary with validation results
    """
    missing_fields = []
    present_fields = []
    
    for field in required_fields:
        if field not in data or data[field] is None:
            missing_fields.append(field)
        else:
            present_fields.append(field)
    
    return {
        "is_complete": len(missing_fields) == 0,
        "missing_fields": missing_fields,
        "present_fields": present_fields,
        "completeness_percentage": (len(present_fields) / len(required_fields) * 100) if required_fields else 100,
    }


def aggregate_data_sources(data_sources: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate data from multiple sources into a single structure.
    
    Args:
        data_sources: List of data dictionaries from different sources
    
    Returns:
        Aggregated data dictionary
    """
    aggregated = {}
    
    for source_data in data_sources:
        if isinstance(source_data, dict):
            for key, value in source_data.items():
                if key not in aggregated:
                    aggregated[key] = value
                elif isinstance(aggregated[key], dict) and isinstance(value, dict):
                    # Merge dictionaries
                    aggregated[key] = {**aggregated[key], **value}
                elif isinstance(aggregated[key], list) and isinstance(value, list):
                    # Combine lists
                    aggregated[key] = aggregated[key] + value
    
    return aggregated


def transform_to_dataframe(data: Dict[str, Any], key: str) -> Optional[pd.DataFrame]:
    """Transform nested dictionary data into a pandas DataFrame.
    
    Args:
        data: Data dictionary
        key: Key to extract from data
    
    Returns:
        DataFrame if transformation successful, None otherwise
    """
    try:
        if key in data and isinstance(data[key], dict):
            df = pd.DataFrame(data[key]).T
            return df
    except Exception:
        pass
    
    return None
