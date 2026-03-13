"""Usage recording and billing helpers."""

from __future__ import annotations

import json
import logging
from typing import Any

import aiosqlite

from gateway.models.billing import UsageRecord, UsageSummary
from gateway.providers.base import BaseProvider

logger = logging.getLogger(__name__)


async def record_usage(
    db: aiosqlite.Connection,
    *,
    api_key_hash: str,
    provider: BaseProvider,
    model: str,
    usage: dict[str, Any],
    request_id: str | None = None,
) -> UsageRecord:
    """Persist a usage record and return it."""
    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)
    total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens)
    cost_usd = provider.estimate_cost(model, prompt_tokens, completion_tokens)

    row = UsageRecord(
        api_key_hash=api_key_hash,
        provider=provider.name,
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        cost_usd=cost_usd,
        request_id=request_id,
    )

    await db.execute(
        """
        INSERT INTO usage_records
            (api_key_hash, provider, model, prompt_tokens,
             completion_tokens, total_tokens, cost_usd, request_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row.api_key_hash,
            row.provider,
            row.model,
            row.prompt_tokens,
            row.completion_tokens,
            row.total_tokens,
            row.cost_usd,
            row.request_id,
        ),
    )
    await db.commit()
    logger.debug(
        "Usage recorded: provider=%s model=%s tokens=%d cost=$%.6f",
        provider.name,
        model,
        total_tokens,
        cost_usd,
    )
    return row


async def get_usage_summary(db: aiosqlite.Connection, api_key_hash: str) -> UsageSummary:
    """Aggregate usage statistics for a key."""
    async with db.execute(
        """
        SELECT
            COUNT(*)                AS total_requests,
            COALESCE(SUM(prompt_tokens), 0)      AS total_prompt_tokens,
            COALESCE(SUM(completion_tokens), 0)  AS total_completion_tokens,
            COALESCE(SUM(total_tokens), 0)       AS total_tokens,
            COALESCE(SUM(cost_usd), 0.0)         AS total_cost_usd
        FROM usage_records
        WHERE api_key_hash = ?
        """,
        (api_key_hash,),
    ) as cursor:
        row = await cursor.fetchone()

    return UsageSummary(
        api_key_hash=api_key_hash,
        total_requests=row[0],
        total_prompt_tokens=row[1],
        total_completion_tokens=row[2],
        total_tokens=row[3],
        total_cost_usd=row[4],
    )


def extract_usage_from_response(body: bytes) -> dict[str, Any]:
    """Parse the usage dict from a non-streaming JSON response body."""
    try:
        data = json.loads(body)
        return data.get("usage") or {}
    except (json.JSONDecodeError, AttributeError):
        return {}
