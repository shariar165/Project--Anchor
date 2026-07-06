"""
Shared pytest fixtures for Anchor AI backend tests.

Uses SQLite in-memory (aiosqlite) + fakeredis — no Docker required.
Every test function gets a fresh DB, a fresh Redis, and rate limiting disabled.
"""
import os
import uuid

# Must be set BEFORE importing app modules so get_settings() picks them up
os.environ.setdefault("HIBP_CHECK_ENABLED", "false")
os.environ.setdefault("ENVIRONMENT", "testing")
# Tests must be hermetic — never hit the live Gemini API even when the developer's
# .env carries a real GEMINI_API_KEY. An (empty) env var overrides the .env value,
# so AI features deterministically fall back to Ollama/stub paths under test.
os.environ["GEMINI_API_KEY"] = ""
# Solver runs in-thread under test: subprocess spawn (the prod default) costs
# seconds per solve and breaks monkeypatching of timetable_solver.solve.
os.environ.setdefault("SOLVER_ISOLATION", "thread")

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db
from app.redis import get_redis
from app.limiter import limiter

# Import all models so Base.metadata knows every table.
# 'from app import models' binds 'models' locally, NOT 'app',
# so the FastAPI 'app' variable above is not shadowed.
from app import models as _models  # noqa: F401

_TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


# ---------------------------------------------------------------------------
# Global autouse fixtures — applied to every test automatically
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _disable_hibp(monkeypatch):
    """Skip HIBP network call in every test."""
    async def _no_hibp(password: str) -> bool:
        return False
    monkeypatch.setattr("app.services.password.check_pwned", _no_hibp)


@pytest.fixture(autouse=True)
def _disable_email(monkeypatch):
    """Block real email delivery in tests so dev_otp is always returned by /auth/register."""
    async def _fake_send(to: str, subject: str, html_content: str) -> bool:
        return False
    monkeypatch.setattr("app.services.email.send_email", _fake_send)


@pytest.fixture(autouse=True)
def _disable_rate_limit():
    """
    Disable slowapi rate limiting for all tests.
    Without this, the 10-req/min limits accumulate across tests sharing
    the same in-process app instance and trigger 429s in later tests.
    """
    limiter.enabled = False
    yield
    limiter.enabled = True


# ---------------------------------------------------------------------------
# Core fixtures — opt-in by declaring as a test parameter
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def db_session():
    """
    Per-test SQLite in-memory database with a fresh schema.

    StaticPool ensures all async tasks share the same single connection —
    required for in-memory SQLite (separate connections are separate databases).

    Overrides get_db so FastAPI route handlers use the SAME session object
    as the test code, making db_session.execute() results immediately visible
    to handler queries without needing an extra commit cycle.
    """
    engine = create_async_engine(
        _TEST_DB_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session = AsyncSession(engine, expire_on_commit=False)

    async def _override_get_db():
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

    app.dependency_overrides[get_db] = _override_get_db
    yield session

    await session.close()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
    app.dependency_overrides.pop(get_db, None)


@pytest_asyncio.fixture
async def mock_redis():
    """
    In-memory Redis (fakeredis) that overrides get_redis for the test.

    Yields a tuple (FakeRedis, dict) so older tests that unpack
    ``redis_client, redis_store = mock_redis`` continue to work.
    The dict is a lightweight proxy — inspect the FakeRedis directly for
    exact key values.
    """
    from fakeredis.aioredis import FakeRedis

    r = FakeRedis(decode_responses=True)
    store: dict = {}   # placeholder second element kept for back-compat

    def _override_get_redis():
        return r

    app.dependency_overrides[get_redis] = _override_get_redis
    yield r, store

    await r.aclose()
    app.dependency_overrides.pop(get_redis, None)


@pytest_asyncio.fixture
async def client(db_session, mock_redis):
    """
    httpx AsyncClient wired to the FastAPI ASGI app.

    Depends on db_session and mock_redis so their dependency overrides are
    installed before the first HTTP request is dispatched.
    """
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


@pytest_asyncio.fixture
async def registered_user(client, mock_redis):
    """
    Register + email-verify an active user; returns dict with email/password/tokens.
    Requires the client fixture (which sets up db_session + mock_redis).
    """
    r, _ = mock_redis
    email = f"testuser_{uuid.uuid4().hex[:8]}@example.com"
    password = "SecurePass!99"

    reg = await client.post("/auth/register", json={
        "full_name": "Test User",
        "email": email,
        "password": password,
        "role": "user",
        "terms": True,
        "data_consent": True,
    })
    assert reg.status_code == 201, f"Register failed: {reg.json()}"
    otp = reg.json()["dev_otp"]

    verify = await client.post("/auth/verify-email", json={"token": f"{email}:{otp}"})
    assert verify.status_code == 200, f"Verify failed: {verify.json()}"
    tokens = verify.json()

    return {"email": email, "password": password, "tokens": tokens}
