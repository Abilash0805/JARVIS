"""Tools that let the lead agent delegate work to specialist agents."""

from __future__ import annotations

from typing import TYPE_CHECKING

from jarvis.agents.specs import AgentSpec
from jarvis.tools.base import Tool, ToolError

if TYPE_CHECKING:
    from jarvis.core.agent import Agent


def make_delegate_tools(
    team: dict[str, "Agent"],
    specs: list[AgentSpec],
) -> list[Tool]:
    desc_by_name = {s.name: s.description for s in specs}

    def delegate_to_agent(agent: str, task: str) -> str:
        name = agent.lower().strip()
        worker = team.get(name)
        if worker is None:
            raise ToolError(
                f"unknown agent {agent!r}. available: {sorted(team)}"
            )
        # Each delegation is a self-contained turn for the specialist.
        result = worker.run(task)
        return f"[{name}] {result}"

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
            "list_agents", "List the specialist agents and what each is good at.",
            {"type": "object", "properties": {}},
            list_agents,
        ),
    ]
