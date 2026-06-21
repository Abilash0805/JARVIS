"""File-system tools: read, write, append, list, and delete files.

By default these tools can touch any path the OS user running JARVIS can
touch — there's no sandbox. If you want JARVIS confined to a working
directory (recommended when running autonomously), set ``JARVIS_FS_ROOT`` to
a directory; every path is then resolved and checked to be inside it before
any read/write/delete proceeds.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from jarvis.tools.base import Tool, ToolError
from jarvis.utils.safety import SafetyGate

_MAX_READ_BYTES = 200_000


def _resolve(path: str) -> Path:
    return Path(os.path.expanduser(path)).resolve()


def _fs_root() -> Optional[Path]:
    raw = os.getenv("JARVIS_FS_ROOT", "").strip()
    if not raw:
        return None
    return Path(os.path.expanduser(raw)).resolve()


def _check_confined(p: Path, root: Optional[Path]) -> None:
    if root is None:
        return
    try:
        p.relative_to(root)
    except ValueError:
        raise ToolError(
            f"path {p} is outside the confined workspace {root} "
            "(JARVIS_FS_ROOT is set)"
        )


def make_filesystem_tools(gate: SafetyGate) -> list[Tool]:
    root = _fs_root()

    def read_file(path: str) -> str:
        p = _resolve(path)
        _check_confined(p, root)
        if not p.is_file():
            raise ToolError(f"not a file: {p}")
        data = p.read_bytes()[:_MAX_READ_BYTES]
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            return f"<binary file, {p.stat().st_size} bytes>"

    def list_dir(path: str = ".") -> str:
        p = _resolve(path)
        _check_confined(p, root)
        if not p.is_dir():
            raise ToolError(f"not a directory: {p}")
        entries = []
        for child in sorted(p.iterdir()):
            kind = "dir " if child.is_dir() else "file"
            size = child.stat().st_size if child.is_file() else "-"
            entries.append(f"{kind} {size:>10} {child.name}")
        return "\n".join(entries) or "<empty>"

    def write_file(path: str, content: str) -> str:
        p = _resolve(path)
        _check_confined(p, root)
        if not gate.confirm(f"WRITE file {p} ({len(content)} chars)"):
            raise ToolError("write denied by safety gate")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"wrote {len(content)} chars to {p}"

    def append_file(path: str, content: str) -> str:
        p = _resolve(path)
        _check_confined(p, root)
        if not gate.confirm(f"APPEND to file {p} ({len(content)} chars)"):
            raise ToolError("append denied by safety gate")
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            fh.write(content)
        return f"appended {len(content)} chars to {p}"

    def delete_file(path: str) -> str:
        p = _resolve(path)
        _check_confined(p, root)
        if not p.exists():
            raise ToolError(f"does not exist: {p}")
        if not gate.confirm(f"DELETE {p}"):
            raise ToolError("delete denied by safety gate")
        if p.is_dir():
            raise ToolError("refusing to delete a directory; delete files individually")
        p.unlink()
        return f"deleted {p}"

    _str = {"type": "string"}
    return [
        Tool(
            "read_file", "Read a UTF-8 text file and return its contents.",
            {"type": "object", "properties": {"path": _str}, "required": ["path"]},
            read_file,
        ),
        Tool(
            "list_dir", "List the entries of a directory.",
            {"type": "object", "properties": {"path": _str}},
            list_dir,
        ),
        Tool(
            "write_file", "Create or overwrite a text file with the given content.",
            {"type": "object",
             "properties": {"path": _str, "content": _str},
             "required": ["path", "content"]},
            write_file, dangerous=True,
        ),
        Tool(
            "append_file", "Append text to a file (creates it if missing).",
            {"type": "object",
             "properties": {"path": _str, "content": _str},
             "required": ["path", "content"]},
            append_file, dangerous=True,
        ),
        Tool(
            "delete_file", "Delete a single file.",
            {"type": "object", "properties": {"path": _str}, "required": ["path"]},
            delete_file, dangerous=True,
        ),
    ]
