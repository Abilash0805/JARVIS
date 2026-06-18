"""Wire config + providers + tools + integrations into a ready Agent."""

from __future__ import annotations

from dataclasses import dataclass

from jarvis.core.agent import Agent
from jarvis.core.config import Config, load_config
from jarvis.core.longterm import LongTermMemory
from jarvis.providers.base import LLMProvider, ProviderError
from jarvis.providers.registry import build_registry, build_vision_provider
from jarvis.providers.router import RoutingProvider
from jarvis.tools.registry import default_toolset
from jarvis.utils.logging import get_logger
from jarvis.utils.safety import SafetyGate

logger = get_logger("jarvis.app")


@dataclass
class JarvisRuntime:
    """Everything a UI needs to talk to JARVIS."""

    agent: Agent
    config: Config
    api_providers: dict[str, LLMProvider]
    web_backends: dict[str, object]
    brain_name: str
    vision_enabled: bool = False


def build_runtime(enable_web: bool = True) -> JarvisRuntime:
    config = load_config()
    api_providers = build_registry()
    if not api_providers:
        raise ProviderError(
            "No API providers configured. Copy .env.example to .env and set at "
            "least one provider key (e.g. GROQ_API_KEY)."
        )

    # Pick the preferred brain, then chain all providers behind it so free-tier
    # rate limits fall through to a working backend automatically.
    brain_name = config.default_provider
    if brain_name not in api_providers:
        brain_name = next(iter(api_providers))
        logger.warning(
            "default provider %r not configured; using %r",
            config.default_provider, brain_name,
        )
    brain = RoutingProvider(list(api_providers.values()), primary=brain_name)

    # Optional browser AIs (Gemini/ChatGPT).
    web_backends: dict[str, object] = {}
    if enable_web:
        from jarvis.integrations.factory import build_web_backends

        web_backends = build_web_backends()

    vision_provider = build_vision_provider()
    longterm = LongTermMemory()

    gate = SafetyGate(require_confirmation=config.require_confirmation)
    toolset = default_toolset(
        gate,
        api_providers=api_providers,
        web_backends=web_backends,
        vision_provider=vision_provider,
        longterm=longterm,
        include_pc_control=config.include_pc_control,
    )

    agent = Agent(
        provider=brain,
        toolset=toolset,
        max_iterations=config.max_iterations,
        temperature=config.temperature,
    )
    return JarvisRuntime(
        agent=agent,
        config=config,
        api_providers=api_providers,
        web_backends=web_backends,
        brain_name=brain_name,
        vision_enabled=vision_provider is not None,
    )
