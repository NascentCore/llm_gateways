"""Tests for admin endpoints and billing."""

from __future__ import annotations

import pytest

ADMIN_HEADERS = {"Authorization": "Bearer test-admin-key"}


# ---------------------------------------------------------------------------
# Admin – provider listing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_providers(async_client):
    resp = await async_client.get("/admin/providers", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert "openai" in data["providers"]
    assert "anthropic" in data["providers"]


@pytest.mark.asyncio
async def test_admin_requires_auth(async_client):
    resp = await async_client.get("/admin/providers")
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Admin – key lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_and_list_key(async_client):
    # Create a key
    resp = await async_client.post(
        "/admin/keys",
        json={"label": "test-key", "owner": "alice"},
        headers=ADMIN_HEADERS,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["label"] == "test-key"
    assert data["owner"] == "alice"
    assert data["is_active"] is True
    raw_key = data["key"]
    assert raw_key.startswith("gw-")

    # List keys
    resp = await async_client.get("/admin/keys", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    keys = resp.json()
    assert any(k["label"] == "test-key" for k in keys)

    return raw_key, data["id"]


@pytest.mark.asyncio
async def test_revoke_key(async_client):
    # Create
    resp = await async_client.post(
        "/admin/keys",
        json={"label": "to-revoke", "owner": "bob"},
        headers=ADMIN_HEADERS,
    )
    key_id = resp.json()["id"]

    # Revoke
    resp = await async_client.delete(f"/admin/keys/{key_id}", headers=ADMIN_HEADERS)
    assert resp.status_code == 204

    # Verify it's gone from active
    resp = await async_client.get("/admin/keys", headers=ADMIN_HEADERS)
    for k in resp.json():
        if k["id"] == key_id:
            assert k["is_active"] is False


@pytest.mark.asyncio
async def test_revoke_nonexistent_key(async_client):
    resp = await async_client.delete("/admin/keys/999999", headers=ADMIN_HEADERS)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Auth middleware
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_valid_gateway_key_auth(async_client):
    """A request with a valid gateway key should pass auth (will fail upstream)."""
    import httpx

    # Create a gateway key
    resp = await async_client.post(
        "/admin/keys",
        json={"label": "auth-test"},
        headers=ADMIN_HEADERS,
    )
    raw_key = resp.json()["key"]

    # Use the key — in the test env the upstream (OpenAI) is unreachable.
    # Either the gateway returns a 5xx, or the httpx client raises a
    # ConnectError.  Both are acceptable: they confirm auth passed and the
    # gateway attempted the upstream call (i.e. we did NOT get a 401).
    try:
        resp = await async_client.post(
            "/v1/chat/completions",
            json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}]},
            headers={"Authorization": f"Bearer {raw_key}"},
        )
        assert resp.status_code != 401
    except httpx.ConnectError:
        # Network unavailable in sandbox — auth passed, upstream call attempted
        pass


@pytest.mark.asyncio
async def test_invalid_gateway_key_returns_401(async_client):
    resp = await async_client.post(
        "/v1/chat/completions",
        json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}]},
        headers={"Authorization": "Bearer gw-totally-wrong-key"},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Usage endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_usage_summary_empty(async_client):
    resp = await async_client.get(
        "/admin/usage/nonexistent-hash",
        headers=ADMIN_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_requests"] == 0
    assert data["total_cost_usd"] == 0.0


@pytest.mark.asyncio
async def test_all_usage_list(async_client):
    resp = await async_client.get("/admin/usage", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
