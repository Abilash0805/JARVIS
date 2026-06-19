"""Multi-agent JARVIS: a lead orchestrator that delegates to specialists.

Each specialist is an :class:`~jarvis.core.agent.Agent` with a focused role,
a curated subset of tools, and a preferred (free) model — so different parts of
a task run on different providers, spreading free-tier load and using the best
model per job. The lead agent picks who does what via ``delegate_to_agent``.
"""

from jarvis.agents.specs import AgentSpec, DEFAULT_SPECS
from jarvis.agents.team import build_team

__all__ = ["AgentSpec", "DEFAULT_SPECS", "build_team"]
