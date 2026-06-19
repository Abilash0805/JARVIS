"""Tool abstraction and a registry that renders OpenAI tool specs."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable


class ToolError(RuntimeError):
    """Raised when a tool fails in an expected, reportable way."""


@dataclass
class Tool:
    """A single callable capability exposed to the model.

    ``parameters`` is a JSON Schema object describing the arguments.
    ``func`` receives keyword arguments matching that schema and returns a
    string (what the model sees back). ``dangerous`` marks actions that the
    safety gate should confirm before running.
    """

    name: str
    description: str
    parameters: dict[str, Any]
    func: Callable[..., str]
    dangerous: bool = False

    def to_openai_spec(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def run(self, arguments: dict[str, Any]) -> str:
        return self.func(**arguments)


@dataclass
class Toolset:
    """A named collection of tools."""

    tools: dict[str, Tool] = field(default_factory=dict)

    def add(self, tool: Tool) -> None:
        self.tools[tool.name] = tool

    def extend(self, tools: list[Tool]) -> None:
        for tool in tools:
            self.add(tool)

    def get(self, name: str) -> Tool | None:
        return self.tools.get(name)

    def subset(self, names: list[str]) -> "Toolset":
        """Return a new Toolset containing only the named tools that exist."""
        sub = Toolset()
        for name in names:
            tool = self.tools.get(name)
            if tool is not None:
                sub.add(tool)
        return sub

    def names(self) -> list[str]:
        return list(self.tools)

    def specs(self) -> list[dict[str, Any]]:
        """OpenAI tool specs for every registered tool."""
        return [t.to_openai_spec() for t in self.tools.values()]

    def execute(self, name: str, arguments_json: str) -> str:
        """Parse JSON args and run the named tool, returning a string result."""
        tool = self.get(name)
        if tool is None:
            return f"ERROR: unknown tool {name!r}"
        try:
            args = json.loads(arguments_json) if arguments_json.strip() else {}
        except json.JSONDecodeError as exc:
            return f"ERROR: could not parse arguments for {name}: {exc}"
        try:
            return tool.run(args)
        except ToolError as exc:
            return f"ERROR: {exc}"
        except Exception as exc:  # noqa: BLE001 - surface to the model, don't crash
            return f"ERROR: {name} raised {type(exc).__name__}: {exc}"

    def __len__(self) -> int:
        return len(self.tools)
