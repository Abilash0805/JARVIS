"""Drive Gemini (gemini.google.com) in a real browser.

Selectors on Google properties change often; they are centralised here and may
need occasional updates. ``ask`` returns Gemini's latest reply as text.
"""

from __future__ import annotations

import time
from typing import Optional

from jarvis.integrations.web.browser import BrowserSession

_URL = "https://gemini.google.com/app"


class GeminiWeb:
    name = "gemini"

    def __init__(self, session: Optional[BrowserSession] = None) -> None:
        self.session = session or BrowserSession(headless=False)

    def ask(self, prompt: str, timeout_s: int = 90) -> str:
        page = self.session.page()
        if not page.url.startswith("https://gemini.google.com"):
            page.goto(_URL, wait_until="domcontentloaded")

        # The composer is a rich-text contenteditable.
        editor = page.locator("div[contenteditable='true']").first
        editor.wait_for(state="visible", timeout=30_000)
        editor.click()
        editor.fill("")
        editor.type(prompt, delay=10)
        page.keyboard.press("Enter")

        return _wait_for_reply(page, "message-content, .model-response-text", timeout_s)


def _wait_for_reply(page, selector: str, timeout_s: int) -> str:
    """Poll the last response node until its text stops growing."""
    deadline = time.time() + timeout_s
    last_text = ""
    stable_for = 0.0
    while time.time() < deadline:
        nodes = page.locator(selector)
        count = nodes.count()
        if count:
            text = (nodes.nth(count - 1).inner_text() or "").strip()
            if text and text == last_text:
                stable_for += 0.8
                if stable_for >= 2.4:  # text unchanged ~2.4s => done
                    return text
            else:
                stable_for = 0.0
                last_text = text
        time.sleep(0.8)
    return last_text or "(no response captured before timeout)"
