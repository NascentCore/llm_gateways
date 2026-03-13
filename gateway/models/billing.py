"""Pydantic models for billing / usage."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class UsageRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    api_key_hash: str
    provider: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    request_id: str | None = None
    created_at: str | None = None


class UsageSummary(BaseModel):
    api_key_hash: str
    total_requests: int
    total_prompt_tokens: int
    total_completion_tokens: int
    total_tokens: int
    total_cost_usd: float
