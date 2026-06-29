"""
Tests for the super-admin System dashboards:
  - /v1/super-admin/ai-health
  - /v1/super-admin/keys/health
  - /v1/super-admin/analytics
  - /v1/super-admin/incidents (full CRUD + timeline)

Uses SQLite in-memory + fakeredis — no Docker. The RAG microservice is not
running in tests, so AI-health / analytics must degrade gracefully (200 with
degraded payload), never 503.
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


# ── Auth gates ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize("path", [
    "/v1/super-admin/ai-health",
    "/v1/super-admin/keys/health",
    "/v1/super-admin/analytics",
    "/v1/super-admin/incidents",
])
async def test_regular_user_forbidden(client, db_session, mock_redis, registered_user, path):
    r = await client.get(path, headers=_auth(registered_user["tokens"]))
    assert r.status_code == 403


# ── AI engine health ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ai_health_degrades_without_rag(client, db_session, mock_redis):
    sa = await _make_super_admin(client, db_session)
    r = await client.get("/v1/super-admin/ai-health", headers=_auth(sa["tokens"]))
    assert r.status_code == 200, r.json()
    body = r.json()
    # RAG not running in tests → unreachable, but endpoint still renders.
    assert body["rag_reachable"] is False
    assert set(body["components"].keys()) == {"pipeline", "embedder", "chromadb", "gemini", "ollama"}
    assert "host" in body and "namespaces" in body


# ── Keys health ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_keys_health_shape_and_no_secrets(client, db_session, mock_redis):
    sa = await _make_super_admin(client, db_session)
    r = await client.get("/v1/super-admin/keys/health", headers=_auth(sa["tokens"]))
    assert r.status_code == 200, r.json()
    body = r.json()
    assert body["jwt"]["algorithm"] == "EdDSA"
    assert body["jwt"]["fingerprint"].startswith("SHA256:")
    # SEC-12 surfaced honestly.
    assert body["totp"]["encrypted_at_rest"] is False
    # Audit chain verifies clean on a fresh DB.
    assert body["audit_chain"]["ok"] in (True, None)
    # Never leak private/secret material anywhere in the payload.
    blob = str(body).lower()
    assert "private" not in body["jwt"].get("source", "")
    assert "begin private key" not in blob


# ── Analytics ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_analytics_counts_users(client, db_session, mock_redis):
    sa = await _make_super_admin(client, db_session)
    r = await client.get("/v1/super-admin/analytics", headers=_auth(sa["tokens"]))
    assert r.status_code == 200, r.json()
    body = r.json()
    # At least the super-admin user exists.
    assert body["users"]["total"] >= 1
    assert "by_role" in body["users"]
    assert len(body["series"]["alerts_14d"]) == 14
    assert body["alerts"]["total"] >= 0


# ── Incidents CRUD ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_incident_lifecycle(client, db_session, mock_redis):
    sa = await _make_super_admin(client, db_session)
    headers = _auth(sa["tokens"])

    # Create
    create = await client.post("/v1/super-admin/incidents", headers=headers, json={
        "title": "RAG latency spike",
        "description": "p95 over 5s",
        "severity": "sev2",
        "component": "RAG",
    })
    assert create.status_code == 200, create.json()
    inc = create.json()
    assert inc["status"] == "investigating"
    assert inc["is_open"] is True
    assert inc["mttr_seconds"] is None
    assert len(inc["updates"]) == 1  # opening update seeded
    inc_id = inc["id"]

    # List shows it
    lst = await client.get("/v1/super-admin/incidents", headers=headers)
    assert lst.status_code == 200
    assert lst.json()["open_count"] >= 1

    # Add a timeline update
    upd = await client.post(f"/v1/super-admin/incidents/{inc_id}/updates", headers=headers,
                            json={"note": "Identified slow embedder", "status": "identified"})
    assert upd.status_code == 200, upd.json()
    assert upd.json()["status"] == "identified"
    assert len(upd.json()["updates"]) == 2

    # Resolve via PATCH → sets resolved_at + MTTR
    patch = await client.patch(f"/v1/super-admin/incidents/{inc_id}", headers=headers,
                               json={"status": "resolved", "postmortem": "Restarted embedder pod."})
    assert patch.status_code == 200, patch.json()
    resolved = patch.json()
    assert resolved["status"] == "resolved"
    assert resolved["is_open"] is False
    assert resolved["resolved_at"] is not None
    assert resolved["mttr_seconds"] is not None and resolved["mttr_seconds"] >= 0
    assert resolved["postmortem"] == "Restarted embedder pod."

    # Detail fetch
    detail = await client.get(f"/v1/super-admin/incidents/{inc_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["status"] == "resolved"


@pytest.mark.asyncio
async def test_incident_validation_and_audit(client, db_session, mock_redis):
    sa = await _make_super_admin(client, db_session)
    headers = _auth(sa["tokens"])

    bad = await client.post("/v1/super-admin/incidents", headers=headers,
                            json={"title": "x bad sev", "severity": "sev9"})
    assert bad.status_code == 422

    await client.post("/v1/super-admin/incidents", headers=headers,
                      json={"title": "Audited incident", "severity": "sev3"})
    rows = (await db_session.execute(
        select(AuditLog).where(AuditLog.event_type == "incident_created")
    )).scalars().all()
    assert len(rows) >= 1


@pytest.mark.asyncio
async def test_incident_filter_open_only(client, db_session, mock_redis):
    sa = await _make_super_admin(client, db_session)
    headers = _auth(sa["tokens"])

    c = await client.post("/v1/super-admin/incidents", headers=headers,
                          json={"title": "Resolve me now", "severity": "sev4"})
    inc_id = c.json()["id"]
    await client.patch(f"/v1/super-admin/incidents/{inc_id}", headers=headers,
                       json={"status": "resolved"})

    open_list = await client.get("/v1/super-admin/incidents?open_only=true", headers=headers)
    assert open_list.status_code == 200
    assert all(i["status"] != "resolved" for i in open_list.json()["items"])
