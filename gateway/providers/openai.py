"""OpenAI provider adapter.

Forwards requests to the OpenAI-compatible API and estimates cost using
the published per-token pricing table (prices as of mid-2024).
"""

from __future__ import annotations

from typing import Any

import httpx

from gateway.config import settings
from gateway.providers.base import BaseProvider

# USD per 1 000 tokens  {model: (prompt, completion)}
_PRICE_PER_1K: dict[str, tuple[float, float]] = {
    "gpt-4o": (0.005, 0.015),
    "gpt-4o-mini": (0.00015, 0.0006),
    "gpt-4-turbo": (0.01, 0.03),
    "gpt-4": (0.03, 0.06),
    "gpt-3.5-turbo": (0.0005, 0.0015),
}


class OpenAIProvider(BaseProvider):
    name = "openai"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client or httpx.AsyncClient(timeout=120)

    async def chat_completions(
        self,
        *,
        payload: dict[str, Any],
        headers: dict[str, str],
        stream: bool,
    ) -> httpx.Response:
        url = f"{settings.openai_base_url}/chat/completions"
        upstream_headers = _build_headers(headers)
        req = self._client.build_request("POST", url, json=payload, headers=upstream_headers)
        return await self._client.send(req, stream=stream)

    async def completions(
        self,
        *,
        payload: dict[str, Any],
        headers: dict[str, str],
        stream: bool,
    ) -> httpx.Response:
        url = f"{settings.openai_base_url}/completions"
        upstream_headers = _build_headers(headers)
        req = self._client.build_request("POST", url, json=payload, headers=upstream_headers)
        return await self._client.send(req, stream=stream)

    async def embeddings(
        self,
        *,
        payload: dict[str, Any],
        headers: dict[str, str],
    ) -> httpx.Response:
        url = f"{settings.openai_base_url}/embeddings"
        upstream_headers = _build_headers(headers)
        req = self._client.build_request("POST", url, json=payload, headers=upstream_headers)
        return await self._client.send(req, stream=False)

    async def models(self, *, headers: dict[str, str]) -> httpx.Response:
        url = f"{settings.openai_base_url}/models"
        upstream_headers = _build_headers(headers)
        req = self._client.build_request("GET", url, headers=upstream_headers)
        return await self._client.send(req, stream=False)

    def estimate_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        # Match by prefix to handle model variants (e.g. "gpt-4o-mini-2024-07-18")
        key = model
        if key not in _PRICE_PER_1K:
            for k in _PRICE_PER_1K:
                if model.startswith(k):
                    key = k
                    break
        prices = _PRICE_PER_1K.get(key, (0.0, 0.0))
        return (prompt_tokens * prices[0] + completion_tokens * prices[1]) / 1000


def _build_headers(incoming: dict[str, str]) -> dict[str, str]:
    """Forward the caller's Authorization header; inject fallback key if absent."""
    headers: dict[str, str] = {"Content-Type": "application/json"}
    auth = incoming.get("authorization") or incoming.get("Authorization")
    if auth:
        headers["Authorization"] = auth
    elif settings.openai_api_key:
        headers["Authorization"] = f"Bearer {settings.openai_api_key}"
    return headers
