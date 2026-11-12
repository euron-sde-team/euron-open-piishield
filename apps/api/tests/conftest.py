"""Shared fixtures.

Unit tests (``tests/unit``) never touch a database or network: they exercise pure
functions (checksums, masking, JSON walking) and the detectors module directly.

Integration tests (``tests/integration``) need real Postgres and Redis, provided by
``TEST_DATABASE_URL`` / ``TEST_REDIS_URL`` (set by ``make test-integration``; see the
Makefile and ``scripts/test-db.sh``). They are skipped automatically if those are not set,
so ``pytest`` without a database does not hang or error confusingly.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from piishield.audit.service import Actor
from piishield.core.config import Settings
from piishield.core.container import Container
from piishield.core.db import Base, import_all_models
from piishield.core.kv import MemoryKV
from piishield.core.sealing import LocalSealer
from piishield.main import create_app

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://piishield:piishield@localhost:5542/piishield_test"
)
TEST_REDIS_URL = os.environ.get("TEST_REDIS_URL", "")

requires_db = pytest.mark.integration


@pytest_asyncio.fixture
async def settings() -> Settings:
    return Settings(
        database_url=TEST_DATABASE_URL,
        redis_url=TEST_REDIS_URL,
        environment="test",
        api_key_pepper="test-pepper-not-for-production-use-at-all-xx",
        session_secret="test-session-secret-not-for-production-xxxx",
        local_master_key="test-local-master-key-not-for-production-xx",
    )


@pytest_asyncio.fixture
async def container(settings: Settings) -> AsyncIterator[Container]:
    import_all_models()
    c = Container.build(settings)
    async with c.db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield c
    finally:
        async with c.db.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await c.close()


@pytest_asyncio.fixture
async def session(container: Container) -> AsyncIterator[AsyncSession]:
    async with container.db.sessionmaker() as s:
        yield s


@pytest_asyncio.fixture
async def app(container: Container) -> AsyncIterator[object]:
    """The FastAPI app, with its ASGI lifespan actually run: ``httpx.ASGITransport``
    never sends the ``lifespan`` scope on its own (it only ever issues plain ``http``
    scopes per request), so without this, ``main.create_app``'s lifespan context manager
    never executes and ``app.state.container`` is never set, a 500 on every single
    request. ``LifespanManager`` drives startup/shutdown explicitly around the tests that
    use this app, exactly as a real ASGI server would on process start/stop."""
    fastapi_app = create_app(container.settings, container)
    async with LifespanManager(fastapi_app):
        yield fastapi_app


@pytest_asyncio.fixture
async def client(app: object) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def second_client(app: object) -> AsyncClient:
    """A fresh AsyncClient against the SAME app/container as the ``client`` fixture, with
    its own header state, for tests that need two independently-authenticated callers in
    one test (e.g. an org-owner session plus a separately-scoped API key). Reuses the
    ``app`` fixture's already-running lifespan; it must not be called after that fixture
    has torn down."""
    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture
def memory_kv() -> MemoryKV:
    return MemoryKV()


@pytest.fixture
def local_sealer() -> LocalSealer:
    return LocalSealer("test-local-master-key-not-for-production-xx")


def make_actor(org_id: uuid.UUID | None = None, role: str = "owner") -> Actor:
    return Actor(org_id or uuid.uuid4(), uuid.uuid4(), "test@example.com", role, kind="user")
