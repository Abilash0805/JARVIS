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


def test_toolless_agent_is_built():
    ts = _toolset()
    specs = [AgentSpec("planner", "plan", "you plan", tools=[])]
    team = build_team(ts, {}, _Echo(), specs=specs)
    assert "planner" in team  # no tools is valid (pure reasoning), not skipped
    assert len(team["planner"].toolset) == 0


def test_delegate_relays_events_to_sink():
    from jarvis.core.agent import EventSink

    ts = _toolset()
    specs = [AgentSpec("coder", "code", "you code", tools=["read_file"])]
    team = build_team(ts, {}, _Echo(), specs=specs)

    seen = []
    sink = EventSink()
    sink.callback = seen.append
    tools = make_delegate_tools(team, specs, sink=sink)
    by_name = {t.name: t for t in tools}

    by_name["delegate_to_agent"].run({"agent": "coder", "task": "do it"})
    # The specialist's final answer is relayed as tagged nested progress.
    assert any(e.kind == "thinking" and e.text.startswith("[coder]") for e in seen)


def test_delegate_parallel_runs_all_in_order():
    ts = _toolset()
    specs = [
        AgentSpec("coder", "code", "you code", tools=["read_file"]),
        AgentSpec("researcher", "research", "you research", tools=["ask_model"]),
    ]
    team = build_team(ts, {}, _Echo(), specs=specs)
    tools = {t.name: t for t in make_delegate_tools(team, specs)}

    out = tools["delegate_parallel"].run({"tasks": [
        {"agent": "coder", "task": "task-A"},
        {"agent": "researcher", "task": "task-B"},
    ]})
    # Both ran, results are labelled, and order is preserved.
    assert "[coder] done:task-A" in out
    assert "[researcher] done:task-B" in out
    assert out.index("[coder]") < out.index("[researcher]")


def test_delegate_parallel_isolates_errors():
    ts = _toolset()
    specs = [AgentSpec("coder", "code", "you code", tools=["read_file"])]
    team = build_team(ts, {}, _Echo(), specs=specs)
    tools = {t.name: t for t in make_delegate_tools(team, specs)}

    out = tools["delegate_parallel"].run({"tasks": [
        {"agent": "coder", "task": "ok"},
        {"agent": "ghost", "task": "fail"},
    ]})
    assert "[coder] done:ok" in out
    assert "unknown agent" in out  # bad task reported, batch still completes

    with pytest.raises(ToolError):
        tools["delegate_parallel"].run({"tasks": []})


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
