"""LangGraph state schema definitions."""

from typing import TypedDict, List, Dict, Any, Optional
from langchain_core.messages import BaseMessage


class ResearchState(TypedDict):
    """State schema for the financial research workflow."""
    # Messages for conversation history
    messages: List[BaseMessage]
    
    # TODO list from planning
    todos: List[Dict[str, Any]]
    
    # Collected research data
    research_data: Dict[str, Any]
    
    # Analysis results
    analysis_results: Dict[str, Any]
    
    # Generated report
    report: Optional[Dict[str, Any]]
    
    # Execution tracking
    iteration_count: int
    replan_count: int
    
    # Budget tracking
    tokens_used: int
    cost_incurred: float
    time_elapsed: float
    
    # Current phase
    current_phase: str  # plan, collect, analyze, report, verify, complete
    
    # Error tracking
    errors: List[str]
    
    # User query
    user_query: str
    
    # Ticker being researched
    ticker: Optional[str]
