"""Web-test fixtures: in-process FastAPI client, no real network.

We avoid pytest-asyncio (not in dev extras) by exposing a synchronous helper
``async_run(coro)`` that drives a fresh event loop per call. Tests write plain
sync test functions that await via the helper.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from pathlib import Path
from typing import TypeVar

import httpx
import pytest
from httpx import ASGITransport

from archithreat.web.app import create_app
from archithreat.web.settings import reset_settings_cache

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"

T = TypeVar("T")


def async_run(coro: Awaitable[T]) -> T:
    """Run an async coroutine to completion in a fresh loop."""
    return asyncio.new_event_loop().run_until_complete(coro)  # type: ignore[arg-type]


@pytest.fixture
def lemonade_xml_bytes() -> bytes:
    return (FIXTURES / "lemonade_shop.xml").read_bytes()


@pytest.fixture
def minimal_xml_bytes() -> bytes:
    return (FIXTURES / "minimal.xml").read_bytes()


@pytest.fixture
def app_factory(monkeypatch: pytest.MonkeyPatch):
    """Build a fresh FastAPI app, optionally with overridden env vars."""

    def _factory(**env: str):
        for k, v in env.items():
            monkeypatch.setenv(k, v)
        reset_settings_cache()
        return create_app()

    yield _factory
    reset_settings_cache()


@pytest.fixture
def make_client(app_factory):
    """Return a callable that builds an httpx.AsyncClient bound to a fresh app."""

    def _make(**env: str) -> httpx.AsyncClient:
        app = app_factory(**env)
        transport = ASGITransport(app=app)
        return httpx.AsyncClient(transport=transport, base_url="http://test")

    return _make


@pytest.fixture
def client(make_client) -> httpx.AsyncClient:
    return make_client()
