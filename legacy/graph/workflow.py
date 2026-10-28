"""LangGraph workflow for financial research agent."""

from typing import Literal, Optional
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from .state import ResearchState
from ..agent import create_main_agent
from ..config import AgentConfig


def create_research_workflow(config: Optional[AgentConfig] = None) -> StateGraph:
    """Create the LangGraph workflow for financial research.
    
    Args:
        config: Agent configuration (optional)
    
    Returns:
        Configured StateGraph workflow
    """
    if config is None:
        config = AgentConfig.from_env()
    
    # Create the main agent
    agent = create_main_agent(config)
    
    # Create the workflow graph
    workflow = StateGraph(ResearchState)
    
    # Define nodes
    def plan_research(state: ResearchState) -> ResearchState:
        """Plan the research task."""
        user_query = state.get("user_query", "")
        ticker = state.get("ticker", "")
        
        # Use the agent to create a plan
        # In a real implementation, this would invoke the agent's planning capabilities
        todos = [
            {"task": "Collect stock data", "status": "pending"},
            {"task": "Collect financial statements", "status": "pending"},
            {"task": "Collect SEC filings", "status": "pending"},
            {"task": "Collect news articles", "status": "pending"},
            {"task": "Perform financial analysis", "status": "pending"},
            {"task": "Assess risk profile", "status": "pending"},
            {"task": "Generate research report", "status": "pending"},
        ]
        
        return {
            **state,
            "todos": todos,
            "current_phase": "collect",
            "iteration_count": state.get("iteration_count", 0) + 1,
        }
    
    def collect_data(state: ResearchState) -> ResearchState:
        """Collect financial data."""
        # In a real implementation, this would invoke the data collector subagent
        research_data = {
            "stock_info": {},
            "financial_statements": {},
            "sec_filings": {},
            "news": {},
        }
        
        return {
            **state,
            "research_data": research_data,
            "current_phase": "analyze",
        }
    
    def analyze_data(state: ResearchState) -> ResearchState:
        """Analyze collected data."""
        # In a real implementation, this would invoke the analyst subagent
        analysis_results = {
            "ratios": {},
            "risk_assessment": {},
            "trends": {},
        }
        
        return {
            **state,
            "analysis_results": analysis_results,
            "current_phase": "report",
        }
    
    def generate_report(state: ResearchState) -> ResearchState:
        """Generate the research report."""
        # In a real implementation, this would invoke the report generator subagent
        report = {
            "metadata": {
                "ticker": state.get("ticker", "UNKNOWN"),
                "generated_at": "2024-01-01T00:00:00",
            },
            "stock_info": state.get("research_data", {}).get("stock_info", {}),
            "analysis": state.get("analysis_results", {}),
        }
        
        return {
            **state,
            "report": report,
            "current_phase": "verify",
        }
    
    def verify_completeness(state: ResearchState) -> ResearchState:
        """Verify that the research is complete."""
        # Check if all todos are completed
        todos = state.get("todos", [])
        completed = all(todo.get("status") == "completed" for todo in todos)
        
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
        
        if completed and not budget_exceeded:
            return {
                **state,
                "current_phase": "complete",
            }
        elif budget_exceeded or iteration_limit_reached or replan_limit_reached:
            # Force completion
            return {
                **state,
                "current_phase": "complete",
            }
        else:
            # Need to replan
            return {
                **state,
                "current_phase": "plan",
                "replan_count": replan_count + 1,
            }
    
    def should_replan(state: ResearchState) -> Literal["plan", "complete"]:
        """Determine if we should replan or complete."""
        if state.get("current_phase") == "complete":
            return "complete"
        else:
            return "plan"
    
    # Add nodes to workflow
    workflow.add_node("plan", plan_research)
    workflow.add_node("collect", collect_data)
    workflow.add_node("analyze", analyze_data)
    workflow.add_node("report", generate_report)
    workflow.add_node("verify", verify_completeness)
    
    # Define edges
    workflow.set_entry_point("plan")
    workflow.add_edge("plan", "collect")
    workflow.add_edge("collect", "analyze")
    workflow.add_edge("analyze", "report")
    workflow.add_edge("report", "verify")
    workflow.add_conditional_edges(
        "verify",
        should_replan,
        {
            "plan": "plan",
            "complete": END,
        }
    )
    
    # Add checkpointing for durable execution
    checkpointer = MemorySaver()
    workflow = workflow.compile(checkpointer=checkpointer)
    
    return workflow
