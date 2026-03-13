"""Abstract base class for all LLM provider adapters."""

from __future__ import annotations

import abc
from typing import Any, AsyncIterator

import httpx


class BaseProvider(abc.ABC):
    """Minimal contract every provider adapter must satisfy."""

    name: str  # e.g. "openai" or "anthropic"

    @abc.abstractmethod
    async def chat_completions(
        self,
        *,
        payload: dict[str, Any],
        headers: dict[str, str],
        stream: bool,
    ) -> httpx.Response:
        """Forward a chat-completions request and return the upstream response."""

    @abc.abstractmethod
    def estimate_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        """Return the estimated cost in USD for a completed request."""

    # ------------------------------------------------------------------
    # Shared streaming helper
    # ------------------------------------------------------------------

    @staticmethod
    async def iter_stream(response: httpx.Response) -> AsyncIterator[bytes]:
        """Yield raw bytes chunks from a streaming upstream response."""
        async for chunk in response.aiter_bytes():
            yield chunk
