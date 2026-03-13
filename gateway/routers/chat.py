"""Chat completions router.

Handles ``POST /v1/chat/completions`` forwarding to the appropriate
provider adapter, records usage, and returns the upstream response —
either as a full JSON body or as a Server-Sent Events stream.

Provider selection:
  • URL path:   ``POST /v1/{provider}/chat/completions``
  • Query param: ``?provider=openai``
  • Body field:  ``{"provider": "openai", ...}``
  Default: ``openai``.
"""

from __future__ import annotations

import logging
import uuid
from typing import Annotated, Any, AsyncIterator

import aiosqlite
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import StreamingResponse

from gateway.billing.tracker import extract_usage_from_response, record_usage
from gateway.database import get_db
from gateway.providers.registry import get_provider
from gateway.routers.deps import resolve_api_key_hash

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])

_STREAM_MEDIA_TYPE = "text/event-stream"


# ---------------------------------------------------------------------------
# Unified endpoint
# ---------------------------------------------------------------------------


@router.post("/v1/chat/completions")
@router.post("/v1/{provider_name}/chat/completions")
async def chat_completions(
    request: Request,
    db: Annotated[aiosqlite.Connection, Depends(get_db)],
    api_key_hash: Annotated[str, Depends(resolve_api_key_hash)],
    provider_name: str = "openai",
) -> Response:
    # ---------- parse body ----------
    body: dict[str, Any] = await request.json()
    # Provider can also be specified inside the body
    provider_name = body.pop("provider", provider_name)
    provider = get_provider(provider_name)

    model: str = body.get("model", "")
    stream: bool = bool(body.get("stream", False))
    request_id = str(uuid.uuid4())

    # Build headers to forward upstream (preserve caller's auth)
    upstream_headers = dict(request.headers)

    # ---------- forward ----------
    upstream = await provider.chat_completions(
        payload=body,
        headers=upstream_headers,
        stream=stream,
    )

    if stream:
        return await _stream_response(
            upstream,
            db=db,
            api_key_hash=api_key_hash,
            provider=provider,
            model=model,
            request_id=request_id,
        )

    # Non-streaming: read body, record usage, return
    response_body = await upstream.aread()
    usage = extract_usage_from_response(response_body)
    if usage:
        await record_usage(
            db,
            api_key_hash=api_key_hash,
            provider=provider,
            model=model,
            usage=usage,
            request_id=request_id,
        )

    return Response(
        content=response_body,
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type", "application/json"),
    )


# ---------------------------------------------------------------------------
# Streaming helper
# ---------------------------------------------------------------------------


async def _stream_response(
    upstream,
    *,
    db: aiosqlite.Connection,
    api_key_hash: str,
    provider,
    model: str,
    request_id: str,
) -> StreamingResponse:
    """Collect chunks, forward them, and record usage after stream ends."""
    chunks: list[bytes] = []

    async def generator() -> AsyncIterator[bytes]:
        async for chunk in provider.iter_stream(upstream):
            chunks.append(chunk)
            yield chunk
        # After stream completes, attempt to record usage from accumulated data
        full = b"".join(chunks)
        usage = extract_usage_from_response(full)
        if not usage:
            # SSE streams contain multiple JSON lines; grab the last data: line
            usage = _parse_sse_usage(full)
        if usage:
            try:
                await record_usage(
                    db,
                    api_key_hash=api_key_hash,
                    provider=provider,
                    model=model,
                    usage=usage,
                    request_id=request_id,
                )
            except (aiosqlite.Error, ValueError) as exc:
                logger.error("Failed to record streaming usage: %s", exc)

    return StreamingResponse(
        generator(),
        status_code=upstream.status_code,
        media_type=_STREAM_MEDIA_TYPE,
    )


def _parse_sse_usage(data: bytes) -> dict[str, Any]:
    """Best-effort extraction of usage from SSE stream bytes."""
    import json

    lines = data.decode(errors="replace").splitlines()
    for line in reversed(lines):
        if line.startswith("data:"):
            payload = line[5:].strip()
            if payload in ("[DONE]", ""):
                continue
            try:
                obj = json.loads(payload)
                usage = obj.get("usage")
                if usage:
                    return usage
            except json.JSONDecodeError:
                continue
    return {}
