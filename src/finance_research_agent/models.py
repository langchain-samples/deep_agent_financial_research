"""Chat model construction shared by the main agent and subagents."""

from typing import Optional

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel

from .config import ModelConfig


def build_model(model_config: Optional[ModelConfig] = None) -> BaseChatModel:
    """Create a chat model from configuration.

    Args:
        model_config: Model configuration (optional, defaults to environment)

    Returns:
        Configured chat model
    """
    if model_config is None:
        model_config = ModelConfig.from_env()

    kwargs = {}
    if model_config.temperature is not None:
        kwargs["temperature"] = model_config.temperature
    if model_config.api_key:
        kwargs["api_key"] = model_config.api_key

    return init_chat_model(
        model_config.model,
        model_provider=model_config.provider,
        **kwargs,
    )
