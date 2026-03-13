"""Completions and embeddings routers (OpenAI-compatible pass-through)."""

from __future__ import annotations

import logging
import uuid
from typing import Annotated, Any

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, Request, Response

from gateway.billing.tracker import extract_usage_from_response, record_usage
from gateway.database import get_db
from gateway.providers.openai import OpenAIProvider
from gateway.providers.registry import get_provider
from gateway.routers.deps import resolve_api_key_hash

logger = logging.getLogger(__name__)

router = APIRouter(tags=["completions"])


@router.post("/v1/completions")
@router.post("/v1/{provider_name}/completions")
async def text_completions(
    request: Request,
    db: Annotated[aiosqlite.Connection, Depends(get_db)],
    api_key_hash: Annotated[str, Depends(resolve_api_key_hash)],
    provider_name: str = "openai",
) -> Response:
    body: dict[str, Any] = await request.json()
    provider_name = body.pop("provider", provider_name)
    provider = get_provider(provider_name)
    model: str = body.get("model", "")
    stream: bool = bool(body.get("stream", False))
    request_id = str(uuid.uuid4())

    # Only OpenAI supports plain completions; forward as-is.
    if not isinstance(provider, OpenAIProvider):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Provider '{provider_name}' does not support /v1/completions."
                " Use /v1/chat/completions."
            ),
        )

    upstream = await provider.completions(
        payload=body,
        headers=dict(request.headers),
        stream=stream,
    )
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


@router.post("/v1/embeddings")
@router.post("/v1/{provider_name}/embeddings")
async def embeddings(
    request: Request,
    db: Annotated[aiosqlite.Connection, Depends(get_db)],
    api_key_hash: Annotated[str, Depends(resolve_api_key_hash)],
    provider_name: str = "openai",
) -> Response:
    body: dict[str, Any] = await request.json()
    provider_name = body.pop("provider", provider_name)
    provider = get_provider(provider_name)
    model: str = body.get("model", "")
    request_id = str(uuid.uuid4())

    if not isinstance(provider, OpenAIProvider):
        raise HTTPException(
            status_code=400,
            detail=f"Provider '{provider_name}' does not support /v1/embeddings.",
        )

    upstream = await provider.embeddings(payload=body, headers=dict(request.headers))
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


@router.get("/v1/models")
@router.get("/v1/{provider_name}/models")
async def list_models(
    request: Request,
    db: Annotated[aiosqlite.Connection, Depends(get_db)],
    api_key_hash: Annotated[str, Depends(resolve_api_key_hash)],
    provider_name: str = "openai",
) -> Response:
    provider = get_provider(provider_name)

    if not isinstance(provider, OpenAIProvider):
        raise HTTPException(
            status_code=400,
            detail=f"Provider '{provider_name}' does not support /v1/models.",
        )

    upstream = await provider.models(headers=dict(request.headers))
    response_body = await upstream.aread()
    return Response(
        content=response_body,
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type", "application/json"),
    )

