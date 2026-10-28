"""Deep research orchestrator: runs the deep agent with budget limits and LangSmith metadata."""

import asyncio
import time
import uuid
from typing import Any, Dict, List, Optional

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage
from langchain_core.outputs import LLMResult
from langgraph.errors import GraphRecursionError

from .agent import build_agent
from .config import AgentConfig
from .schemas import report_to_output_dict


class TokenBudgetExceeded(Exception):
    """Raised when a research run exceeds its token budget."""


class TokenBudgetHandler(BaseCallbackHandler):
    """Counts tokens across the main agent and all subagents and enforces a budget.

    Callbacks propagate into subagent runs, so this sees every model call.
    """

    raise_error = True
    run_inline = True

    def __init__(self, max_tokens: int):
        self.max_tokens = max_tokens
        self.tokens_used = 0

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        for generations in response.generations:
            for generation in generations:
                usage = getattr(getattr(generation, "message", None), "usage_metadata", None)
                if usage:
                    self.tokens_used += usage.get("total_tokens", 0)
        if self.tokens_used > self.max_tokens:
            raise TokenBudgetExceeded(
                f"Token budget exceeded: {self.tokens_used} > {self.max_tokens}"
            )


def get_subagent_calls(messages: List[Any]) -> List[str]:
    """Return the subagent names the main agent delegated to via the task tool, in order."""
    calls = []
    for message in messages:
        if isinstance(message, AIMessage):
            for tool_call in message.tool_calls:
                if tool_call["name"] == "task":
                    calls.append(tool_call["args"].get("subagent_type", "unknown"))
    return calls


class DeepResearchOrchestrator:
    """Runs a financial research request through the deep agent."""

    def __init__(self, config: Optional[AgentConfig] = None):
        """Initialize the orchestrator.

        Args:
            config: Agent configuration
        """
        if config is None:
            config = AgentConfig.from_env()
        self.config = config

    def build_run_config(
        self,
        ticker: Optional[str],
        budget: TokenBudgetHandler,
        run_id: uuid.UUID,
        extra_callbacks: Optional[List[BaseCallbackHandler]] = None,
    ) -> Dict[str, Any]:
        """Build the LangGraph run config, including LangSmith run name, tags, and metadata."""
        return {
            "recursion_limit": self.config.execution.max_iterations,
            "callbacks": [budget, *(extra_callbacks or [])],
            "run_id": run_id,
            "run_name": "financial-research",
            "tags": ["finance-research-agent", *([ticker] if ticker else [])],
            "metadata": {
                "ticker": ticker,
                "model_provider": self.config.model.provider,
                "model": self.config.model.model,
                "snowflake_enabled": self.config.snowflake.enabled,
            },
        }

    async def aexecute_research(
        self,
        user_query: str,
        ticker: Optional[str] = None,
        extra_callbacks: Optional[List[BaseCallbackHandler]] = None,
    ) -> Dict[str, Any]:
        """Execute a research request.

        Args:
            user_query: User's research query
            ticker: Optional stock ticker symbol
            extra_callbacks: Additional callback handlers, e.g. for live progress in a UI

        Returns:
            Dictionary with research results, including the run_id of the LangSmith trace
        """
        start_time = time.monotonic()
        budget = TokenBudgetHandler(self.config.budget.max_tokens)
        run_id = uuid.uuid4()
        agent = await build_agent(self.config)

        errors: List[str] = []
        result: Optional[Dict[str, Any]] = None
        try:
            result = await asyncio.wait_for(
                agent.ainvoke(
                    {"messages": [{"role": "user", "content": user_query}]},
                    config=self.build_run_config(ticker, budget, run_id, extra_callbacks),
                ),
                timeout=self.config.budget.max_time_minutes * 60,
            )
        except asyncio.TimeoutError:
            errors.append(f"Time budget exceeded ({self.config.budget.max_time_minutes} min)")
        except TokenBudgetExceeded as e:
            errors.append(str(e))
        except GraphRecursionError:
            errors.append(
                f"Step limit reached (max_iterations={self.config.execution.max_iterations})"
            )

        messages = result["messages"] if result else []
        structured = result.get("structured_response") if result else None
        report = report_to_output_dict(structured) if structured else None
        subagent_calls = get_subagent_calls(messages)

        return {
            "status": "completed" if report else "incomplete",
            "run_id": str(run_id),
            "state": {
                "report": report,
                "structured_response": structured,
                "messages": messages,
            },
            "verification": {
                "is_complete": report is not None,
                "overall_completeness": 100.0 if report else 0.0,
                "subagents_used": sorted(set(subagent_calls)),
            },
            "execution_summary": {
                "iterations": len([m for m in messages if isinstance(m, AIMessage)]),
                "subagent_calls": len(subagent_calls),
                "replans": 0,
                "time_elapsed": time.monotonic() - start_time,
                "tokens_used": budget.tokens_used,
                "errors": errors,
            },
        }

    def execute_research(self, user_query: str, ticker: Optional[str] = None) -> Dict[str, Any]:
        """Synchronous wrapper around ``aexecute_research``."""
        return asyncio.run(self.aexecute_research(user_query, ticker))
