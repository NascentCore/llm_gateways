"""Shared pytest fixtures."""

from __future__ import annotations

import os
import tempfile

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Create a temporary SQLite database for the entire test session.
# It is registered for cleanup via a session-scoped fixture finalizer.
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
_TEST_DB = _tmp.name

os.environ.setdefault("DATABASE_URL", _TEST_DB)
os.environ.setdefault("ADMIN_API_KEY", "test-admin-key")

# Import *after* setting env vars so Settings picks them up
from gateway.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_db():
    """Remove the temporary SQLite database file after the test session."""
    yield
    try:
        os.unlink(_TEST_DB)
    except OSError:
        pass


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture(scope="function")
async def async_client():
    """Async HTTPX client backed by the ASGI app (no real HTTP)."""
    from gateway.database import init_db

    await init_db()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client

