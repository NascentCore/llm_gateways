"""Admin router — key management and usage reporting.

All endpoints require the master ``ADMIN_API_KEY`` supplied via
``Authorization: Bearer <admin_key>`` or ``X-API-Key: <admin_key>``.
"""

from __future__ import annotations

import logging
from typing import Annotated

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, Request, status

from gateway.billing.tracker import get_usage_summary
from gateway.database import get_db
from gateway.middleware.auth import create_api_key, extract_raw_key, revoke_api_key
from gateway.models.billing import UsageSummary
from gateway.models.keys import APIKeyCreate, APIKeyInfo
from gateway.providers.registry import list_providers

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


# ---------------------------------------------------------------------------
# Admin auth dependency
# ---------------------------------------------------------------------------


def require_admin(request: Request, raw_key: Annotated[str | None, Depends(extract_raw_key)]):
    from gateway.config import settings

    if not raw_key or raw_key != settings.admin_api_key:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")


AdminDep = Depends(require_admin)


# ---------------------------------------------------------------------------
# API key management
# ---------------------------------------------------------------------------


@router.post("/keys", response_model=APIKeyInfo, status_code=status.HTTP_201_CREATED)
async def create_key(
    body: APIKeyCreate,
    db: Annotated[aiosqlite.Connection, Depends(get_db)],
    _: None = AdminDep,
) -> APIKeyInfo:
    """Create a new gateway API key."""
    raw, key_id = await create_api_key(
        db, label=body.label, owner=body.owner, expires_at=body.expires_at
    )
    # Re-fetch the row so we return the DB-generated created_at timestamp
    async with db.execute(
        "SELECT id, label, owner, is_active, created_at, expires_at FROM api_keys WHERE id = ?",
        (key_id,),
    ) as cursor:
        row = await cursor.fetchone()
    return APIKeyInfo(
        id=row[0],
        label=row[1],
        owner=row[2],
        is_active=bool(row[3]),
        created_at=row[4],
        expires_at=row[5],
        key=raw,
    )


@router.get("/keys", response_model=list[APIKeyInfo])
async def list_keys(
    db: Annotated[aiosqlite.Connection, Depends(get_db)],
    _: None = AdminDep,
) -> list[APIKeyInfo]:
    """List all gateway API keys (raw keys are never returned here)."""
    async with db.execute(
        "SELECT id, label, owner, is_active, created_at, expires_at FROM api_keys ORDER BY id"
    ) as cursor:
        rows = await cursor.fetchall()
    return [
        APIKeyInfo(
            id=r[0],
            label=r[1],
            owner=r[2],
            is_active=bool(r[3]),
            created_at=r[4],
            expires_at=r[5],
        )
        for r in rows
    ]


@router.delete("/keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_key(
    key_id: int,
    db: Annotated[aiosqlite.Connection, Depends(get_db)],
    _: None = AdminDep,
) -> None:
    """Revoke (deactivate) a gateway API key by its numeric id."""
    ok = await revoke_api_key(db, key_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Key not found")


# ---------------------------------------------------------------------------
# Usage reporting
# ---------------------------------------------------------------------------


@router.get("/usage/{key_hash}", response_model=UsageSummary)
async def usage_summary(
    key_hash: str,
    db: Annotated[aiosqlite.Connection, Depends(get_db)],
    _: None = AdminDep,
) -> UsageSummary:
    """Return aggregated usage statistics for a hashed key."""
    return await get_usage_summary(db, key_hash)


@router.get("/usage", response_model=list[dict])
async def all_usage(
    db: Annotated[aiosqlite.Connection, Depends(get_db)],
    _: None = AdminDep,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    """List recent usage records (newest first)."""
    async with db.execute(
        """
        SELECT id, api_key_hash, provider, model,
               prompt_tokens, completion_tokens, total_tokens,
               cost_usd, request_id, created_at
        FROM usage_records
        ORDER BY id DESC
        LIMIT ? OFFSET ?
        """,
        (limit, offset),
    ) as cursor:
        rows = await cursor.fetchall()
    keys = [
        "id",
        "api_key_hash",
        "provider",
        "model",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "cost_usd",
        "request_id",
        "created_at",
    ]
    return [dict(zip(keys, r)) for r in rows]


# ---------------------------------------------------------------------------
# Provider info
# ---------------------------------------------------------------------------


@router.get("/providers")
async def get_providers(_: None = AdminDep) -> dict:
    """List registered LLM provider adapters."""
    return {"providers": list_providers()}
