"""Keyboard, mouse, screenshot and window control.

Depends on ``pyautogui`` / ``pygetwindow`` / ``pyperclip``, which require a
desktop session. Imports are lazy so the rest of JARVIS works headless; if the
libraries are missing the tools return a helpful message instead of crashing.
"""

from __future__ import annotations

import os
from datetime import datetime

from jarvis.tools.base import Tool, ToolError
from jarvis.utils.safety import SafetyGate

_SCREENSHOT_DIR = os.path.expanduser("~/jarvis_screenshots")


def _require_pyautogui():
    try:
        import pyautogui

        # Fail-safe: slamming the mouse into a corner aborts automation.
        pyautogui.FAILSAFE = True
        return pyautogui
    except Exception as exc:  # noqa: BLE001
        raise ToolError(
            "pyautogui unavailable (need a desktop session and "
            f"`pip install pyautogui`): {exc}"
        )


def make_pc_control_tools(gate: SafetyGate) -> list[Tool]:
    def screenshot(region: str = "") -> str:
        pg = _require_pyautogui()
        os.makedirs(_SCREENSHOT_DIR, exist_ok=True)
        path = os.path.join(
            _SCREENSHOT_DIR, f"shot_{datetime.now():%Y%m%d_%H%M%S}.png"
        )
        kwargs = {}
        if region:
            try:
                x, y, w, h = (int(v) for v in region.split(","))
                kwargs["region"] = (x, y, w, h)
            except ValueError:
                raise ToolError("region must be 'x,y,width,height'")
        pg.screenshot(path, **kwargs)
        return f"saved screenshot to {path}"

    def move_mouse(x: int, y: int, duration: float = 0.2) -> str:
        pg = _require_pyautogui()
        pg.moveTo(x, y, duration=duration)
        return f"moved mouse to ({x}, {y})"

    def click(x: int = -1, y: int = -1, button: str = "left", clicks: int = 1) -> str:
        pg = _require_pyautogui()
        if not gate.confirm(f"CLICK {button} x{clicks} at ({x},{y})"):
            raise ToolError("click denied by safety gate")
        if x >= 0 and y >= 0:
            pg.click(x=x, y=y, clicks=clicks, button=button)
        else:
            pg.click(clicks=clicks, button=button)
        return f"clicked {button} {clicks}x"

    def type_text(text: str, interval: float = 0.02) -> str:
        pg = _require_pyautogui()
        if not gate.confirm(f"TYPE text ({len(text)} chars)"):
            raise ToolError("typing denied by safety gate")
        pg.typewrite(text, interval=interval)
        return f"typed {len(text)} chars"

    def press_keys(keys: str) -> str:
        """Press a hotkey combo like 'ctrl,c' or a single key like 'enter'."""
        pg = _require_pyautogui()
        combo = [k.strip() for k in keys.split(",") if k.strip()]
        if not combo:
            raise ToolError("no keys given")
        if not gate.confirm(f"PRESS keys {'+'.join(combo)}"):
            raise ToolError("keypress denied by safety gate")
        if len(combo) == 1:
            pg.press(combo[0])
        else:
            pg.hotkey(*combo)
        return f"pressed {'+'.join(combo)}"

    def set_clipboard(text: str) -> str:
        try:
            import pyperclip

            pyperclip.copy(text)
            return f"copied {len(text)} chars to clipboard"
        except Exception as exc:  # noqa: BLE001
            raise ToolError(f"clipboard unavailable: {exc}")

    def get_clipboard() -> str:
        try:
            import pyperclip

            return pyperclip.paste()
        except Exception as exc:  # noqa: BLE001
            raise ToolError(f"clipboard unavailable: {exc}")

    _int = {"type": "integer"}
    _str = {"type": "string"}
    return [
        Tool("screenshot",
             "Capture the screen (or a region 'x,y,width,height') to a PNG file.",
             {"type": "object", "properties": {"region": _str}},
             screenshot),
        Tool("move_mouse", "Move the mouse cursor to absolute screen coordinates.",
             {"type": "object",
              "properties": {"x": _int, "y": _int, "duration": {"type": "number"}},
              "required": ["x", "y"]},
             move_mouse),
        Tool("click",
             "Click the mouse. Omit x/y to click at the current position.",
             {"type": "object",
              "properties": {"x": _int, "y": _int,
                             "button": {"type": "string", "enum": ["left", "right", "middle"]},
                             "clicks": _int}},
             click, dangerous=True),
        Tool("type_text", "Type a string of text at the keyboard focus.",
             {"type": "object",
              "properties": {"text": _str, "interval": {"type": "number"}},
              "required": ["text"]},
             type_text, dangerous=True),
        Tool("press_keys",
             "Press a key or hotkey combo. Comma-separated, e.g. 'ctrl,c' or 'enter'.",
             {"type": "object", "properties": {"keys": _str}, "required": ["keys"]},
             press_keys, dangerous=True),
        Tool("set_clipboard", "Put text on the system clipboard.",
             {"type": "object", "properties": {"text": _str}, "required": ["text"]},
             set_clipboard),
        Tool("get_clipboard", "Read the current system clipboard text.",
             {"type": "object", "properties": {}},
             get_clipboard),
    ]
