"""Pydantic models for API key management."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class APIKeyCreate(BaseModel):
    label: str = ""
    owner: str = ""
    expires_at: str | None = None


class APIKeyInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    label: str
    owner: str
    is_active: bool
    created_at: str
    expires_at: str | None = None
    # The raw key is only returned on creation
    key: str | None = None
