"""Report drafting subagent for writing research report content."""

from deepagents import SubAgent

from . import load_prompt


def create_report_generator_subagent() -> SubAgent:
    """Create the report drafting subagent spec.

    This subagent drafts report content only. Rendered files (Excel, PDF, Markdown,
    JSON) are written by the CLI via ``output.save_report`` into the configured output
    directory, so the model never chooses filesystem paths.

    Returns:
        SubAgent spec for report drafting
    """
    return {
        "name": "report_generator",
        "description": (
            "Drafts a structured research report (executive summary, metrics, analysis, "
            "risks, sources) from collected data and analysis you pass it."
        ),
        "system_prompt": load_prompt(
            "report_generator",
            "You are a specialized report writing agent. Turn the data and analysis you "
            "are given into a well-structured financial research report with clear "
            "insights and citations for every figure.",
        ),
        "tools": [],
    }
