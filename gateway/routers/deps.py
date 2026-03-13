"""Shared FastAPI dependencies used across multiple routers."""

from __future__ import annotations

from typing import Annotated

import aiosqlite
from fastapi import Depends

from gateway.database import get_db
from gateway.middleware.auth import extract_raw_key, verify_api_key


async def resolve_api_key_hash(
    db: Annotated[aiosqlite.Connection, Depends(get_db)],
    raw_key: Annotated[str | None, Depends(extract_raw_key)],
) -> str:
    """Dependency that validates the caller's key and returns its hash.

    If no key is provided the request is treated as anonymous (useful
    during bootstrapping before any keys have been created).
    """
    if raw_key is None:
        return "anonymous"
    return await verify_api_key(db, raw_key)
