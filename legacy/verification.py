"""Verification functions for research completeness and quality."""

from typing import Dict, Any, List
from .graph.state import ResearchState
from .config import AgentConfig, BudgetConfig


def check_research_completeness(state: ResearchState) -> Dict[str, Any]:
    """Check if research is complete based on todos and collected data.
    
    Args:
        state: Current research state
    
    Returns:
        Dictionary with completeness assessment
    """
    todos = state.get("todos", [])
    research_data = state.get("research_data", {})
    analysis_results = state.get("analysis_results", {})
    report = state.get("report")
    
    # Check if all todos are completed
    completed_todos = [todo for todo in todos if todo.get("status") == "completed"]
    total_todos = len(todos)
    completion_rate = (len(completed_todos) / total_todos * 100) if total_todos > 0 else 0
    
    # Check data completeness
    required_data_keys = ["stock_info", "financial_statements", "sec_filings", "news"]
    present_data_keys = [key for key in required_data_keys if key in research_data and research_data[key]]
    data_completeness = (len(present_data_keys) / len(required_data_keys) * 100) if required_data_keys else 0
    
    # Check analysis completeness
    required_analysis_keys = ["ratios", "risk_assessment", "trends"]
    present_analysis_keys = [key for key in required_analysis_keys if key in analysis_results and analysis_results[key]]
    analysis_completeness = (len(present_analysis_keys) / len(required_analysis_keys) * 100) if required_analysis_keys else 0
    
    # Check if report exists
    has_report = report is not None
    
    # Overall completeness
    overall_completeness = (
        completion_rate * 0.3 +
        data_completeness * 0.3 +
        analysis_completeness * 0.3 +
        (100 if has_report else 0) * 0.1
    )
    
    is_complete = (
        completion_rate >= 80 and
        data_completeness >= 75 and
        analysis_completeness >= 75 and
        has_report
    )
    
    return {
        "is_complete": is_complete,
        "overall_completeness": overall_completeness,
        "todo_completion_rate": completion_rate,
        "data_completeness": data_completeness,
        "analysis_completeness": analysis_completeness,
        "has_report": has_report,
        "missing_components": {
            "todos": [todo for todo in todos if todo.get("status") != "completed"],
            "data": [key for key in required_data_keys if key not in research_data or not research_data[key]],
            "analysis": [key for key in required_analysis_keys if key not in analysis_results or not analysis_results[key]],
        },
    }


def validate_data_quality(state: ResearchState) -> Dict[str, Any]:
    """Validate the quality of collected data.
    
    Args:
        state: Current research state
    
    Returns:
        Dictionary with data quality assessment
    """
    research_data = state.get("research_data", {})
    errors = state.get("errors", [])
    
    quality_issues = []
    quality_score = 100.0
    
    # Check for errors
    if errors:
        quality_issues.append(f"Found {len(errors)} errors during execution")
        quality_score -= len(errors) * 5
    
    # Check data structure
    if not isinstance(research_data, dict):
        quality_issues.append("Research data is not properly structured")
        quality_score -= 20
    
    # Check for empty data
    empty_keys = [key for key, value in research_data.items() if not value]
    if empty_keys:
        quality_issues.append(f"Empty data in keys: {', '.join(empty_keys)}")
        quality_score -= len(empty_keys) * 5
    
    # Check stock info
    stock_info = research_data.get("stock_info", {})
    if stock_info:
        required_stock_fields = ["ticker", "name", "current_price"]
        missing_stock_fields = [field for field in required_stock_fields if field not in stock_info]
        if missing_stock_fields:
            quality_issues.append(f"Missing stock info fields: {', '.join(missing_stock_fields)}")
            quality_score -= len(missing_stock_fields) * 3
    
    quality_score = max(0.0, min(100.0, quality_score))
    
    return {
        "quality_score": quality_score,
        "quality_level": "high" if quality_score >= 80 else ("medium" if quality_score >= 60 else "low"),
        "quality_issues": quality_issues,
        "is_acceptable": quality_score >= 60,
    }


def assess_report_quality(state: ResearchState) -> Dict[str, Any]:
    """Assess the quality of the generated report.
    
    Args:
        state: Current research state
    
    Returns:
        Dictionary with report quality assessment
    """
    report = state.get("report")
    
    if not report:
        return {
            "has_report": False,
            "quality_score": 0.0,
            "quality_level": "none",
            "is_acceptable": False,
            "missing_components": ["report"],
        }
    
    quality_score = 50.0  # Base score
    missing_components = []
    
    # Check for required sections
    required_sections = ["metadata", "stock_info", "analysis"]
    for section in required_sections:
        if section in report and report[section]:
            quality_score += 15
        else:
            missing_components.append(section)
            quality_score -= 10
    
    # Check metadata
    metadata = report.get("metadata", {})
    if "ticker" in metadata:
        quality_score += 5
    if "generated_at" in metadata:
        quality_score += 5
    
    # Check analysis depth
    analysis = report.get("analysis", {})
    if isinstance(analysis, dict) and len(analysis) > 0:
        quality_score += 10
    
    quality_score = max(0.0, min(100.0, quality_score))
    
    return {
        "has_report": True,
        "quality_score": quality_score,
        "quality_level": "high" if quality_score >= 80 else ("medium" if quality_score >= 60 else "low"),
        "is_acceptable": quality_score >= 60,
        "missing_components": missing_components,
    }


def should_replan(state: ResearchState, config: AgentConfig) -> Dict[str, Any]:
    """Determine if replanning is needed.
    
    Args:
        state: Current research state
        config: Agent configuration
    
    Returns:
        Dictionary with replanning decision
    """
    # Check completeness
    completeness = check_research_completeness(state)
    
    # Check data quality
    data_quality = validate_data_quality(state)
    
    # Check report quality
    report_quality = assess_report_quality(state)
    
    # Check budget limits
    budget = config.budget
    tokens_used = state.get("tokens_used", 0)
    cost_incurred = state.get("cost_incurred", 0.0)
    
    budget_exceeded = (
        tokens_used >= budget.max_tokens or
        cost_incurred >= budget.max_cost
    )
    
    # Check iteration limits
    execution = config.execution
    iteration_count = state.get("iteration_count", 0)
    replan_count = state.get("replan_count", 0)
    
    iteration_limit_reached = iteration_count >= execution.max_iterations
    replan_limit_reached = replan_count >= execution.max_replans
    
    # Decision logic
    should_replan_flag = (
        not completeness["is_complete"] and
        not budget_exceeded and
        not iteration_limit_reached and
        not replan_limit_reached
    )
    
    force_completion = (
        budget_exceeded or
        iteration_limit_reached or
        replan_limit_reached
    )
    
    return {
        "should_replan": should_replan_flag,
        "force_completion": force_completion,
        "reason": (
            "budget_exceeded" if budget_exceeded else
            "iteration_limit" if iteration_limit_reached else
            "replan_limit" if replan_limit_reached else
            "incomplete_research" if not completeness["is_complete"] else
            "complete"
        ),
        "completeness": completeness,
        "data_quality": data_quality,
        "report_quality": report_quality,
        "budget_status": {
            "tokens_used": tokens_used,
            "tokens_limit": budget.max_tokens,
            "cost_incurred": cost_incurred,
            "cost_limit": budget.max_cost,
            "budget_exceeded": budget_exceeded,
        },
        "iteration_status": {
            "iteration_count": iteration_count,
            "iteration_limit": execution.max_iterations,
            "replan_count": replan_count,
            "replan_limit": execution.max_replans,
        },
    }
