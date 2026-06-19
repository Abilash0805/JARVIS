"""Build specialist agents from specs, a shared toolset, and the providers."""

from __future__ import annotations

from typing import Optional

from jarvis.agents.specs import DEFAULT_SPECS, AgentSpec
from jarvis.core.agent import Agent
from jarvis.core.memory import Memory
from jarvis.providers.base import LLMProvider
from jarvis.providers.router import RoutingProvider
from jarvis.tools.base import Toolset
from jarvis.utils.logging import get_logger

logger = get_logger("jarvis.team")


def _provider_for(
    spec: AgentSpec,
    api_providers: dict[str, LLMProvider],
    fallback_brain: LLMProvider,
) -> LLMProvider:
    """Pick the specialist's provider, chained with the rest for resilience."""
    if not api_providers:
        return fallback_brain
    primary = spec.provider if spec.provider in api_providers else None
    if primary is None:
        return fallback_brain
    # Primary first, then every other provider as automatic fallback.
    return RoutingProvider(list(api_providers.values()), primary=primary)


def build_team(
    toolset: Toolset,
    api_providers: dict[str, LLMProvider],
    fallback_brain: LLMProvider,
    *,
    specs: Optional[list[AgentSpec]] = None,
    max_iterations: int = 12,
) -> dict[str, Agent]:
    """Create one Agent per spec, each with its filtered toolset and provider.

    Specs whose tools are entirely unavailable (e.g. vision off) are skipped so
    the team only contains agents that can actually act.
    """
    specs = specs or DEFAULT_SPECS
    team: dict[str, Agent] = {}
    for spec in specs:
        sub_tools = toolset.subset(spec.tools)
        if len(sub_tools) == 0:
            logger.info("skipping agent %r — none of its tools are available", spec.name)
            continue
        provider = _provider_for(spec, api_providers, fallback_brain)
        team[spec.name] = Agent(
            provider=provider,
            toolset=sub_tools,
            memory=Memory(spec.system_prompt),
            max_iterations=max_iterations,
        )
        logger.info(
            "agent %r ready (provider=%s, %d tools)",
            spec.name, getattr(provider, "active_name", provider.name), len(sub_tools),
        )
    return team
