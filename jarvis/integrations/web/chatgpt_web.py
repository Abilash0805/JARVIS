"""Drive ChatGPT (chatgpt.com) in a real browser.

Like the Gemini backend, selectors may need occasional maintenance. ``ask``
returns ChatGPT's latest assistant message as text.
"""

from __future__ import annotations

import time
from typing import Optional

from jarvis.integrations.web.browser import BrowserSession

_URL = "https://chatgpt.com/"


class ChatGPTWeb:
    name = "chatgpt"

    def __init__(self, session: Optional[BrowserSession] = None) -> None:
        self.session = session or BrowserSession(headless=False)

    def ask(self, prompt: str, timeout_s: int = 120) -> str:
        page = self.session.page()
        if not page.url.startswith("https://chatgpt.com"):
            page.goto(_URL, wait_until="domcontentloaded")

        editor = page.locator("#prompt-textarea, textarea[data-id], div[contenteditable='true']").first
        editor.wait_for(state="visible", timeout=30_000)
        editor.click()
        editor.fill("") if editor.evaluate("el => el.tagName") == "TEXTAREA" else None
        editor.type(prompt, delay=8)
        page.keyboard.press("Enter")

        return _wait_for_assistant_message(page, timeout_s)


def _wait_for_assistant_message(page, timeout_s: int) -> str:
    selector = "[data-message-author-role='assistant']"
    deadline = time.time() + timeout_s
    last_text = ""
    stable_for = 0.0
    # Wait for a stop/regenerate state by detecting stable text on the last node.
    while time.time() < deadline:
        nodes = page.locator(selector)
        count = nodes.count()
        if count:
            text = (nodes.nth(count - 1).inner_text() or "").strip()
            if text and text == last_text:
                stable_for += 0.8
                if stable_for >= 2.4:
                    return text
            else:
                stable_for = 0.0
                last_text = text
        time.sleep(0.8)
    return last_text or "(no response captured before timeout)"
