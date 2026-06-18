"""Persistent long-term memory backed by local SQLite (free, offline).

Stores tagged notes/facts JARVIS chooses to remember across sessions, with a
simple substring search for recall. The database lives at ``~/.jarvis/memory.db``.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

_DEFAULT_DB = os.path.expanduser("~/.jarvis/memory.db")


class LongTermMemory:
    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or _DEFAULT_DB
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memories (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                tag       TEXT    NOT NULL DEFAULT 'note',
                content   TEXT    NOT NULL,
                created   TEXT    NOT NULL
            )
            """
        )
        self._conn.commit()

    def remember(self, content: str, tag: str = "note") -> int:
        cur = self._conn.execute(
            "INSERT INTO memories (tag, content, created) VALUES (?, ?, ?)",
            (tag, content, datetime.now(timezone.utc).isoformat(timespec="seconds")),
        )
        self._conn.commit()
        return int(cur.lastrowid)

    def recall(self, query: str = "", tag: str = "", limit: int = 10) -> list[tuple]:
        sql = "SELECT id, tag, content, created FROM memories"
        clauses, params = [], []
        if query:
            clauses.append("content LIKE ?")
            params.append(f"%{query}%")
        if tag:
            clauses.append("tag = ?")
            params.append(tag)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(int(limit))
        return list(self._conn.execute(sql, params).fetchall())

    def forget(self, memory_id: int) -> bool:
        cur = self._conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        self._conn.commit()
        return cur.rowcount > 0

    def close(self) -> None:
        self._conn.close()
