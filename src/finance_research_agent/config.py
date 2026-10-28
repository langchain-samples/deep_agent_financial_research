"""Configuration classes for the financial research agent."""

import os
from dataclasses import dataclass, field
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


@dataclass
class BudgetConfig:
    """Budget limits for agent execution."""
    max_tokens: int = 100000
    max_cost: float = 1.00
    max_time_minutes: int = 10

    @classmethod
    def from_env(cls) -> "BudgetConfig":
        """Create BudgetConfig from environment variables."""
        return cls(
            max_tokens=int(os.getenv("MAX_TOKENS", 100000)),
            max_cost=float(os.getenv("MAX_COST", 1.00)),
            max_time_minutes=int(os.getenv("MAX_TIME_MINUTES", 10)),
        )


@dataclass
class ExecutionConfig:
    """Execution parameters for the agent."""
    # LangGraph recursion limit for a single research run (one step = one model or tool call)
    max_iterations: int = 200
    # Deprecated: Deep Agents replans natively via write_todos; kept for CLI compatibility
    max_replans: int = 2
    max_task_retries: int = 5
    enable_parallel: bool = True
    enable_filesystem: bool = True

    @classmethod
    def from_env(cls) -> "ExecutionConfig":
        """Create ExecutionConfig from environment variables."""
        return cls(
            max_iterations=int(os.getenv("MAX_ITERATIONS", 200)),
            max_replans=int(os.getenv("MAX_REPLANS", 2)),
            max_task_retries=int(os.getenv("MAX_TASK_RETRIES", 5)),
            enable_parallel=os.getenv("ENABLE_PARALLEL", "true").lower() == "true",
            enable_filesystem=os.getenv("ENABLE_FILESYSTEM", "true").lower() == "true",
        )


@dataclass
class ModelConfig:
    """Model configuration for LLM."""
    provider: str = "openai"
    model: str = "gpt-4o"
    # None uses the provider default. Some models (e.g. claude-sonnet-5-5) reject other values.
    temperature: Optional[float] = None
    api_key: Optional[str] = None

    @classmethod
    def from_env(cls) -> "ModelConfig":
        """Create ModelConfig from environment variables."""
        provider = os.getenv("DEFAULT_MODEL_PROVIDER", "openai")
        model = os.getenv("DEFAULT_MODEL", "gpt-4o")
        temperature_env = os.getenv("DEFAULT_TEMPERATURE")
        temperature = float(temperature_env) if temperature_env else None
        
        # Get API key based on provider
        if provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
        elif provider == "anthropic":
            api_key = os.getenv("ANTHROPIC_API_KEY")
        else:
            api_key = None

        return cls(
            provider=provider,
            model=model,
            temperature=temperature,
            api_key=api_key,
        )


@dataclass
class DataSourceConfig:
    """Configuration for external data sources.

    SEC EDGAR and the RSS news feeds need no API key. SEC requires a User-Agent that
    identifies you, e.g. "Acme Research jane@acme.com".
    """
    sec_user_agent: Optional[str] = None
    news_api_key: Optional[str] = None  # Optional: NewsAPI is used instead of RSS when set

    @classmethod
    def from_env(cls) -> "DataSourceConfig":
        """Create DataSourceConfig from environment variables."""
        return cls(
            sec_user_agent=os.getenv("SEC_USER_AGENT"),
            news_api_key=os.getenv("NEWS_API_KEY"),
        )


@dataclass
class SnowflakeConfig:
    """Configuration for the Snowflake MCP server used by the snowflake_analyst subagent.

    transport="streamable_http" targets a Snowflake-managed MCP server object.
    transport="stdio" launches the (deprecated) Snowflake-Labs server locally via uvx.
    """
    transport: str = "streamable_http"
    url: Optional[str] = None
    pat: Optional[str] = None
    service_config_file: str = "config/snowflake_mcp_readonly.yaml"
    timeout_seconds: float = 120.0

    @property
    def enabled(self) -> bool:
        """Whether enough configuration is present to connect to Snowflake."""
        if self.transport == "stdio":
            return bool(os.getenv("SNOWFLAKE_ACCOUNT"))
        return bool(self.url and self.pat)

    @classmethod
    def from_env(cls) -> "SnowflakeConfig":
        """Create SnowflakeConfig from environment variables."""
        return cls(
            transport=os.getenv("SNOWFLAKE_MCP_TRANSPORT", "streamable_http"),
            url=os.getenv("SNOWFLAKE_MCP_URL"),
            pat=os.getenv("SNOWFLAKE_PAT"),
            service_config_file=os.getenv(
                "SNOWFLAKE_MCP_SERVICE_CONFIG", "config/snowflake_mcp_readonly.yaml"
            ),
            timeout_seconds=float(os.getenv("SNOWFLAKE_MCP_TIMEOUT", 120)),
        )


@dataclass
class OutputConfig:
    """Output configuration."""
    output_dir: str = "output"
    default_format: str = "excel"  # excel, pdf, markdown, json

    @classmethod
    def from_env(cls) -> "OutputConfig":
        """Create OutputConfig from environment variables."""
        return cls(
            output_dir=os.getenv("OUTPUT_DIR", "output"),
            default_format=os.getenv("DEFAULT_OUTPUT_FORMAT", "excel"),
        )


@dataclass
class AgentConfig:
    """Main configuration class combining all configs."""
    budget: BudgetConfig
    execution: ExecutionConfig
    model: ModelConfig
    data_sources: DataSourceConfig
    output: OutputConfig
    snowflake: SnowflakeConfig = field(default_factory=SnowflakeConfig)

    @classmethod
    def from_env(cls) -> "AgentConfig":
        """Create AgentConfig from environment variables."""
        return cls(
            budget=BudgetConfig.from_env(),
            execution=ExecutionConfig.from_env(),
            model=ModelConfig.from_env(),
            data_sources=DataSourceConfig.from_env(),
            output=OutputConfig.from_env(),
            snowflake=SnowflakeConfig.from_env(),
        )

    @classmethod
    def default(cls) -> "AgentConfig":
        """Create default AgentConfig."""
        return cls(
            budget=BudgetConfig(),
            execution=ExecutionConfig(),
            model=ModelConfig(),
            data_sources=DataSourceConfig(),
            output=OutputConfig(),
        )
