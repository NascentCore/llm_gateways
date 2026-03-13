"""Tests for gateway meta-endpoints (health, root) and startup."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_health(async_client):
    resp = await async_client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_root(async_client):
    resp = await async_client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "LLM Gateway"
    assert "version" in data
    assert "docs" in data
