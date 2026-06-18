"""Generic desktop-app driver via window focus + keyboard automation."""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass


@dataclass
class DesktopApp:
    """Drive a desktop app by launching, focusing and typing into it.

    This is deliberately generic: ``send_prompt`` focuses the window, types the
    text and presses Enter. It cannot reliably *read back* a desktop app's
    answer (no DOM), so use it to drive apps, and prefer the API/web backends
    when you need the model's reply as text.
    """

    name: str
    window_title: str
    launch_target: str

    def open(self) -> str:
        subprocess.Popen(f'start "" "{self.launch_target}"', shell=True)
        return f"launched {self.name}"

    def focus(self) -> str:
        import pygetwindow as gw  # raises if no desktop session

        for title in gw.getAllTitles():
            if self.window_title.lower() in title.lower():
                win = gw.getWindowsWithTitle(title)[0]
                if win.isMinimized:
                    win.restore()
                win.activate()
                return f"focused {title}"
        # Not open yet — launch and wait briefly.
        self.open()
        time.sleep(4)
        return self.focus()

    def send_prompt(self, prompt: str) -> str:
        import pyautogui

        self.focus()
        time.sleep(0.6)
        pyautogui.typewrite(prompt, interval=0.01)
        pyautogui.press("enter")
        return f"sent prompt to {self.name}"


class ClaudeDesktop(DesktopApp):
    def __init__(self) -> None:
        super().__init__(
            name="claude-desktop",
            window_title="Claude",
            launch_target="claude",
        )


class CursorDesktop(DesktopApp):
    def __init__(self) -> None:
        super().__init__(
            name="cursor-desktop",
            window_title="Cursor",
            launch_target="cursor",
        )
