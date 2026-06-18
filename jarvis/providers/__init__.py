"""LLM provider adapters.

Every provider in this package speaks the OpenAI chat-completions dialect,
so they all share :class:`OpenAICompatibleProvider`. The registry builds the
set of providers that have credentials configured.
"""

from jarvis.providers.base import (
    ChatMessage,
    LLMProvider,
    ProviderError,
    ProviderResponse,
    ToolCall,
)
from jarvis.providers.registry import available_providers, build_provider, build_registry

__all__ = [
    "ChatMessage",
    "LLMProvider",
    "ProviderError",
    "ProviderResponse",
    "ToolCall",
    "available_providers",
    "build_provider",
    "build_registry",
]
