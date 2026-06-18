"""A provider that chains several free backends with automatic fallback.

Free tiers rate-limit aggressively, so JARVIS treats its configured providers
as an ordered chain: the preferred one first, the rest as backups. On a
recoverable error (rate limit / transient HTTP failure) it falls through to the
next provider, so the assistant keeps working without you touching anything.
"""

from __future__ import annotations

from typing import Any, Optional

from jarvis.providers.base import (
    ChatMessage,
    LLMProvider,
    ProviderError,
    ProviderResponse,
)
from jarvis.utils.logging import get_logger

logger = get_logger("jarvis.router")

# Substrings that mark an error worth retrying on the next provider.
_RECOVERABLE = ("429", "rate limit", "rate_limit", "quota", "overloaded",
                "503", "502", "timeout", "timed out", "temporarily")


def _is_recoverable(exc: ProviderError) -> bool:
    msg = str(exc).lower()
    return any(token in msg for token in _RECOVERABLE)


class RoutingProvider(LLMProvider):
    """Try an ordered list of providers until one succeeds.

    Implements :class:`LLMProvider`, so it drops straight into the agent in
    place of a single provider.
    """

    def __init__(self, providers: list[LLMProvider], primary: Optional[str] = None) -> None:
        if not providers:
            raise ProviderError("RoutingProvider needs at least one provider")
        ordered = list(providers)
        if primary:
            ordered.sort(key=lambda p: 0 if p.name == primary else 1)
        self._providers = ordered
        self._active = ordered[0]
        self.name = "router"
        self.model = f"router({'>'.join(p.name for p in ordered)})"
        self.supports_tools = all(p.supports_tools for p in ordered)

    @property
    def active_name(self) -> str:
        return self._active.name

    def chat(
        self,
        messages: list[ChatMessage],
        *,
        tools: Optional[list[dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> ProviderResponse:
        last_error: Optional[ProviderError] = None
        for provider in self._providers:
            # Skip backends that can't do tools when tools are required.
            if tools and not provider.supports_tools:
                continue
            try:
                resp = provider.chat(
                    messages,
                    tools=tools,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs,
                )
                self._active = provider
                return resp
            except ProviderError as exc:
                last_error = exc
                if _is_recoverable(exc):
                    logger.warning("%s unavailable (%s); falling back", provider.name, exc)
                    continue
                # Non-recoverable (bad request, auth) — still try the next one,
                # but remember the error in case all fail.
                logger.warning("%s failed (%s); trying next", provider.name, exc)
                continue
        raise ProviderError(
            f"all providers failed; last error: {last_error}"
        )
