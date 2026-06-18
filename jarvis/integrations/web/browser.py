"""Shared Playwright browser session with a persistent profile.

A persistent context means you log in to Gemini/ChatGPT once (in the launched
browser window) and the session is reused on later runs. Headless is off by
default so you can complete logins / captchas.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

_PROFILE_DIR = os.path.expanduser("~/.jarvis/browser_profile")


class BrowserSession:
    """Lazily-started Playwright Chromium with a persistent profile."""

    def __init__(self, headless: bool = False, profile_dir: Optional[str] = None) -> None:
        self.headless = headless
        self.profile_dir = profile_dir or _PROFILE_DIR
        self._pw = None
        self._context = None

    def start(self):
        if self._context is not None:
            return self._context
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "playwright not installed. Run `pip install playwright` and "
                "`playwright install chromium`."
            ) from exc

        Path(self.profile_dir).mkdir(parents=True, exist_ok=True)
        self._pw = sync_playwright().start()
        self._context = self._pw.chromium.launch_persistent_context(
            self.profile_dir,
            headless=self.headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        return self._context

    def page(self):
        ctx = self.start()
        if ctx.pages:
            return ctx.pages[0]
        return ctx.new_page()

    def close(self) -> None:
        if self._context is not None:
            self._context.close()
            self._context = None
        if self._pw is not None:
            self._pw.stop()
            self._pw = None
