"""The JARVIS agent loop: reason → call tools → observe → repeat."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from jarvis.core.memory import Memory
from jarvis.core.prompts import build_system_prompt
from jarvis.providers.base import ChatMessage, LLMProvider, ProviderError
from jarvis.tools.base import Toolset
from jarvis.utils.logging import get_logger

logger = get_logger("jarvis.agent")


@dataclass
class AgentEvent:
    """Streamed back to the UI as the agent works."""

    kind: str  # "thinking" | "tool_call" | "tool_result" | "final" | "error"
    text: str = ""
    tool_name: str = ""
    detail: str = ""


class EventSink:
    """A re-pointable event relay.

    The UI (CLI / dashboard) sets :attr:`callback`; components deep in the
    system (e.g. the delegate tool forwarding a specialist's progress) call
    :meth:`emit` without needing a direct reference to the UI.
    """

    def __init__(self) -> None:
        self.callback: Optional[Callable[[AgentEvent], None]] = None

    def emit(self, event: AgentEvent) -> None:
        if self.callback is not None:
            self.callback(event)


@dataclass
class Agent:
    """Orchestrates a provider + toolset + memory into a working agent."""

    provider: LLMProvider
    toolset: Toolset
    memory: Memory = field(default=None)  # type: ignore[assignment]
    max_iterations: int = 12
    temperature: float = 0.7

    def __post_init__(self) -> None:
        if self.memory is None:
            self.memory = Memory(build_system_prompt())

    def run(
        self,
        user_input: str,
        on_event: Optional[Callable[[AgentEvent], None]] = None,
    ) -> str:
        """Process one user turn to completion and return the final answer."""
        emit = on_event or (lambda _e: None)
        self.memory.add_user(user_input)

        specs = self.toolset.specs() if (self.toolset and len(self.toolset)) else None

        for iteration in range(1, self.max_iterations + 1):
            try:
                response = self.provider.chat(
                    self.memory.history(),
                    tools=specs,
                    temperature=self.temperature,
                )
            except ProviderError as exc:
                emit(AgentEvent("error", text=str(exc)))
                return f"[provider error] {exc}"

            self.memory.add(response.as_message())

            if not response.wants_tools:
                final = response.content or ""
                emit(AgentEvent("final", text=final))
                return final

            if response.content:
                emit(AgentEvent("thinking", text=response.content))

            for call in response.tool_calls:
                emit(AgentEvent("tool_call", tool_name=call.name, detail=call.arguments))
                logger.debug("tool_call %s %s", call.name, call.arguments)
                result = self.toolset.execute(call.name, call.arguments)
                emit(AgentEvent("tool_result", tool_name=call.name, detail=result))
                self.memory.add(
                    ChatMessage.tool_result(call.id, call.name, result)
                )

        msg = f"(stopped after {self.max_iterations} iterations without finishing)"
        emit(AgentEvent("error", text=msg))
        return msg
