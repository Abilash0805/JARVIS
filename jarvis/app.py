"""Wire config + providers + tools + integrations into a ready Agent."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from jarvis.core.agent import Agent, EventSink
from jarvis.core.config import Config, load_config
from jarvis.core.longterm import LongTermMemory
from jarvis.core.memory import Memory
from jarvis.core.prompts import build_system_prompt
from jarvis.scheduler import TaskScheduler
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
    scheduler: Optional[TaskScheduler] = None
    team: dict[str, Agent] = field(default_factory=dict)
    sink: Optional[EventSink] = None


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

    # Scheduler: scheduled tasks run in a fresh agent (same brain + tools, new
    # memory) so they don't interfere with the live conversation.
    scheduler = TaskScheduler()

    def scheduled_runner(prompt: str) -> str:
        worker = Agent(
            provider=brain,
            toolset=toolset,
            memory=Memory(build_system_prompt()),
            max_iterations=config.max_iterations,
            temperature=config.temperature,
        )
        return worker.run(prompt)

    from jarvis.tools.scheduler_tools import make_scheduler_tools

    toolset.extend(make_scheduler_tools(scheduler, scheduled_runner))

    # Multi-agent team: specialists get a filtered copy of the toolset (snapshot
    # before delegate tools are added, so specialists can't re-delegate).
    from jarvis.agents.specs import DEFAULT_SPECS
    from jarvis.agents.team import build_team
    from jarvis.tools.agent_tools import make_delegate_tools

    team = build_team(toolset, api_providers, brain,
                      max_iterations=config.max_iterations)
    sink = EventSink()  # lets specialist progress reach whatever UI is attached
    toolset.extend(make_delegate_tools(team, DEFAULT_SPECS, sink=sink))

    # The lead/orchestrator agent owns the full toolset incl. delegation.
    agent = Agent(
        provider=brain,
        toolset=toolset,
        memory=Memory(build_system_prompt(orchestrator=True)),
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
        scheduler=scheduler,
        team=team,
        sink=sink,
    )
