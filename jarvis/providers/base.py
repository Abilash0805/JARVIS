"""Provider-agnostic message/response types and the provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


class ProviderError(RuntimeError):
    """Raised when a provider request fails."""


@dataclass
class ToolCall:
    """A model's request to invoke a tool (OpenAI function-calling shape)."""

    id: str
    name: str
    arguments: str  # raw JSON string, as returned by the model

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": "function",
            "function": {"name": self.name, "arguments": self.arguments},
        }


@dataclass
class ChatMessage:
    """A single chat message in OpenAI format.

    ``role`` is one of: system, user, assistant, tool.
    ``tool_calls`` is set on assistant turns that call tools.
    ``tool_call_id``/``name`` are set on ``tool`` results.
    """

    role: str
    content: Optional[str] = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: Optional[str] = None
    name: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        msg: dict[str, Any] = {"role": self.role}
        # Assistant tool-call turns may legitimately have null content.
        if self.content is not None or not self.tool_calls:
            msg["content"] = self.content
        if self.tool_calls:
            msg["tool_calls"] = [tc.to_dict() for tc in self.tool_calls]
        if self.tool_call_id is not None:
            msg["tool_call_id"] = self.tool_call_id
        if self.name is not None:
            msg["name"] = self.name
        return msg

    @classmethod
    def system(cls, content: str) -> "ChatMessage":
        return cls(role="system", content=content)

    @classmethod
    def user(cls, content: str) -> "ChatMessage":
        return cls(role="user", content=content)

    @classmethod
    def tool_result(cls, tool_call_id: str, name: str, content: str) -> "ChatMessage":
        return cls(role="tool", tool_call_id=tool_call_id, name=name, content=content)


@dataclass
class ProviderResponse:
    """The model's reply for a single turn."""

    content: Optional[str]
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: Optional[str] = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def wants_tools(self) -> bool:
        return bool(self.tool_calls)

    def as_message(self) -> ChatMessage:
        """Convert this reply into an assistant message for history."""
        return ChatMessage(
            role="assistant", content=self.content, tool_calls=list(self.tool_calls)
        )


class LLMProvider(ABC):
    """Interface every model backend implements."""

    #: short, stable identifier (e.g. "groq", "cerebras")
    name: str
    #: model id sent to the API
    model: str
    #: whether the backend supports OpenAI-style function calling
    supports_tools: bool = True

    @abstractmethod
    def chat(
        self,
        messages: list[ChatMessage],
        *,
        tools: Optional[list[dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> ProviderResponse:
        """Send a chat-completion request and return the model's reply."""

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"<{type(self).__name__} name={self.name!r} model={self.model!r}>"
