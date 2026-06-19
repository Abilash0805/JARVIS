"""Tests for routing fallback and long-term memory (headless, no keys)."""

import tempfile
from pathlib import Path

from jarvis.core.longterm import LongTermMemory
from jarvis.providers.base import ChatMessage, LLMProvider, ProviderError, ProviderResponse
from jarvis.providers.router import RoutingProvider


class _FakeProvider(LLMProvider):
    def __init__(self, name, *, fail_with=None, reply="ok"):
        self.name = name
        self.model = f"{name}-model"
        self.supports_tools = True
        self._fail_with = fail_with
        self._reply = reply

    def chat(self, messages, *, tools=None, temperature=0.7, max_tokens=None, **kw):
        if self._fail_with:
            raise ProviderError(self._fail_with)
        return ProviderResponse(content=self._reply)


def test_router_falls_back_on_rate_limit():
    primary = _FakeProvider("groq", fail_with="HTTP 429: rate limit exceeded")
    backup = _FakeProvider("mistral", reply="from mistral")
    router = RoutingProvider([primary, backup], primary="groq")

    resp = router.chat([ChatMessage.user("hi")])
    assert resp.content == "from mistral"
    assert router.active_name == "mistral"


def test_router_raises_when_all_fail():
    a = _FakeProvider("a", fail_with="429 rate limit")
    b = _FakeProvider("b", fail_with="503 overloaded")
    router = RoutingProvider([a, b])
    try:
        router.chat([ChatMessage.user("hi")])
        assert False, "expected ProviderError"
    except ProviderError as exc:
        assert "all providers failed" in str(exc)


def test_router_orders_primary_first():
    a = _FakeProvider("a", reply="a")
    b = _FakeProvider("b", reply="b")
    router = RoutingProvider([a, b], primary="b")
    assert router.chat([ChatMessage.user("x")]).content == "b"


def test_longterm_remember_recall_forget():
    with tempfile.TemporaryDirectory() as d:
        store = LongTermMemory(db_path=str(Path(d) / "m.db"))
        mid = store.remember("user prefers dark mode", tag="preference")
        rows = store.recall(query="dark")
        assert rows and rows[0][2] == "user prefers dark mode"
        assert store.recall(tag="preference")
        assert store.forget(mid) is True
        assert store.recall(query="dark") == []
        store.close()
