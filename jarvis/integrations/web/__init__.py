"""Browser-driven AI backends (Gemini, ChatGPT) via Playwright."""

from jarvis.integrations.web.gemini_web import GeminiWeb
from jarvis.integrations.web.chatgpt_web import ChatGPTWeb

__all__ = ["GeminiWeb", "ChatGPTWeb"]
