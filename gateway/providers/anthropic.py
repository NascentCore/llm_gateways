"""Anthropic provider adapter.

Translates the OpenAI-style chat-completions wire format to Anthropic's
Messages API so callers can use a single, unified request schema.
"""

from __future__ import annotations

from typing import Any

import httpx

from gateway.config import settings
from gateway.providers.base import BaseProvider

# USD per 1 000 tokens  {model: (input, output)}
_PRICE_PER_1K: dict[str, tuple[float, float]] = {
    "claude-3-5-sonnet": (0.003, 0.015),
    "claude-3-opus": (0.015, 0.075),
    "claude-3-sonnet": (0.003, 0.015),
    "claude-3-haiku": (0.00025, 0.00125),
    "claude-2.1": (0.008, 0.024),
    "claude-2": (0.008, 0.024),
    "claude-instant-1": (0.0008, 0.0024),
}

_ANTHROPIC_VERSION = "2023-06-01"


class AnthropicProvider(BaseProvider):
    name = "anthropic"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client or httpx.AsyncClient(timeout=120)

    async def chat_completions(
        self,
        *,
        payload: dict[str, Any],
        headers: dict[str, str],
        stream: bool,
    ) -> httpx.Response:
        """Accept an OpenAI-style payload and forward to Anthropic Messages API."""
        anthropic_payload = _openai_to_anthropic(payload)
        url = f"{settings.anthropic_base_url}/v1/messages"
        upstream_headers = _build_headers(headers, stream=stream)
        req = self._client.build_request(
            "POST", url, json=anthropic_payload, headers=upstream_headers
        )
        return await self._client.send(req, stream=stream)

    def estimate_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        key = model
        if key not in _PRICE_PER_1K:
            for k in _PRICE_PER_1K:
                if model.startswith(k):
                    key = k
                    break
        prices = _PRICE_PER_1K.get(key, (0.0, 0.0))
        return (prompt_tokens * prices[0] + completion_tokens * prices[1]) / 1000


# ---------------------------------------------------------------------------
# Format translation helpers
# ---------------------------------------------------------------------------


def _openai_to_anthropic(payload: dict[str, Any]) -> dict[str, Any]:
    """Convert OpenAI chat-completion payload to Anthropic Messages format."""
    messages = payload.get("messages", [])
    system_content: str | None = None
    anthropic_messages: list[dict[str, Any]] = []

    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role == "system":
            system_content = content
        elif role == "assistant":
            anthropic_messages.append({"role": "assistant", "content": content})
        else:
            anthropic_messages.append({"role": "user", "content": content})

    result: dict[str, Any] = {
        "model": payload.get("model", "claude-3-haiku"),
        "messages": anthropic_messages,
        "max_tokens": payload.get("max_tokens", 1024),
    }
    if system_content:
        result["system"] = system_content
    if "temperature" in payload:
        result["temperature"] = payload["temperature"]
    if "top_p" in payload:
        result["top_p"] = payload["top_p"]
    if "stop" in payload:
        result["stop_sequences"] = (
            payload["stop"] if isinstance(payload["stop"], list) else [payload["stop"]]
        )
    if payload.get("stream"):
        result["stream"] = True
    return result


def _build_headers(incoming: dict[str, str], *, stream: bool = False) -> dict[str, str]:
    headers: dict[str, str] = {
        "Content-Type": "application/json",
        "anthropic-version": _ANTHROPIC_VERSION,
    }
    # Accept x-api-key or Bearer token from caller
    api_key = (
        incoming.get("x-api-key")
        or incoming.get("X-Api-Key")
        or _bearer_key(incoming.get("authorization") or incoming.get("Authorization") or "")
        or settings.anthropic_api_key
    )
    if api_key:
        headers["x-api-key"] = api_key
    if stream:
        headers["Accept"] = "text/event-stream"
    return headers


def _bearer_key(auth: str) -> str:
    if auth.lower().startswith("bearer "):
        return auth[7:]
    return ""
