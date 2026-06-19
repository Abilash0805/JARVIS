"""Tests for the multi-agent team: building, tool filtering, delegation."""

from jarvis.agents.specs import AgentSpec
from jarvis.agents.team import build_team
from jarvis.providers.base import ChatMessage, LLMProvider, ProviderResponse
import pytest

from jarvis.tools.agent_tools import make_delegate_tools
from jarvis.tools.base import Tool, ToolError, Toolset


class _Echo(LLMProvider):
    """Provider that answers without ever calling tools."""

    def __init__(self, name="echo"):
        self.name = name
        self.model = "echo-1"
        self.supports_tools = True

    def chat(self, messages, *, tools=None, temperature=0.7, max_tokens=None, **kw):
        # Reflect the last user/task message back as the final answer.
        last = next((m.content for m in reversed(messages) if m.role == "user"), "")
        return ProviderResponse(content=f"done:{last}")


def _toolset():
    ts = Toolset()
    for n in ["read_file", "run_command", "see_screen", "ask_model"]:
        ts.add(Tool(n, n, {"type": "object", "properties": {}}, lambda **k: "ok"))
    return ts


def test_build_team_filters_tools_and_skips_empty():
    ts = _toolset()
    specs = [
        AgentSpec("coder", "code", "you code", tools=["read_file", "run_command"]),
        AgentSpec("ghost", "nothing", "n/a", tools=["does_not_exist"]),
    ]
    team = build_team(ts, {}, _Echo(), specs=specs)
    assert "coder" in team
    assert "ghost" not in team  # no available tools => skipped
    assert set(team["coder"].toolset.names()) == {"read_file", "run_command"}


def test_delegate_runs_specialist():
    ts = _toolset()
    specs = [AgentSpec("coder", "code", "you code", tools=["read_file"])]
    team = build_team(ts, {}, _Echo(), specs=specs)
    tools = make_delegate_tools(team, specs)
    by_name = {t.name: t for t in tools}

    out = by_name["delegate_to_agent"].run({"agent": "coder", "task": "build X"})
    assert out.startswith("[coder]")
    assert "build X" in out

    assert "coder: code" in by_name["list_agents"].run({})
    with pytest.raises(ToolError):
        by_name["delegate_to_agent"].run({"agent": "nope", "task": "x"})
