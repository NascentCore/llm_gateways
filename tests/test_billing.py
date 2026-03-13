"""Tests for billing tracker utilities."""

from __future__ import annotations

import json

from gateway.billing.tracker import extract_usage_from_response


def test_extract_usage_valid():
    body = json.dumps(
        {
            "id": "chatcmpl-abc",
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        }
    ).encode()
    usage = extract_usage_from_response(body)
    assert usage["prompt_tokens"] == 10
    assert usage["completion_tokens"] == 20
    assert usage["total_tokens"] == 30


def test_extract_usage_missing_usage_field():
    body = json.dumps({"id": "chatcmpl-abc"}).encode()
    usage = extract_usage_from_response(body)
    assert usage == {}


def test_extract_usage_invalid_json():
    usage = extract_usage_from_response(b"not json at all")
    assert usage == {}


def test_extract_usage_empty():
    usage = extract_usage_from_response(b"")
    assert usage == {}
