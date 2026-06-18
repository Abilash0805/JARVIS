"""Vision tools: let JARVIS look at the screen or an image file.

Backed by a free vision model (Groq's Llama-4-Scout or NVIDIA's vision NIM).
``see_screen`` captures a screenshot and describes it, which is what lets
JARVIS act on what's actually on screen rather than blind coordinates.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import TYPE_CHECKING

from jarvis.tools.base import Tool, ToolError

if TYPE_CHECKING:
    from jarvis.providers.openai_compatible import OpenAICompatibleProvider

_SCREENSHOT_DIR = os.path.expanduser("~/jarvis_screenshots")


def make_vision_tools(vision_provider: "OpenAICompatibleProvider") -> list[Tool]:
    def describe_image(path: str, question: str = "Describe this image in detail.") -> str:
        return vision_provider.describe_image(path, question)

    def see_screen(question: str = "Describe what is on the screen in detail.") -> str:
        try:
            import pyautogui
        except Exception as exc:  # noqa: BLE001
            raise ToolError(f"pyautogui unavailable for screenshot: {exc}")
        os.makedirs(_SCREENSHOT_DIR, exist_ok=True)
        path = os.path.join(_SCREENSHOT_DIR, f"see_{datetime.now():%Y%m%d_%H%M%S}.png")
        pyautogui.screenshot(path)
        return vision_provider.describe_image(path, question)

    _str = {"type": "string"}
    return [
        Tool(
            "see_screen",
            "Take a screenshot and have a vision model describe what is on the "
            "screen. Use this to understand the UI before clicking/typing.",
            {"type": "object", "properties": {"question": _str}},
            see_screen,
        ),
        Tool(
            "describe_image",
            "Describe or answer a question about an image file using a vision model.",
            {"type": "object",
             "properties": {"path": _str, "question": _str},
             "required": ["path"]},
            describe_image,
        ),
    ]
