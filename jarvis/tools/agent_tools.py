"""Tools that let the lead agent delegate work to specialist agents."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from jarvis.agents.specs import AgentSpec
from jarvis.tools.base import Tool, ToolError

if TYPE_CHECKING:
    from jarvis.core.agent import Agent, EventSink


def make_delegate_tools(
    team: dict[str, "Agent"],
    specs: list[AgentSpec],
    sink: Optional["EventSink"] = None,
) -> list[Tool]:
    desc_by_name = {s.name: s.description for s in specs}

    def _relay(name: str):
        """Forward a specialist's events to the sink, tagged with its name."""
        if sink is None:
            return None
        from jarvis.core.agent import AgentEvent

        def relay(e: "AgentEvent") -> None:
            if e.kind in ("tool_call", "tool_result"):
                sink.emit(AgentEvent(e.kind, tool_name=f"{name}:{e.tool_name}",
                                     detail=e.detail))
            elif e.kind == "error":
                sink.emit(AgentEvent("error", text=f"[{name}] {e.text}"))
            else:  # thinking / final -> show as nested progress, not THE answer
                if e.text:
                    sink.emit(AgentEvent("thinking", text=f"[{name}] {e.text}"))

        return relay

    def delegate_to_agent(agent: str, task: str) -> str:
        name = agent.lower().strip()
        worker = team.get(name)
        if worker is None:
            raise ToolError(
                f"unknown agent {agent!r}. available: {sorted(team)}"
            )
        # Each delegation is a self-contained turn for the specialist.
        result = worker.run(task, on_event=_relay(name))
        return f"[{name}] {result}"

    def _run_one(item: dict) -> str:
        name = str(item.get("agent", "")).lower().strip()
        task = str(item.get("task", "")).strip()
        worker = team.get(name)
        if worker is None:
            return f"[{name or '?'}] ERROR: unknown agent (have {sorted(team)})"
        if not task:
            return f"[{name}] ERROR: empty task"
        try:
            return f"[{name}] {worker.run(task, on_event=_relay(name))}"
        except Exception as exc:  # noqa: BLE001 - report, don't abort the batch
            return f"[{name}] ERROR: {type(exc).__name__}: {exc}"

    def delegate_parallel(tasks: list) -> str:
        if not isinstance(tasks, list) or not tasks:
            raise ToolError("tasks must be a non-empty list of {agent, task}")
        # Specialists are independent agents (separate memory + provider), so
        # independent subtasks run concurrently across different free models.
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=min(len(tasks), 5)) as pool:
            results = list(pool.map(_run_one, tasks))  # order preserved
        return "\n\n".join(results)

    def list_agents() -> str:
        if not team:
            return "no specialist agents available"
        return "\n".join(
            f"{n}: {desc_by_name.get(n, '')}" for n in team
        )

    available = sorted(team) or ["none"]
    return [
        Tool(
            "delegate_to_agent",
            "Hand a subtask to a specialist agent and get its result. Use this "
            "to decompose complex jobs: delegate coding to 'coder', GUI control "
            "to 'operator', information gathering to 'researcher', and "
            "diagnosis to 'analyst'. Give the agent a clear, self-contained task.",
            {
                "type": "object",
                "properties": {
                    "agent": {"type": "string", "enum": available,
                              "description": "which specialist to use"},
                    "task": {"type": "string",
                             "description": "a clear, self-contained instruction"},
                },
                "required": ["agent", "task"],
            },
            delegate_to_agent,
        ),
        Tool(
            "delegate_parallel",
            "Run several INDEPENDENT subtasks at the same time, each on its own "
            "specialist (and model). Use this when steps don't depend on each "
            "other — it's much faster than calling delegate_to_agent one by "
            "one. Results come back labelled per agent, in order.",
            {
                "type": "object",
                "properties": {
                    "tasks": {
                        "type": "array",
                        "description": "independent subtasks to run concurrently",
                        "items": {
                            "type": "object",
                            "properties": {
                                "agent": {"type": "string", "enum": available},
                                "task": {"type": "string"},
                            },
                            "required": ["agent", "task"],
                        },
                    }
                },
                "required": ["tasks"],
            },
            delegate_parallel,
        ),
        Tool(
            "list_agents", "List the specialist agents and what each is good at.",
            {"type": "object", "properties": {}},
            list_agents,
        ),
    ]
