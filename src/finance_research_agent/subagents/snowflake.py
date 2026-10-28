"""Snowflake subagent that queries internal data through a Snowflake MCP server."""

import os
import re
import sys
from typing import Awaitable, Callable, List, Optional
from urllib.parse import urlparse

from deepagents import SubAgent
from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.interceptors import MCPToolCallRequest, MCPToolCallResult
from mcp.types import CallToolResult, TextContent

from . import load_prompt
from ..config import SnowflakeConfig

SERVER_NAME = "snowflake"

# Tool arguments that carry raw SQL on the managed (SYSTEM_EXECUTE_SQL) and
# Snowflake-Labs servers. Natural-language args (e.g. Cortex Search "query") are not checked.
SQL_ARG_NAMES = {"sql", "statement", "sql_statement"}
READ_ONLY_KEYWORDS = {"SELECT", "WITH", "SHOW", "DESCRIBE", "DESC", "EXPLAIN"}

# Environment passed to the stdio server. Everything else in the parent env is withheld.
STDIO_ENV_VARS = (
    "SNOWFLAKE_ACCOUNT",
    "SNOWFLAKE_HOST",
    "SNOWFLAKE_USER",
    "SNOWFLAKE_PASSWORD",
    "SNOWFLAKE_ROLE",
    "SNOWFLAKE_WAREHOUSE",
    "SNOWFLAKE_PRIVATE_KEY_FILE",
    "SNOWFLAKE_PRIVATE_KEY_FILE_PWD",
    "PATH",
    "HOME",
)

_COMMENT_RE = re.compile(r"--[^\n]*|/\*.*?\*/", re.DOTALL)
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]+")

MAX_LISTED_TOOLS = 15
MAX_TOOL_SUMMARY_CHARS = 150


def check_read_only_sql(sql: str) -> Optional[str]:
    """Return a rejection reason if ``sql`` is not a single read-only statement.

    This is a conservative client-side check layered on top of server-side controls
    (``read_only: true`` on the managed server, ``sql_statement_permissions`` on the
    Labs server, and a least-privileged Snowflake role). A semicolon inside a string
    literal is rejected too; rewrite the query without it.
    """
    stripped = _COMMENT_RE.sub(" ", sql).strip().rstrip(";").strip()
    if not stripped:
        return "Empty SQL statement."
    if ";" in stripped:
        return "Only a single SQL statement is allowed per call."
    first_keyword = stripped.split(None, 1)[0].upper()
    if first_keyword not in READ_ONLY_KEYWORDS:
        return (
            f"'{first_keyword}' statements are not allowed. This agent has read-only "
            f"access: use one of {', '.join(sorted(READ_ONLY_KEYWORDS))}."
        )
    return None


async def read_only_sql_interceptor(
    request: MCPToolCallRequest,
    handler: Callable[[MCPToolCallRequest], Awaitable[MCPToolCallResult]],
) -> MCPToolCallResult:
    """Block non-read-only SQL before it reaches Snowflake."""
    for arg_name, value in request.args.items():
        if arg_name in SQL_ARG_NAMES and isinstance(value, str):
            reason = check_read_only_sql(value)
            if reason:
                return CallToolResult(
                    content=[TextContent(type="text", text=f"Query rejected: {reason}")],
                    isError=True,
                )
    return await handler(request)


def _build_connection(config: SnowflakeConfig) -> dict:
    """Build the MultiServerMCPClient connection for the configured transport."""
    if config.transport == "stdio":
        env = {name: os.environ[name] for name in STDIO_ENV_VARS if name in os.environ}
        return {
            "transport": "stdio",
            "command": "uvx",
            "args": ["snowflake-labs-mcp", "--service-config-file", config.service_config_file],
            "env": env,
        }

    if config.transport != "streamable_http":
        raise ValueError(f"Unsupported SNOWFLAKE_MCP_TRANSPORT: {config.transport}")
    if urlparse(config.url or "").scheme != "https":
        raise ValueError("SNOWFLAKE_MCP_URL must be an https:// URL")
    return {
        "transport": "streamable_http",
        "url": config.url,
        "headers": {"Authorization": f"Bearer {config.pat}"},
        "timeout": config.timeout_seconds,
    }


async def load_snowflake_tools(config: Optional[SnowflakeConfig] = None) -> List[BaseTool]:
    """Load tools from the Snowflake MCP server.

    Args:
        config: Snowflake configuration (optional, defaults to environment)

    Returns:
        MCP tools wrapped as LangChain tools, or an empty list if Snowflake is not
        configured or the server cannot be reached
    """
    if config is None:
        config = SnowflakeConfig.from_env()
    if not config.enabled:
        return []

    client = MultiServerMCPClient(
        {SERVER_NAME: _build_connection(config)},
        tool_interceptors=[read_only_sql_interceptor],
    )
    try:
        return await client.get_tools(server_name=SERVER_NAME)
    except Exception as e:
        # Don't echo exception messages: they can include request details.
        print(
            f"Warning: could not load Snowflake MCP tools ({_describe_error(e)}); "
            "continuing without the snowflake_analyst subagent.",
            file=sys.stderr,
        )
        return []


def _describe_error(error: BaseException) -> str:
    """Summarize an error by type and HTTP status only, unwrapping exception groups."""
    if isinstance(error, BaseExceptionGroup):
        return ", ".join(_describe_error(e) for e in error.exceptions)
    status = getattr(getattr(error, "response", None), "status_code", None)
    return f"{type(error).__name__} HTTP {status}" if status else type(error).__name__


def describe_tools(tools: List[BaseTool]) -> str:
    """Summarize available MCP tools as one line each, sanitized and truncated.

    Descriptions come from the Snowflake MCP server's configuration, so they are
    flattened to single lines and capped in length before entering the prompt.
    """
    lines = []
    for tool in tools[:MAX_LISTED_TOOLS]:
        summary = _CONTROL_CHARS_RE.sub(" ", tool.description or "").strip()
        summary = summary.split(". ")[0][:MAX_TOOL_SUMMARY_CHARS]
        name = _CONTROL_CHARS_RE.sub("", tool.name)[:64]
        lines.append(f"- {name}: {summary}")
    return "\n".join(lines)


def create_snowflake_subagent(tools: List[BaseTool]) -> SubAgent:
    """Create the Snowflake analyst subagent spec.

    Args:
        tools: Tools loaded from the Snowflake MCP server

    Returns:
        SubAgent spec for querying Snowflake
    """
    return {
        "name": "snowflake_analyst",
        "description": (
            "Queries the firm's internal Snowflake data warehouse (read-only) through MCP. "
            "Use it for proprietary or internal data not available from public market "
            "sources. Its tools:\n" + describe_tools(tools)
        ),
        "system_prompt": load_prompt(
            "snowflake_analyst",
            "You are a data analyst with read-only access to a Snowflake data warehouse. "
            "Discover relevant tables before querying, keep queries small, and cite the "
            "table and query behind every number you report.",
        ),
        "tools": tools,
    }
