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

# Friendly app name -> the process/executable name used to terminate it. Lets
# the user say "close chrome" instead of needing to know it is "chrome.exe".
_PROCESS_ALIASES: dict[str, str] = {
    "claude": "Claude.exe",
    "cursor": "Cursor.exe",
    "chrome": "chrome.exe",
    "notepad": "notepad.exe",
    "explorer": "explorer.exe",
    "terminal": "WindowsTerminal.exe",
    "code": "Code.exe",
    "vscode": "Code.exe",
}

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


def _terminate_by_name(name: str) -> str:
    """Terminate every process whose name matches ``name`` (alias-aware).

    Prefers ``psutil`` (cross-platform, graceful terminate then kill); falls
    back to the OS killer (``taskkill`` / ``pkill``) when psutil is missing.
    """
    target = _PROCESS_ALIASES.get(name.lower(), name)
    base = target.lower()
    # Compare on the name with and without a trailing ``.exe`` so "chrome" and
    # "chrome.exe" both match a running ``chrome.exe``.
    wanted = {base, base[:-4] if base.endswith(".exe") else base + ".exe"}

    try:
        import psutil
    except Exception:  # noqa: BLE001 - psutil optional, fall back below
        psutil = None

    if psutil is not None:
        killed = 0
        for proc in psutil.process_iter(["name"]):
            pname = (proc.info.get("name") or "").lower()
            if pname in wanted:
                try:
                    proc.terminate()
                    killed += 1
                except Exception:  # noqa: BLE001 - already gone / no permission
                    continue
        if killed:
            # Give them a moment to exit, then hard-kill stragglers.
            gone, alive = psutil.wait_procs(
                [p for p in psutil.process_iter(["name"])
                 if (p.info.get("name") or "").lower() in wanted],
                timeout=3,
            )
            for proc in alive:
                try:
                    proc.kill()
                except Exception:  # noqa: BLE001
                    continue
            return f"closed {killed} '{target}' process(es)"
        raise ToolError(f"no running process named {target!r}")

    # No psutil: shell out to the platform killer.
    if platform.system() == "Windows":
        result = subprocess.run(
            ["taskkill", "/F", "/IM", target if target.lower().endswith(".exe")
             else target + ".exe"],
            capture_output=True, text=True,
        )
    else:
        result = subprocess.run(["pkill", "-f", target],
                                capture_output=True, text=True)
    if result.returncode == 0:
        return f"closed {target}"
    raise ToolError(
        f"could not close {target!r}: {result.stderr.strip() or 'not found'}"
    )


def make_app_tools(gate: SafetyGate) -> list[Tool]:
    is_windows = platform.system() == "Windows"

    def open_app(name: str) -> str:
        if not gate.confirm(f"LAUNCH application: {name}"):
            raise ToolError("launch denied by safety gate")
        if is_windows:
            return _launch_windows(name)
        return _launch_posix(name)

    def close_app(name: str) -> str:
        """Terminate an application by name (e.g. 'chrome', 'notepad')."""
        if not gate.confirm(f"CLOSE application: {name}"):
            raise ToolError("close denied by safety gate")
        return _terminate_by_name(name)

    def close_window(title_contains: str) -> str:
        """Gracefully close the window whose title contains ``title_contains``."""
        if not gate.confirm(f"CLOSE window: {title_contains}"):
            raise ToolError("close denied by safety gate")
        try:
            import pygetwindow as gw
        except Exception as exc:  # noqa: BLE001
            raise ToolError(f"pygetwindow unavailable: {exc}")
        matches = gw.getWindowsWithTitle(title_contains)
        if not matches:
            matches = [
                gw.getWindowsWithTitle(t)[0]
                for t in gw.getAllTitles()
                if title_contains.lower() in t.lower()
            ]
        if not matches:
            raise ToolError(f"no window matching {title_contains!r}")
        win = matches[0]
        title = win.title
        try:
            win.close()
        except Exception as exc:  # noqa: BLE001 - platform quirks
            raise ToolError(f"could not close window: {exc}")
        return f"closed window: {title}"

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
            "close_app",
            "Close/quit a running application by name (terminates its "
            "process). Known shortcuts: claude, cursor, chrome, notepad, "
            "explorer, terminal, code. Use this to 'close', 'quit' or 'kill' "
            "an app. For a single window, prefer close_window.",
            {"type": "object", "properties": {"name": _str}, "required": ["name"]},
            close_app, dangerous=True,
        ),
        Tool(
            "close_window",
            "Gracefully close a single window by a substring of its title "
            "(sends the normal close request, like clicking the X).",
            {"type": "object",
             "properties": {"title_contains": _str},
             "required": ["title_contains"]},
            close_window, dangerous=True,
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
