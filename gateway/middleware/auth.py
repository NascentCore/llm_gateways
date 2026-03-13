"""API key authentication helpers.

Gateway API keys are stored hashed (SHA-256) in the database so the raw
value never persists.  On each request the caller supplies the key in
the ``Authorization: Bearer <key>`` header (or ``X-API-Key: <key>``).
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone

import aiosqlite
from fastapi import Header, HTTPException, status


def generate_key() -> str:
    """Generate a cryptographically secure random API key."""
    return "gw-" + secrets.token_urlsafe(32)


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


async def create_api_key(
    db: aiosqlite.Connection,
    *,
    label: str = "",
    owner: str = "",
    expires_at: str | None = None,
) -> tuple[str, int]:
    """Insert a new key and return (raw_key, row_id)."""
    raw = generate_key()
    hashed = hash_key(raw)
    cursor = await db.execute(
        "INSERT INTO api_keys (key_hash, label, owner, expires_at) VALUES (?, ?, ?, ?)",
        (hashed, label, owner, expires_at),
    )
    await db.commit()
    return raw, cursor.lastrowid  # type: ignore[return-value]


async def revoke_api_key(db: aiosqlite.Connection, key_id: int) -> bool:
    """Deactivate a key by id; return True if a row was updated."""
    cursor = await db.execute(
        "UPDATE api_keys SET is_active = 0 WHERE id = ?",
        (key_id,),
    )
    await db.commit()
    return cursor.rowcount > 0


async def verify_api_key(
    db: aiosqlite.Connection,
    raw_key: str,
) -> str:
    """
    Validate the key against the database.

    Returns the key_hash on success so callers can use it for billing.
    Raises HTTPException(401) on failure.
    """
    hashed = hash_key(raw_key)
    async with db.execute(
        "SELECT is_active, expires_at FROM api_keys WHERE key_hash = ?",
        (hashed,),
    ) as cursor:
        row = await cursor.fetchone()

    if row is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

    is_active, expires_at = row[0], row[1]
    if not is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key revoked")

    if expires_at:
        exp = datetime.fromisoformat(expires_at)
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if datetime.now(tz=timezone.utc) > exp:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key expired")

    return hashed


def extract_raw_key(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> str | None:
    """Pull the raw key from request headers (FastAPI dependency)."""
    if x_api_key:
        return x_api_key
    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() == "bearer":
            return token
    return None
