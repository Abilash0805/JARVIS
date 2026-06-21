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
        # If the user closes the browser window (or it crashes), drop our
        # stale reference so the next call relaunches instead of repeatedly
        # raising "Target page, context or browser has been closed".
        self._context.on("close", lambda _ctx: self._reset())
        return self._context

    def page(self):
        try:
            ctx = self.start()
            pages = [p for p in ctx.pages if not p.is_closed()]
            return pages[0] if pages else ctx.new_page()
        except Exception:
            # Stale/closed context that didn't fire the close event in time
            # (crash, killed process) — relaunch once and retry.
            self._reset()
            ctx = self.start()
            return ctx.new_page()

    def _reset(self) -> None:
        self._context = None
        if self._pw is not None:
            try:
                self._pw.stop()
            except Exception:
                pass
            self._pw = None

    def close(self) -> None:
        if self._context is not None:
            self._context.close()
        self._reset()
