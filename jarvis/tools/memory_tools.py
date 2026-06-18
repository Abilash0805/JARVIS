"""Tools that expose long-term memory to the agent."""

from __future__ import annotations

from jarvis.core.longterm import LongTermMemory
from jarvis.tools.base import Tool


def make_memory_tools(store: LongTermMemory) -> list[Tool]:
    def remember(content: str, tag: str = "note") -> str:
        mem_id = store.remember(content, tag=tag)
        return f"remembered #{mem_id} [{tag}]"

    def recall(query: str = "", tag: str = "", limit: int = 10) -> str:
        rows = store.recall(query=query, tag=tag, limit=limit)
        if not rows:
            return "no matching memories"
        return "\n".join(f"#{r[0]} [{r[1]}] {r[2]}" for r in rows)

    def forget(memory_id: int) -> str:
        return "forgotten" if store.forget(memory_id) else "no such memory"

    _str = {"type": "string"}
    return [
        Tool(
            "remember",
            "Save a fact, preference, or note to long-term memory so you recall "
            "it in future sessions. Use a tag like 'preference' or 'fact'.",
            {"type": "object",
             "properties": {"content": _str, "tag": _str},
             "required": ["content"]},
            remember,
        ),
        Tool(
            "recall",
            "Search long-term memory. Optionally filter by query substring and tag.",
            {"type": "object",
             "properties": {"query": _str, "tag": _str, "limit": {"type": "integer"}}},
            recall,
        ),
        Tool(
            "forget", "Delete a memory by its id.",
            {"type": "object",
             "properties": {"memory_id": {"type": "integer"}},
             "required": ["memory_id"]},
            forget,
        ),
    ]
