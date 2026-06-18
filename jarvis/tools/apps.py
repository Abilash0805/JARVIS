"""Launch, focus and list desktop applications.

Includes shortcuts for the apps the user cares about (Claude desktop, Cursor),
plus generic launch-by-name. Window focusing uses pygetwindow when available.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess

from jarvis.tools.base import Tool, ToolError
from jarvis.utils.safety import SafetyGate

# Best-effort launch hints per known app. On Windows these are resolved against
# the usual install locations / PATH; users can override via the config file.
_WINDOWS_APP_HINTS: dict[str, list[str]] = {
    "claude": [
        os.path.expandvars(r"%LOCALAPPDATA%\AnthropicClaude\Claude.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\claude\Claude.exe"),
        "claude",
    ],
    "cursor": [
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\cursor\Cursor.exe"),
        "cursor",
    ],
    "chrome": [
        os.path.expandvars(r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe"),
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        "chrome",
    ],
    "notepad": ["notepad.exe"],
    "explorer": ["explorer.exe"],
    "terminal": ["wt.exe", "powershell.exe", "cmd.exe"],
}


def _launch_windows(target: str) -> str:
    hints = _WINDOWS_APP_HINTS.get(target.lower())
    candidates = hints if hints else [target]
    for candidate in candidates:
        if os.path.isfile(candidate) or shutil.which(candidate):
            subprocess.Popen([candidate], shell=False)
            return f"launched {candidate}"
    # Last resort: hand it to the shell (handles UWP aliases & PATH apps).
    subprocess.Popen(f'start "" "{target}"', shell=True)
    return f"asked Windows to start {target}"


def _launch_posix(target: str) -> str:
    system = platform.system()
    if system == "Darwin":
        subprocess.Popen(["open", "-a", target])
        return f"opened {target} (macOS)"
    # Linux
    if shutil.which(target):
        subprocess.Popen([target])
        return f"launched {target}"
    subprocess.Popen(["xdg-open", target])
    return f"xdg-open {target}"


def make_app_tools(gate: SafetyGate) -> list[Tool]:
    is_windows = platform.system() == "Windows"

    def open_app(name: str) -> str:
        if not gate.confirm(f"LAUNCH application: {name}"):
            raise ToolError("launch denied by safety gate")
        if is_windows:
            return _launch_windows(name)
        return _launch_posix(name)

    def list_windows() -> str:
        try:
            import pygetwindow as gw
        except Exception as exc:  # noqa: BLE001
            raise ToolError(f"pygetwindow unavailable: {exc}")
        titles = [t for t in gw.getAllTitles() if t.strip()]
        return "\n".join(titles) or "<no visible windows>"

    def focus_window(title_contains: str) -> str:
        try:
            import pygetwindow as gw
        except Exception as exc:  # noqa: BLE001
            raise ToolError(f"pygetwindow unavailable: {exc}")
        matches = gw.getWindowsWithTitle(title_contains)
        if not matches:
            # Fall back to a fuzzy contains match.
            matches = [
                gw.getWindowsWithTitle(t)[0]
                for t in gw.getAllTitles()
                if title_contains.lower() in t.lower()
            ]
        if not matches:
            raise ToolError(f"no window matching {title_contains!r}")
        win = matches[0]
        try:
            if win.isMinimized:
                win.restore()
            win.activate()
        except Exception as exc:  # noqa: BLE001 - platform quirks
            raise ToolError(f"could not focus window: {exc}")
        return f"focused window: {win.title}"

    _str = {"type": "string"}
    return [
        Tool(
            "open_app",
            "Launch a desktop application by name. Known shortcuts: claude, "
            "cursor, chrome, notepad, explorer, terminal. Any other name is "
            "resolved against PATH / the OS launcher.",
            {"type": "object", "properties": {"name": _str}, "required": ["name"]},
            open_app, dangerous=True,
        ),
        Tool(
            "list_windows", "List the titles of all open windows.",
            {"type": "object", "properties": {}},
            list_windows,
        ),
        Tool(
            "focus_window", "Bring a window to the foreground by a title substring.",
            {"type": "object",
             "properties": {"title_contains": _str},
             "required": ["title_contains"]},
            focus_window,
        ),
    ]
