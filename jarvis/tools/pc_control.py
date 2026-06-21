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

    def get_screen_size() -> str:
        """Report the screen resolution so clicks can use valid coordinates."""
        pg = _require_pyautogui()
        w, h = pg.size()
        x, y = pg.position()
        return f"screen size: {w}x{h}; mouse at ({x}, {y})"

    def move_mouse(x: int, y: int, duration: float = 0.2) -> str:
        pg = _require_pyautogui()
        pg.moveTo(x, y, duration=duration)
        return f"moved mouse to ({x}, {y})"

    def click(x: int = -1, y: int = -1, button: str = "left", clicks: int = 1) -> str:
        pg = _require_pyautogui()
        if not gate.confirm(f"CLICK {button} x{clicks} at ({x},{y})"):
            raise ToolError("click denied by safety gate")
        # Move first, then click, so the OS reliably registers the event at the
        # target (a bare pg.click(x, y) can race the cursor move on Windows).
        if x >= 0 and y >= 0:
            pg.moveTo(x, y, duration=0.1)
            pg.click(x=x, y=y, clicks=clicks, button=button, interval=0.05)
        else:
            pg.click(clicks=clicks, button=button, interval=0.05)
        where = f" at ({x},{y})" if x >= 0 and y >= 0 else ""
        return f"clicked {button} {clicks}x{where}"

    def double_click(x: int = -1, y: int = -1, button: str = "left") -> str:
        return click(x=x, y=y, button=button, clicks=2)

    def right_click(x: int = -1, y: int = -1) -> str:
        return click(x=x, y=y, button="right", clicks=1)

    def scroll(amount: int, x: int = -1, y: int = -1) -> str:
        """Scroll vertically. Positive = up, negative = down."""
        pg = _require_pyautogui()
        if x >= 0 and y >= 0:
            pg.moveTo(x, y, duration=0.1)
        pg.scroll(amount)
        return f"scrolled {amount}"

    def drag_mouse(x: int, y: int, duration: float = 0.3,
                   button: str = "left") -> str:
        """Press and drag from the current position to (x, y)."""
        pg = _require_pyautogui()
        if not gate.confirm(f"DRAG to ({x},{y})"):
            raise ToolError("drag denied by safety gate")
        pg.dragTo(x, y, duration=duration, button=button)
        return f"dragged to ({x}, {y})"

    def click_image(image_path: str, confidence: float = 0.8,
                    button: str = "left", clicks: int = 1) -> str:
        """Find an on-screen image (a saved screenshot crop) and click it."""
        pg = _require_pyautogui()
        if not gate.confirm(f"CLICK image {image_path}"):
            raise ToolError("click denied by safety gate")
        try:
            location = pg.locateCenterOnScreen(image_path, confidence=confidence)
        except Exception as exc:  # noqa: BLE001 - needs opencv for confidence
            raise ToolError(
                f"could not locate image (install opencv-python for matching): {exc}"
            )
        if location is None:
            raise ToolError(f"image {image_path!r} not found on screen")
        pg.click(x=location.x, y=location.y, clicks=clicks, button=button)
        return f"clicked image at ({location.x}, {location.y})"

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
        Tool("get_screen_size",
             "Report the screen resolution and current mouse position. Call "
             "this before clicking so coordinates stay on-screen.",
             {"type": "object", "properties": {}},
             get_screen_size),
        Tool("move_mouse", "Move the mouse cursor to absolute screen coordinates.",
             {"type": "object",
              "properties": {"x": _int, "y": _int, "duration": {"type": "number"}},
              "required": ["x", "y"]},
             move_mouse),
        Tool("click",
             "Click the mouse at absolute screen coordinates (x, y). Omit x/y "
             "to click at the current position. Set clicks=2 for double-click "
             "and button='right' for a context menu.",
             {"type": "object",
              "properties": {"x": _int, "y": _int,
                             "button": {"type": "string", "enum": ["left", "right", "middle"]},
                             "clicks": _int}},
             click, dangerous=True),
        Tool("double_click",
             "Double-click at absolute screen coordinates (x, y).",
             {"type": "object",
              "properties": {"x": _int, "y": _int,
                             "button": {"type": "string", "enum": ["left", "right", "middle"]}}},
             double_click, dangerous=True),
        Tool("right_click",
             "Right-click at absolute screen coordinates (x, y) to open a "
             "context menu.",
             {"type": "object", "properties": {"x": _int, "y": _int}},
             right_click, dangerous=True),
        Tool("scroll",
             "Scroll the mouse wheel. Positive amount scrolls up, negative "
             "scrolls down. Optionally move to (x, y) first.",
             {"type": "object",
              "properties": {"amount": _int, "x": _int, "y": _int},
              "required": ["amount"]},
             scroll, dangerous=True),
        Tool("drag_mouse",
             "Press and drag from the current mouse position to (x, y).",
             {"type": "object",
              "properties": {"x": _int, "y": _int, "duration": {"type": "number"},
                             "button": {"type": "string", "enum": ["left", "right", "middle"]}},
              "required": ["x", "y"]},
             drag_mouse, dangerous=True),
        Tool("click_image",
             "Locate an image (a saved PNG crop of a button/icon) on screen "
             "and click its center. Needs opencv-python for the 'confidence' "
             "match.",
             {"type": "object",
              "properties": {"image_path": _str,
                             "confidence": {"type": "number"},
                             "button": {"type": "string", "enum": ["left", "right", "middle"]},
                             "clicks": _int},
              "required": ["image_path"]},
             click_image, dangerous=True),
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
