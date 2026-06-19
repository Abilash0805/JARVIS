"""Build the set of providers that have credentials configured."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from jarvis.providers.base import LLMProvider, ProviderError
from jarvis.providers.openai_compatible import OpenAICompatibleProvider


@dataclass(frozen=True)
class ProviderSpec:
    """Static description of how to construct a provider from env vars."""

    name: str
    key_env: str
    base_env: str
    model_env: str
    default_base: str
    default_model: str
    supports_tools: bool = True


# All four are OpenAI-compatible; only the env var names / defaults differ.
PROVIDER_SPECS: dict[str, ProviderSpec] = {
    "groq": ProviderSpec(
        "groq", "GROQ_API_KEY", "GROQ_BASE_URL", "GROQ_MODEL",
        "https://api.groq.com/openai/v1", "llama-3.3-70b-versatile",
    ),
    "cerebras": ProviderSpec(
        "cerebras", "CEREBRAS_API_KEY", "CEREBRAS_BASE_URL", "CEREBRAS_MODEL",
        "https://api.cerebras.ai/v1", "gpt-oss-120b",
    ),
    "mistral": ProviderSpec(
        "mistral", "MISTRAL_API_KEY", "MISTRAL_BASE_URL", "MISTRAL_MODEL",
        "https://api.mistral.ai/v1", "mistral-small-latest",
    ),
    "nvidia": ProviderSpec(
        "nvidia", "NVIDIA_API_KEY", "NVIDIA_BASE_URL", "NVIDIA_MODEL",
        "https://integrate.api.nvidia.com/v1",
        "nvidia/nemotron-3-super-120b-a12b",
    ),
}


# Free vision-capable models, keyed by the provider whose credentials they use.
VISION_MODELS: dict[str, str] = {
    "groq": "meta-llama/llama-4-scout-17b-16e-instruct",
    "nvidia": "meta/llama-3.2-90b-vision-instruct",
}


def build_vision_provider() -> Optional[OpenAICompatibleProvider]:
    """Build a provider configured for image description, if keys allow.

    Controlled by ``JARVIS_VISION_PROVIDER`` (default: groq) and
    ``JARVIS_VISION_MODEL`` (override the model). Reuses the chosen provider's
    base URL and API key.
    """
    name = os.getenv("JARVIS_VISION_PROVIDER", "groq").lower()
    spec = PROVIDER_SPECS.get(name)
    if spec is None:
        return None
    api_key = os.getenv(spec.key_env, "").strip()
    if not api_key:
        return None
    model = os.getenv("JARVIS_VISION_MODEL") or VISION_MODELS.get(name)
    if not model:
        return None
    return OpenAICompatibleProvider(
        name=f"{name}-vision",
        api_key=api_key,
        base_url=os.getenv(spec.base_env, spec.default_base),
        model=model,
    )


def build_provider(name: str) -> Optional[LLMProvider]:
    """Construct one provider by name, or ``None`` if its key is unset."""
    spec = PROVIDER_SPECS.get(name)
    if spec is None:
        raise ProviderError(f"unknown provider: {name!r}")
    api_key = os.getenv(spec.key_env, "").strip()
    if not api_key:
        return None
    return OpenAICompatibleProvider(
        name=spec.name,
        api_key=api_key,
        base_url=os.getenv(spec.base_env, spec.default_base),
        model=os.getenv(spec.model_env, spec.default_model),
        supports_tools=spec.supports_tools,
    )


def build_registry() -> dict[str, LLMProvider]:
    """Build every provider that has an API key configured."""
    registry: dict[str, LLMProvider] = {}
    for name in PROVIDER_SPECS:
        provider = build_provider(name)
        if provider is not None:
            registry[name] = provider
    return registry


def available_providers() -> list[str]:
    """Names of providers that currently have credentials."""
    return [n for n in PROVIDER_SPECS if os.getenv(PROVIDER_SPECS[n].key_env, "").strip()]
