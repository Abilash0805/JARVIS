"""Conversation memory with optional on-disk persistence.

Keeps the running message list for the agent loop and can save/load a JSON
transcript so sessions survive restarts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from jarvis.providers.base import ChatMessage, ToolCall


class Memory:
    def __init__(self, system_prompt: str, max_messages: int = 200) -> None:
        self._system = ChatMessage.system(system_prompt)
        self.max_messages = max_messages
        self._messages: list[ChatMessage] = []

    def add(self, message: ChatMessage) -> None:
        self._messages.append(message)
        self._truncate()

    def add_user(self, content: str) -> None:
        self.add(ChatMessage.user(content))

    def history(self) -> list[ChatMessage]:
        """Full message list including the system prompt at position 0."""
        return [self._system, *self._messages]

    def _truncate(self) -> None:
        # Keep the most recent messages; the system prompt is stored separately.
        if len(self._messages) > self.max_messages:
            self._messages = self._messages[-self.max_messages :]

    # --- persistence -----------------------------------------------------
    def save(self, path: str | Path) -> None:
        data = [_message_to_json(m) for m in self._messages]
        Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")

    def load(self, path: str | Path) -> None:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        self._messages = [_message_from_json(d) for d in raw]
        self._truncate()


def _message_to_json(m: ChatMessage) -> dict:
    return {
        "role": m.role,
        "content": m.content,
        "tool_calls": [tc.to_dict() for tc in m.tool_calls],
        "tool_call_id": m.tool_call_id,
        "name": m.name,
    }


def _message_from_json(d: dict) -> ChatMessage:
    tool_calls = [
        ToolCall(id=tc["id"], name=tc["function"]["name"], arguments=tc["function"]["arguments"])
        for tc in d.get("tool_calls") or []
    ]
    return ChatMessage(
        role=d["role"],
        content=d.get("content"),
        tool_calls=tool_calls,
        tool_call_id=d.get("tool_call_id"),
        name=d.get("name"),
    )
