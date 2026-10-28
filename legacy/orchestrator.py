"""Deep research orchestrator with replanning, budget management, and verification."""

import time
from typing import Dict, Any, Optional, List
from datetime import datetime

from .agent import create_main_agent
from .graph.workflow import create_research_workflow
from .graph.state import ResearchState
from .config import AgentConfig
from .verification import should_replan, check_research_completeness


class DeepResearchOrchestrator:
    """Orchestrator for deep financial research with replanning and budget management."""
    
    def __init__(self, config: Optional[AgentConfig] = None):
        """Initialize the orchestrator.
        
        Args:
            config: Agent configuration
        """
        if config is None:
            config = AgentConfig.from_env()
        
        self.config = config
        self.agent = create_main_agent(config)
        self.workflow = create_research_workflow(config)
        self.start_time = None
        self.state_history: List[Dict[str, Any]] = []
    
    def execute_research(self, user_query: str, ticker: Optional[str] = None) -> Dict[str, Any]:
        """Execute the research workflow.
        
        Args:
            user_query: User's research query
            ticker: Optional stock ticker symbol
        
        Returns:
            Dictionary with research results
        """
        self.start_time = time.time()
        
        # Initialize state
        initial_state: ResearchState = {
            "messages": [],
            "todos": [],
            "research_data": {},
            "analysis_results": {},
            "report": None,
            "iteration_count": 0,
            "replan_count": 0,
            "tokens_used": 0,
            "cost_incurred": 0.0,
            "time_elapsed": 0.0,
            "current_phase": "plan",
            "errors": [],
            "user_query": user_query,
            "ticker": ticker,
        }
        
        current_state = initial_state
        
        # Main execution loop
        while True:
            # Update time elapsed
            current_state["time_elapsed"] = time.time() - self.start_time
            
            # Check budget limits
            if self._check_budget_exceeded(current_state):
                current_state["current_phase"] = "complete"
                current_state["errors"].append("Budget limit exceeded - forcing completion")
                break
            
            # Check iteration limits
            if self._check_iteration_limits(current_state):
                current_state["current_phase"] = "complete"
                current_state["errors"].append("Iteration limit reached - forcing completion")
                break
            
            # Execute workflow step
            try:
                # In a real implementation, this would invoke the workflow
                # For now, we simulate the workflow execution
                current_state = self._execute_workflow_step(current_state)
            except Exception as e:
                current_state["errors"].append(f"Workflow execution error: {str(e)}")
                current_state["iteration_count"] += 1
                continue
            
            # Save state history
            self.state_history.append({
                "iteration": current_state["iteration_count"],
                "phase": current_state["current_phase"],
                "timestamp": datetime.now().isoformat(),
            })
            
            # Verify completeness and decide on next action
            verification_result = should_replan(current_state, self.config)
            
            if verification_result["force_completion"]:
                current_state["current_phase"] = "complete"
                break
            
            if not verification_result["should_replan"]:
                # Research is complete
                current_state["current_phase"] = "complete"
                break
            
            # Replan if needed
            if verification_result["should_replan"]:
                current_state["replan_count"] += 1
                current_state["current_phase"] = "plan"
                current_state["iteration_count"] += 1
                # Continue loop to replan
        
        # Finalize
        current_state["time_elapsed"] = time.time() - self.start_time
        
        return {
            "status": "completed" if current_state["current_phase"] == "complete" else "incomplete",
            "state": current_state,
            "verification": check_research_completeness(current_state),
            "execution_summary": {
                "iterations": current_state["iteration_count"],
                "replans": current_state["replan_count"],
                "time_elapsed": current_state["time_elapsed"],
                "tokens_used": current_state["tokens_used"],
                "cost_incurred": current_state["cost_incurred"],
                "errors": current_state["errors"],
            },
        }
    
    def _check_budget_exceeded(self, state: ResearchState) -> bool:
        """Check if budget limits have been exceeded."""
        budget = self.config.budget
        return (
            state.get("tokens_used", 0) >= budget.max_tokens or
            state.get("cost_incurred", 0.0) >= budget.max_cost or
            state.get("time_elapsed", 0.0) >= (budget.max_time_minutes * 60)
        )
    
    def _check_iteration_limits(self, state: ResearchState) -> bool:
        """Check if iteration limits have been reached."""
        execution = self.config.execution
        return (
            state.get("iteration_count", 0) >= execution.max_iterations or
            state.get("replan_count", 0) >= execution.max_replans
        )
    
    def _execute_workflow_step(self, state: ResearchState) -> ResearchState:
        """Execute a single workflow step.
        
        This is a simplified implementation. In production, this would
        properly invoke the LangGraph workflow.
        """
        current_phase = state.get("current_phase", "plan")
        
        if current_phase == "plan":
            # Planning phase - would invoke agent planning
            state["todos"] = [
                {"task": "Collect stock data", "status": "pending"},
                {"task": "Collect financial statements", "status": "pending"},
                {"task": "Perform analysis", "status": "pending"},
                {"task": "Generate report", "status": "pending"},
            ]
            state["current_phase"] = "collect"
        
        elif current_phase == "collect":
            # Data collection phase - would invoke data collector subagent
            state["research_data"] = {
                "stock_info": {},
                "financial_statements": {},
                "sec_filings": {},
                "news": {},
            }
            # Mark collection todos as completed
            for todo in state["todos"]:
                if "collect" in todo["task"].lower():
                    todo["status"] = "completed"
            state["current_phase"] = "analyze"
        
        elif current_phase == "analyze":
            # Analysis phase - would invoke analyst subagent
            state["analysis_results"] = {
                "ratios": {},
                "risk_assessment": {},
                "trends": {},
            }
            # Mark analysis todos as completed
            for todo in state["todos"]:
                if "analysis" in todo["task"].lower():
                    todo["status"] = "completed"
            state["current_phase"] = "report"
        
        elif current_phase == "report":
            # Report generation phase - would invoke report generator subagent
            state["report"] = {
                "metadata": {
                    "ticker": state.get("ticker", "UNKNOWN"),
                    "generated_at": datetime.now().isoformat(),
                },
                "stock_info": state.get("research_data", {}).get("stock_info", {}),
                "analysis": state.get("analysis_results", {}),
            }
            # Mark report todos as completed
            for todo in state["todos"]:
                if "report" in todo["task"].lower():
                    todo["status"] = "completed"
            state["current_phase"] = "verify"
        
        elif current_phase == "verify":
            # Verification phase - already handled in main loop
            pass
        
        return state
