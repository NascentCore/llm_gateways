"""Provider registry – maps provider name strings to adapter instances."""

from __future__ import annotations

from gateway.providers.anthropic import AnthropicProvider
from gateway.providers.base import BaseProvider
from gateway.providers.openai import OpenAIProvider

_registry: dict[str, BaseProvider] = {
    "openai": OpenAIProvider(),
    "anthropic": AnthropicProvider(),
}


def get_provider(name: str) -> BaseProvider:
    """Return a provider adapter by name (case-insensitive)."""
    provider = _registry.get(name.lower())
    if provider is None:
        supported = list(_registry.keys())
        raise ValueError(f"Unknown provider '{name}'. Supported: {supported}")
    return provider


def list_providers() -> list[str]:
    return list(_registry.keys())
