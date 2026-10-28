# Legacy code (not imported)

These files are the original hand-coded plan → collect → analyze → report loop. It filled
state with placeholder dicts and never called the LLM. Deep Agents now provides planning
(`write_todos`), delegation (`task`), and iteration natively, and
`src/finance_research_agent/orchestrator.py` invokes the agent directly.

They are kept for reference only and can be deleted.
