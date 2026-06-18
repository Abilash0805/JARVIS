"""Let JARVIS delegate a subtask to another model or web AI.

This is what makes JARVIS a *router*: its core brain can hand a prompt to
Gemini/ChatGPT (browser) or to any configured API provider and use the answer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from jarvis.providers.base import ChatMessage
from jarvis.tools.base import Tool, ToolError

if TYPE_CHECKING:
    from jarvis.providers.base import LLMProvider


def make_ai_delegate_tools(
    api_providers: dict[str, "LLMProvider"],
    web_backends: dict[str, object] | None = None,
) -> list[Tool]:
    web_backends = web_backends or {}

    def ask_model(provider: str, prompt: str) -> str:
        name = provider.lower().strip()
        if name in api_providers:
            resp = api_providers[name].chat(
                [ChatMessage.user(prompt)], temperature=0.7
            )
            return resp.content or "<no content>"
        if name in web_backends:
            backend = web_backends[name]
            ask = getattr(backend, "ask", None)
            if ask is None:
                raise ToolError(f"web backend {name!r} has no ask() method")
            return ask(prompt)
        raise ToolError(
            f"unknown provider {provider!r}. available: "
            f"{sorted(set(api_providers) | set(web_backends))}"
        )

    def list_models() -> str:
        lines = []
        for n, p in api_providers.items():
            lines.append(f"{n} (api) -> {getattr(p, 'model', '?')}")
        for n in web_backends:
            lines.append(f"{n} (web)")
        return "\n".join(lines) or "<no models configured>"

    choices = sorted(set(api_providers) | set(web_backends))
    return [
        Tool(
            "ask_model",
            "Delegate a question/subtask to another AI model and return its "
            "answer. Use this to consult Gemini, ChatGPT, or a specific API "
            "model when it is better suited than your own reasoning.",
            {
                "type": "object",
                "properties": {
                    "provider": {
                        "type": "string",
                        "description": "which model to ask",
                        "enum": choices or ["none"],
                    },
                    "prompt": {"type": "string"},
                },
                "required": ["provider", "prompt"],
            },
            ask_model,
        ),
        Tool(
            "list_models", "List the AI models/backends available to delegate to.",
            {"type": "object", "properties": {}},
            list_models,
        ),
    ]
