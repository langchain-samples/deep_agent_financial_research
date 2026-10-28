"""Core deep agent implementation using LangChain Deep Agents."""

from typing import List, Optional

from deepagents import SubAgent, create_deep_agent
from langchain.agents.middleware import TodoListMiddleware
from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph

from .config import AgentConfig
from .models import build_model
from .schemas import ResearchReport
from .subagents import load_prompt
from .subagents.data_collector import create_data_collector_subagent
from .subagents.analyst import create_analyst_subagent
from .subagents.report_generator import create_report_generator_subagent
from .subagents.snowflake import create_snowflake_subagent, load_snowflake_tools

AGENT_NAME = "finance-research-agent"


def create_main_agent(
    config: Optional[AgentConfig] = None,
    snowflake_tools: Optional[List[BaseTool]] = None,
) -> CompiledStateGraph:
    """Create the main deep agent with its subagents.

    Deep Agents adds a virtual filesystem and the task tool for subagent delegation.
    Planning (write_todos) is opt-in since deepagents 0.7, so it is added explicitly.

    Args:
        config: Agent configuration (optional)
        snowflake_tools: Tools from the Snowflake MCP server. When non-empty, the
            snowflake_analyst subagent is added. Use ``build_agent`` to load them.

    Returns:
        Compiled deep agent graph
    """
    if config is None:
        config = AgentConfig.from_env()

    subagents: List[SubAgent] = [
        create_data_collector_subagent(),
        create_analyst_subagent(),
        create_report_generator_subagent(),
    ]
    if snowflake_tools:
        subagents.append(create_snowflake_subagent(snowflake_tools))

    system_prompt = load_prompt(
        "main_agent",
        "You are a comprehensive financial research agent. Plan research with write_todos, "
        "delegate to subagents, and synthesize their findings into a research report.",
    )

    return create_deep_agent(
        model=build_model(config.model),
        tools=[],  # Main agent delegates to subagents, so it doesn't need direct tools
        system_prompt=system_prompt,
        subagents=subagents,
        middleware=[TodoListMiddleware()],
        # A plain schema lets LangChain pick native structured output where the model
        # supports it (required for models without forced tool_choice, e.g. claude-sonnet-5-5)
        # and fall back to a structured-output tool otherwise.
        response_format=ResearchReport,
        name=AGENT_NAME,
    )


async def build_agent(config: Optional[AgentConfig] = None) -> CompiledStateGraph:
    """Create the main agent, loading Snowflake MCP tools if Snowflake is configured.

    MCP tools are async-only, so agents built this way must be run with
    ``ainvoke``/``astream``.
    """
    if config is None:
        config = AgentConfig.from_env()
    snowflake_tools = await load_snowflake_tools(config.snowflake)
    return create_main_agent(config, snowflake_tools)


async def make_graph() -> CompiledStateGraph:
    """Graph factory referenced by langgraph.json for LangGraph Studio / Agent Server."""
    return await build_agent()
