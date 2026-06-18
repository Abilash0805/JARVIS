"""Build optional integration backends without hard failures."""

from __future__ import annotations

import os

from jarvis.utils.logging import get_logger

logger = get_logger("jarvis.integrations")


def build_web_backends() -> dict[str, object]:
    """Construct browser AI backends if playwright + a desktop are available.

    Controlled by env: set ``JARVIS_ENABLE_WEB=false`` to skip entirely. Each
    backend shares one browser session so a single window hosts both.
    """
    if os.getenv("JARVIS_ENABLE_WEB", "true").lower() == "false":
        return {}
    try:
        import playwright  # noqa: F401
    except ImportError:
        logger.info("playwright not installed; Gemini/ChatGPT web disabled")
        return {}

    try:
        from jarvis.integrations.web.browser import BrowserSession
        from jarvis.integrations.web.chatgpt_web import ChatGPTWeb
        from jarvis.integrations.web.gemini_web import GeminiWeb

        session = BrowserSession(headless=False)
        return {
            "gemini": GeminiWeb(session=session),
            "chatgpt": ChatGPTWeb(session=session),
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("could not init web backends: %s", exc)
        return {}
