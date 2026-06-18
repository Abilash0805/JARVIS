"""A single client for every OpenAI-compatible chat API.

Kimi, GLM, Groq, Cerebras, Mistral and NVIDIA NIM all expose the
``/chat/completions`` endpoint with the same request/response shape, so one
implementation parameterised by base URL + key + model covers all of them.
"""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Any, Optional

import httpx

from jarvis.providers.base import (
    ChatMessage,
    LLMProvider,
    ProviderError,
    ProviderResponse,
    ToolCall,
)


class OpenAICompatibleProvider(LLMProvider):
    """Generic client for an OpenAI-style chat-completions endpoint."""

    def __init__(
        self,
        *,
        name: str,
        api_key: str,
        base_url: str,
        model: str,
        supports_tools: bool = True,
        timeout: float = 120.0,
        extra_headers: Optional[dict[str, str]] = None,
    ) -> None:
        if not api_key:
            raise ProviderError(f"{name}: missing API key")
        self.name = name
        self.model = model
        self.supports_tools = supports_tools
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        if extra_headers:
            headers.update(extra_headers)
        self._headers = headers

    def chat(
        self,
        messages: list[ChatMessage],
        *,
        tools: Optional[list[dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> ProviderResponse:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [m.to_dict() for m in messages],
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if tools and self.supports_tools:
            payload["tools"] = tools
            payload["tool_choice"] = kwargs.pop("tool_choice", "auto")
        payload.update(kwargs)

        url = f"{self._base_url}/chat/completions"
        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.post(url, headers=self._headers, json=payload)
        except httpx.HTTPError as exc:  # network-level failure
            raise ProviderError(f"{self.name}: request failed: {exc}") from exc

        if resp.status_code >= 400:
            raise ProviderError(
                f"{self.name}: HTTP {resp.status_code}: {resp.text[:500]}"
            )

        try:
            data = resp.json()
        except ValueError as exc:
            raise ProviderError(f"{self.name}: invalid JSON response") from exc

        return self._parse(data)

    def describe_image(
        self,
        image_path: str,
        prompt: str,
        *,
        model: Optional[str] = None,
        max_tokens: int = 1024,
    ) -> str:
        """Send an image + prompt to a vision model and return its description.

        Uses the OpenAI multimodal message shape (a content array with an
        ``image_url`` carrying a base64 data URL), which the free vision models
        on Groq and NVIDIA NIM accept.
        """
        path = Path(image_path).expanduser()
        if not path.is_file():
            raise ProviderError(f"image not found: {path}")
        mime = mimetypes.guess_type(path.name)[0] or "image/png"
        b64 = base64.b64encode(path.read_bytes()).decode("ascii")
        payload = {
            "model": model or self.model,
            "max_tokens": max_tokens,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url",
                         "image_url": {"url": f"data:{mime};base64,{b64}"}},
                    ],
                }
            ],
        }
        url = f"{self._base_url}/chat/completions"
        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.post(url, headers=self._headers, json=payload)
        except httpx.HTTPError as exc:
            raise ProviderError(f"{self.name}: vision request failed: {exc}") from exc
        if resp.status_code >= 400:
            raise ProviderError(f"{self.name}: HTTP {resp.status_code}: {resp.text[:500]}")
        return self._parse(resp.json()).content or "<no description>"

    @staticmethod
    def _parse(data: dict[str, Any]) -> ProviderResponse:
        choices = data.get("choices") or []
        if not choices:
            raise ProviderError(f"empty choices in response: {data}")
        choice = choices[0]
        message = choice.get("message", {})

        tool_calls: list[ToolCall] = []
        for tc in message.get("tool_calls") or []:
            fn = tc.get("function", {})
            tool_calls.append(
                ToolCall(
                    id=tc.get("id", ""),
                    name=fn.get("name", ""),
                    arguments=fn.get("arguments", "") or "{}",
                )
            )

        return ProviderResponse(
            content=message.get("content"),
            tool_calls=tool_calls,
            finish_reason=choice.get("finish_reason"),
            raw=data,
        )
