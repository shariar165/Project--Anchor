"""
Tests for the Super-Admin audit-log explorer (/v1/admin/audit).

The audit trail is platform-wide and Super-Admin only. The backend writes
SHA-256 hash-chained rows via services/audit.py::log_event; this exercises the
read/filter/verify/export side, plus access control and actor masking.
"""
import uuid
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select, update

from app.models.user import User, Role
from app.models.audit import AuditLog
from app.services.audit import log_event


def _auth(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def _make_privileged_user(client, db_session, role: str) -> dict:
    email = f"{role}_{uuid.uuid4().hex[:8]}@example.com"
    password = "SecurePass!99"
    reg = await client.post("/auth/register", json={
        "full_name": f"{role.title()} User", "email": email,
        "password": password, "role": "user", "terms": True, "data_consent": True,
    })
    otp = reg.json()["dev_otp"]
    await client.post("/auth/verify-email", json={"token": f"{email}:{otp}"})
    await db_session.execute(update(User).where(User.email == email).values(role=Role(role)))
    await db_session.commit()
    login = await client.post("/auth/login", json={"identifier": email, "password": password})
    return {"email": email, "password": password, "tokens": login.json()}


@pytest_asyncio.fixture
async def super_admin(client, db_session, mock_redis):
    return await _make_privileged_user(client, db_session, "super_admin")


@pytest_asyncio.fixture
async def plain_admin(client, db_session, mock_redis):
    return await _make_privileged_user(client, db_session, "admin")


async def _user_id(db_session, email: str) -> uuid.UUID:
    res = await db_session.execute(select(User.id).where(User.email == email))
    return res.scalar_one()


async def _seed(db_session, event_type, user_id=None, metadata=None):
    await log_event(db_session, event_type, user_id=user_id, ip_address="10.0.0.1", metadata=metadata)
    await db_session.commit()


# ─── Access control ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_user_cannot_read_audit(client: AsyncClient, registered_user, db_session, mock_redis):
    resp = await client.get("/v1/admin/audit", headers=_auth(registered_user["tokens"]))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_plain_admin_cannot_read_audit(client: AsyncClient, plain_admin, db_session, mock_redis):
    """Audit is Super-Admin only — a tenant admin must be rejected."""
    resp = await client.get("/v1/admin/audit", headers=_auth(plain_admin["tokens"]))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_super_admin_can_read_audit(client: AsyncClient, super_admin, db_session, mock_redis):
    await _seed(db_session, "test_event_alpha")
    resp = await client.get("/v1/admin/audit", headers=_auth(super_admin["tokens"]))
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data and "total" in data
    assert any(i["event_type"] == "test_event_alpha" for i in data["items"])


# ─── Filtering ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_filter_prefix(client: AsyncClient, super_admin, db_session, mock_redis):
    await _seed(db_session, "alert_dispatched_by_admin")
    await _seed(db_session, "feed_post_created")
    resp = await client.get("/v1/admin/audit?prefix=alert_", headers=_auth(super_admin["tokens"]))
    assert resp.status_code == 200
    types = [i["event_type"] for i in resp.json()["items"]]
    assert types  # non-empty
    assert all(t.startswith("alert_") for t in types)


@pytest.mark.asyncio
async def test_filter_event_type_exact(client: AsyncClient, super_admin, db_session, mock_redis):
    await _seed(db_session, "zone_created_by_admin")
    resp = await client.get("/v1/admin/audit?event_type=zone_created_by_admin",
                            headers=_auth(super_admin["tokens"]))
    assert all(i["event_type"] == "zone_created_by_admin" for i in resp.json()["items"])


@pytest.mark.asyncio
async def test_filter_q_matches_metadata(client: AsyncClient, super_admin, db_session, mock_redis):
    await _seed(db_session, "thing_happened", metadata={"event_id": "needle-12345"})
    resp = await client.get("/v1/admin/audit?q=needle-12345", headers=_auth(super_admin["tokens"]))
    assert resp.status_code == 200
    assert len(resp.json()["items"]) >= 1


@pytest.mark.asyncio
async def test_filter_role(client: AsyncClient, super_admin, registered_user, db_session, mock_redis):
    uid = await _user_id(db_session, registered_user["email"])
    await _seed(db_session, "user_did_thing", user_id=uid)
    # Filter to a role nobody in our seeded rows has → empty
    resp = await client.get("/v1/admin/audit?role=moderator", headers=_auth(super_admin["tokens"]))
    assert resp.status_code == 200
    assert all(i["actor"]["role"] == "moderator" for i in resp.json()["items"])


@pytest.mark.asyncio
async def test_bad_date_returns_400(client: AsyncClient, super_admin, db_session, mock_redis):
    resp = await client.get("/v1/admin/audit?date_from=not-a-date", headers=_auth(super_admin["tokens"]))
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_bad_role_returns_400(client: AsyncClient, super_admin, db_session, mock_redis):
    resp = await client.get("/v1/admin/audit?role=wizard", headers=_auth(super_admin["tokens"]))
    assert resp.status_code == 400


# ─── Pagination ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_pagination(client: AsyncClient, super_admin, db_session, mock_redis):
    for i in range(5):
        await _seed(db_session, f"paged_event_{i}")
    page = await client.get("/v1/admin/audit?limit=2&offset=0", headers=_auth(super_admin["tokens"]))
    assert page.status_code == 200
    body = page.json()
    assert body["limit"] == 2
    assert len(body["items"]) == 2
    assert body["total"] >= 5


# ─── Actor masking ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_actor_email_is_masked(client: AsyncClient, super_admin, registered_user, db_session, mock_redis):
    uid = await _user_id(db_session, registered_user["email"])
    await _seed(db_session, "masking_check", user_id=uid)
    resp = await client.get("/v1/admin/audit?event_type=masking_check",
                            headers=_auth(super_admin["tokens"]))
    item = resp.json()["items"][0]
    masked = item["actor"]["masked_email"]
    assert "***" in masked
    assert registered_user["email"] not in masked  # full email never leaks


@pytest.mark.asyncio
async def test_system_event_actor_is_system(client: AsyncClient, super_admin, db_session, mock_redis):
    await _seed(db_session, "system_event", user_id=None)
    resp = await client.get("/v1/admin/audit?event_type=system_event",
                            headers=_auth(super_admin["tokens"]))
    item = resp.json()["items"][0]
    assert item["actor"]["masked_email"] == "system"
    assert item["actor"]["user_id"] is None


# ─── Chain verification ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_verify_ok_on_clean_chain(client: AsyncClient, super_admin, db_session, mock_redis):
    await _seed(db_session, "clean_1")
    await _seed(db_session, "clean_2")
    resp = await client.get("/v1/admin/audit/verify", headers=_auth(super_admin["tokens"]))
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["first_tampered_id"] is None


@pytest.mark.asyncio
async def test_verify_detects_tampering(client: AsyncClient, super_admin, db_session, mock_redis):
    await _seed(db_session, "tamper_target", metadata={"v": 1})
    res = await db_session.execute(
        select(AuditLog).where(AuditLog.event_type == "tamper_target")
    )
    row = res.scalars().first()
    # Mutate the metadata without recomputing the stored hash → chain breaks
    await db_session.execute(
        update(AuditLog).where(AuditLog.id == row.id).values(metadata_={"v": 999})
    )
    await db_session.commit()

    resp = await client.get("/v1/admin/audit/verify", headers=_auth(super_admin["tokens"]))
    body = resp.json()
    assert body["ok"] is False
    assert body["first_tampered_id"] == str(row.id)


# ─── CSV export ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_export_csv(client: AsyncClient, super_admin, db_session, mock_redis):
    await _seed(db_session, "exported_event")
    resp = await client.get("/v1/admin/audit/export", headers=_auth(super_admin["tokens"]))
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "attachment" in resp.headers.get("content-disposition", "")
    assert "timestamp,event_type" in resp.text
    assert "exported_event" in resp.text


@pytest.mark.asyncio
async def test_export_requires_super_admin(client: AsyncClient, plain_admin, db_session, mock_redis):
    resp = await client.get("/v1/admin/audit/export", headers=_auth(plain_admin["tokens"]))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_verify_route_not_shadowed(client: AsyncClient, super_admin, db_session, mock_redis):
    """Regression: /audit/verify and /audit/export are literals, not captured by a param route."""
    v = await client.get("/v1/admin/audit/verify", headers=_auth(super_admin["tokens"]))
    assert v.status_code == 200
    assert "ok" in v.json()
