"""Smoke tests that run headless (no API keys, no desktop)."""

import json

from jarvis.providers.base import ChatMessage, ProviderResponse, ToolCall
from jarvis.providers.openai_compatible import OpenAICompatibleProvider
from jarvis.tools.base import Tool, Toolset
from jarvis.utils.safety import SafetyGate


def test_chatmessage_roundtrip():
    msg = ChatMessage.user("hello")
    assert msg.to_dict() == {"role": "user", "content": "hello"}

    tc = ToolCall(id="1", name="foo", arguments='{"a":1}')
    assistant = ChatMessage(role="assistant", content=None, tool_calls=[tc])
    d = assistant.to_dict()
    assert d["tool_calls"][0]["function"]["name"] == "foo"


def test_provider_parse_tool_calls():
    data = {
        "choices": [
            {
                "finish_reason": "tool_calls",
                "message": {
                    "content": None,
                    "tool_calls": [
                        {"id": "x", "type": "function",
                         "function": {"name": "run_command", "arguments": "{}"}}
                    ],
                },
            }
        ]
    }
    resp = OpenAICompatibleProvider._parse(data)
    assert isinstance(resp, ProviderResponse)
    assert resp.wants_tools
    assert resp.tool_calls[0].name == "run_command"


def test_toolset_execute_and_safety():
    gate = SafetyGate(require_confirmation=False)
    calls = []

    def echo(text: str) -> str:
        calls.append(text)
        return f"echoed:{text}"

    ts = Toolset()
    ts.add(Tool("echo", "echo text", {
        "type": "object", "properties": {"text": {"type": "string"}},
        "required": ["text"]}, echo))

    out = ts.execute("echo", json.dumps({"text": "hi"}))
    assert out == "echoed:hi"
    assert ts.execute("missing", "{}").startswith("ERROR: unknown tool")
    # Hard blocklist never proceeds even with confirmation disabled.
    assert gate.confirm("safe action") is True
    assert SafetyGate(require_confirmation=False).is_hard_blocked("rm -rf /") is True


def test_specs_render():
    gate = SafetyGate(require_confirmation=False)
    from jarvis.tools.registry import default_toolset

    ts = default_toolset(gate, include_pc_control=True)
    specs = ts.specs()
    assert all(s["type"] == "function" for s in specs)
    names = {s["function"]["name"] for s in specs}
    assert {"read_file", "run_command", "system_info", "open_app"} <= names
    # Document builders are always available.
    assert {"create_pptx", "create_pdf", "create_website"} <= names


def test_autonomous_by_default():
    # Default gate does not prompt and lets actions proceed.
    gate = SafetyGate()
    assert gate.require_confirmation is False
    assert gate.confirm("WRITE file /tmp/x") is True
    # ...but still blocks catastrophic commands.
    assert gate.confirm("rm -rf /") is False
    # Disabling the blocklist removes even that guard.
    open_gate = SafetyGate(enforce_blocklist=False)
    assert open_gate.confirm("rm -rf /") is True
