"""Subagents for specialized financial research tasks."""

from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def load_prompt(name: str, default: str) -> str:
    """Load a system prompt from the prompts directory, falling back to a default."""
    path = PROMPTS_DIR / f"{name}.md"
    if path.exists():
        return path.read_text()
    return default
