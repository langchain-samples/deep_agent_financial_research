"""Callback handler that turns agent tool activity into UI events."""

import json
import queue
from typing import Any, Dict, Optional
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler

MAX_ARGS_CHARS = 200
MAIN_AGENT = "finance-research-agent"


class ActivityHandler(BaseCallbackHandler):
    """Pushes plan, delegation, and tool events onto a queue for the UI thread.

    Events are dicts with a "type" of "todos", "subagent_start", "subagent_end", or
    "tool". Only tool names and truncated arguments are included.
    """

    run_inline = True

    def __init__(self, events: "queue.Queue[Dict[str, Any]]"):
        self.events = events
        self._task_runs: Dict[UUID, str] = {}

    def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        metadata: Optional[Dict[str, Any]] = None,
        inputs: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        name = (serialized or {}).get("name", "tool")
        inputs = inputs or {}
        agent = (metadata or {}).get("lc_agent_name", MAIN_AGENT)

        if name == "write_todos":
            todos = [
                {"content": str(t.get("content", "")), "status": str(t.get("status", "pending"))}
                for t in inputs.get("todos", [])
                if isinstance(t, dict)
            ]
            self.events.put({"type": "todos", "agent": agent, "todos": todos})
        elif name == "task":
            subagent = str(inputs.get("subagent_type", "subagent"))
            self._task_runs[run_id] = subagent
            self.events.put({
                "type": "subagent_start",
                "subagent": subagent,
                "description": str(inputs.get("description", ""))[:MAX_ARGS_CHARS],
            })
        else:
            args = json.dumps(inputs, default=str) if inputs else input_str
            self.events.put({
                "type": "tool",
                "agent": agent,
                "tool": name,
                "args": args[:MAX_ARGS_CHARS],
            })

    def on_tool_end(self, output: Any, *, run_id: UUID, **kwargs: Any) -> None:
        subagent = self._task_runs.pop(run_id, None)
        if subagent:
            self.events.put({"type": "subagent_end", "subagent": subagent, "ok": True})

    def on_tool_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
        subagent = self._task_runs.pop(run_id, None)
        if subagent:
            self.events.put({"type": "subagent_end", "subagent": subagent, "ok": False})
