"""Tests for provider adapters."""

from __future__ import annotations

import pytest

from gateway.providers.anthropic import AnthropicProvider, _openai_to_anthropic
from gateway.providers.openai import OpenAIProvider
from gateway.providers.registry import get_provider, list_providers

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


def test_list_providers():
    providers = list_providers()
    assert "openai" in providers
    assert "anthropic" in providers


def test_get_known_provider():
    p = get_provider("openai")
    assert p.name == "openai"


def test_get_unknown_provider():
    with pytest.raises(ValueError, match="Unknown provider"):
        get_provider("nonexistent")


# ---------------------------------------------------------------------------
# OpenAI cost estimation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "model,prompt,completion,expected_approx",
    [
        ("gpt-4o", 1000, 500, 0.005 + 0.0075),  # (1000*0.005 + 500*0.015)/1000
        ("gpt-4o-mini", 1000, 500, 0.00045),     # (1000*0.00015 + 500*0.0006)/1000
        ("gpt-3.5-turbo", 1000, 1000, 0.002),    # (1000*0.0005 + 1000*0.0015)/1000
        # Unknown model → 0.0
        ("unknown-model-xyz", 1000, 1000, 0.0),
    ],
)
def test_openai_cost_estimate(model, prompt, completion, expected_approx):
    provider = OpenAIProvider()
    cost = provider.estimate_cost(model, prompt, completion)
    assert cost == pytest.approx(expected_approx, rel=1e-6)


def test_openai_cost_zero_tokens():
    provider = OpenAIProvider()
    assert provider.estimate_cost("gpt-4o", 0, 0) == 0.0


# ---------------------------------------------------------------------------
# Anthropic cost estimation
# ---------------------------------------------------------------------------


def test_anthropic_cost_estimate():
    provider = AnthropicProvider()
    cost = provider.estimate_cost("claude-3-haiku", 1000, 500)
    assert cost > 0


# ---------------------------------------------------------------------------
# OpenAI → Anthropic payload translation
# ---------------------------------------------------------------------------


def test_openai_to_anthropic_basic():
    payload = {
        "model": "claude-3-haiku",
        "messages": [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello"},
        ],
        "max_tokens": 256,
    }
    result = _openai_to_anthropic(payload)
    assert result["model"] == "claude-3-haiku"
    assert result["system"] == "You are helpful."
    assert result["max_tokens"] == 256
    assert result["messages"] == [{"role": "user", "content": "Hello"}]


def test_openai_to_anthropic_no_system():
    payload = {
        "model": "claude-3-haiku",
        "messages": [{"role": "user", "content": "Hi"}],
    }
    result = _openai_to_anthropic(payload)
    assert "system" not in result


def test_openai_to_anthropic_stop_string():
    payload = {
        "model": "claude-3-haiku",
        "messages": [{"role": "user", "content": "Hi"}],
        "stop": "\n",
    }
    result = _openai_to_anthropic(payload)
    assert result["stop_sequences"] == ["\n"]


def test_openai_to_anthropic_stop_list():
    payload = {
        "model": "claude-3-haiku",
        "messages": [{"role": "user", "content": "Hi"}],
        "stop": ["\n", "END"],
    }
    result = _openai_to_anthropic(payload)
    assert result["stop_sequences"] == ["\n", "END"]


def test_openai_to_anthropic_stream_flag():
    payload = {
        "model": "claude-3-haiku",
        "messages": [{"role": "user", "content": "Hi"}],
        "stream": True,
    }
    result = _openai_to_anthropic(payload)
    assert result["stream"] is True
