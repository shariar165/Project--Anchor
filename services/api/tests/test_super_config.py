"""
Tests for super-admin platform config (/v1/super-admin/config) and the
legal-corpus proxy guards (/v1/super-admin/corpus, /ai/ingest).

Uses SQLite in-memory + fakeredis — no Docker required. The corpus proxy tests
assert the auth gate and graceful 503 when the RAG service is unreachable (it
is not running in the test environment).
"""
import uuid

import pytest
from sqlalchemy import update, select

from app.models.user import User, Role
from app.models.audit import AuditLog


def _auth(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def _make_super_admin(client, db_session) -> dict:
    email = f"superadmin_{uuid.uuid4().hex[:8]}@example.com"
    password = "SuperSecure!99"
    reg = await client.post("/auth/register", json={
        "full_name": "AiVion Platform Team",
        "email": email, "password": password, "role": "user",
        "terms": True, "data_consent": True,
    })
    assert reg.status_code == 201, reg.json()
    otp = reg.json()["dev_otp"]
    verify = await client.post("/auth/verify-email", json={"token": f"{email}:{otp}"})
    assert verify.status_code == 200, verify.json()
    await db_session.execute(update(User).where(User.email == email).values(role=Role.super_admin))
    await db_session.commit()
    login = await client.post("/auth/login", json={"identifier": email, "password": password})
    assert login.status_code == 200, login.json()
    return {"email": email, "password": password, "tokens": login.json()}


# ── Policy config ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_regular_user_cannot_read_config(client, db_session, mock_redis, registered_user):
    r = await client.get("/v1/super-admin/config", headers=_auth(registered_user["tokens"]))
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_super_admin_get_returns_defaults(client, db_session, mock_redis):
    sa = await _make_super_admin(client, db_session)
    r = await client.get("/v1/super-admin/config", headers=_auth(sa["tokens"]))
    assert r.status_code == 200
    cfg = r.json()
    # Defaults from schemas/platform_config.py
    assert cfg["rate_limits"]["ai_queries_per_hour"] == 60
    assert cfg["escalation"]["level1_to_level2_hours"] == 72
    assert cfg["pdpo"]["right_to_access"] is True
    assert "en" in cfg["disclaimer"] and "bn" in cfg["disclaimer"]


@pytest.mark.asyncio
async def test_super_admin_patch_persists_and_merges(client, db_session, mock_redis):
    sa = await _make_super_admin(client, db_session)
    headers = _auth(sa["tokens"])

    patch = {"sections": {"rate_limits": {
        "complaint_filing_per_24h": 9,
        "active_alerts_per_24h": 4,
        "news_publishing_per_hour": 2,
        "ai_queries_per_hour": 120,
    }}}
    r = await client.patch("/v1/super-admin/config", json=patch, headers=headers)
    assert r.status_code == 200, r.json()
    assert r.json()["rate_limits"]["ai_queries_per_hour"] == 120

    # Second GET reflects the saved value; untouched sections keep defaults.
    r2 = await client.get("/v1/super-admin/config", headers=headers)
    assert r2.status_code == 200
    cfg = r2.json()
    assert cfg["rate_limits"]["complaint_filing_per_24h"] == 9
    assert cfg["escalation"]["level1_to_level2_hours"] == 72  # untouched default


@pytest.mark.asyncio
async def test_patch_writes_audit_row(client, db_session, mock_redis):
    sa = await _make_super_admin(client, db_session)
    await client.patch(
        "/v1/super-admin/config",
        json={"sections": {"bans": {"complaint_spam_days": 21}}},
        headers=_auth(sa["tokens"]),
    )
    rows = (await db_session.execute(
        select(AuditLog).where(AuditLog.event_type == "platform_config_updated")
    )).scalars().all()
    assert len(rows) >= 1
    assert "bans" in (rows[-1].metadata_ or {}).get("sections", [])


@pytest.mark.asyncio
async def test_patch_requires_super_admin(client, db_session, mock_redis, registered_user):
    r = await client.patch(
        "/v1/super-admin/config",
        json={"sections": {"bans": {"complaint_spam_days": 1}}},
        headers=_auth(registered_user["tokens"]),
    )
    assert r.status_code == 403


# ── Legal corpus proxy guards ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_corpus_requires_super_admin(client, db_session, mock_redis, registered_user):
    r = await client.get(
        "/v1/super-admin/corpus/documents?namespace=national",
        headers=_auth(registered_user["tokens"]),
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_corpus_returns_503_when_rag_unreachable(client, db_session, mock_redis):
    """With RAG not running, the proxy must degrade to 503 — not 500."""
    sa = await _make_super_admin(client, db_session)
    r = await client.get(
        "/v1/super-admin/corpus/documents?namespace=national",
        headers=_auth(sa["tokens"]),
    )
    assert r.status_code == 503


@pytest.mark.asyncio
async def test_ai_ingest_now_requires_super_admin(client, db_session, mock_redis, registered_user):
    """The previously-unauthenticated sample-corpus reload is now guarded."""
    r = await client.post("/ai/ingest", json={}, headers=_auth(registered_user["tokens"]))
    assert r.status_code == 403
