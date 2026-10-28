"""Shared fixtures: a scripted fake chat model so the agent runs without API keys."""

import os

# config.py loads .env on import; keep test runs out of LangSmith.
os.environ["LANGSMITH_TRACING"] = "false"

from typing import Any, List  # noqa: E402

import pytest  # noqa: E402
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel  # noqa: E402
from langchain_core.messages import AIMessage  # noqa: E402

from finance_research_agent.config import AgentConfig, SnowflakeConfig  # noqa: E402


class ScriptedChatModel(GenericFakeChatModel):
    """Fake chat model that returns a fixed sequence of messages and accepts bind_tools."""

    def bind_tools(self, tools: Any, **kwargs: Any) -> "ScriptedChatModel":
        return self


def scripted_model(messages: List[AIMessage]) -> ScriptedChatModel:
    return ScriptedChatModel(messages=iter(messages))


def task_call(subagent: str, description: str, call_id: str) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[{
            "name": "task",
            "args": {"subagent_type": subagent, "description": description},
            "id": call_id,
        }],
    )


def report_call(call_id: str = "report-1", **overrides: Any) -> AIMessage:
    args = {
        "ticker": "AAPL",
        "company_name": "Apple Inc.",
        "executive_summary": "Apple remains highly profitable.",
        "key_metrics": [{"name": "P/E", "value": "30x", "source": "Yahoo Finance"}],
        "financial_analysis": "Margins are stable.",
        "risks": ["China exposure"],
        "news_sentiment": "Neutral",
        "sources": ["Yahoo Finance"],
        "limitations": [],
    }
    args.update(overrides)
    return AIMessage(
        content="",
        tool_calls=[{"name": "ResearchReport", "args": args, "id": call_id}],
    )


@pytest.fixture
def config() -> AgentConfig:
    config = AgentConfig.default()
    config.snowflake = SnowflakeConfig(url=None, pat=None)
    return config


@pytest.fixture
def use_model(monkeypatch):
    """Patch the agent's model factory to return the given scripted model."""

    def _use(model: ScriptedChatModel) -> None:
        monkeypatch.setattr("finance_research_agent.agent.build_model", lambda _cfg: model)

    return _use
