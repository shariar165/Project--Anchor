"""
Tests for the university-admin analytics endpoint (GET /v1/admin/analytics).

Tenant-scoped, campus-ops aggregates that drive the Uni Admin "Insights" page.
Uses SQLite in-memory + fakeredis — no Docker required.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import update

from app.models.filing import Filing, FilingState
from app.models.user import User


def _auth(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def _seed(db_session):
    from app.services.filing_svc import seed_templates
    await seed_templates(db_session)


async def _make_admin_and_relogin(client, db_session, email: str, password: str,
                                  tenant_id: uuid.UUID | None = None) -> dict:
    values = {"role": "admin"}
    if tenant_id is not None:
        values["tenant_id"] = tenant_id
    await db_session.execute(update(User).where(User.email == email).values(**values))
    await db_session.commit()
    resp = await client.post("/auth/login", json={"identifier": email, "password": password})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _submit_complaint(client, headers) -> str:
    """Create + fill + submit an attributed complaint; returns the filing id (state=routed)."""
    r = await client.post("/v1/filings", json={"template_key": "academic_rank1", "language": "en"},
                          headers=headers)
    fid = r.json()["id"]
    await client.patch(f"/v1/filings/{fid}", json={"body": "Complaint body text for testing."},
                       headers=headers)
    await client.post(f"/v1/filings/{fid}/submit", headers=headers)
    return fid


# ── Auth ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_analytics_requires_admin(client, db_session, mock_redis, registered_user):
    r = await client.get("/v1/admin/analytics", headers=_auth(registered_user["tokens"]))
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_analytics_unauthenticated(client, db_session, mock_redis):
    r = await client.get("/v1/admin/analytics")
    assert r.status_code in (401, 403)


# ── Empty tenant — full shape ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_analytics_empty_shape(client, db_session, mock_redis, registered_user):
    headers = await _make_admin_and_relogin(
        client, db_session, registered_user["email"], registered_user["password"])
    r = await client.get("/v1/admin/analytics", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()

    for key in ("filings", "applications", "alerts", "users", "content", "series", "generated_at"):
        assert key in data, f"missing top-level key {key}"

    f = data["filings"]
    assert f["total"] == 0 and f["resolution_rate"] == 0.0 and f["escalation_rate"] == 0.0
    assert f["avg_resolution_secs"] is None
    assert f["by_category"] == {} and f["by_state"] == {}

    a = data["applications"]
    assert a["total"] == 0 and a["approval_rate"] == 0.0
    assert a["by_stage"] == {"mentor": 0, "department_head": 0, "dean": 0, "accounts": 0}

    assert data["alerts"] == {"total": 0, "active": 0, "resolved_24h": 0, "false_alarm_30d": 0}
    assert data["content"] == {"notices": 0, "feed_posts": 0}

    # 14-day zero-filled series for each tracked model.
    for series_key in ("filings_14d", "applications_14d", "alerts_14d"):
        s = data["series"][series_key]
        assert len(s) == 14
        assert all(pt["count"] == 0 for pt in s)


# ── Filing counts + rate math ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_analytics_filing_counts_and_rates(client, db_session, mock_redis, registered_user):
    await _seed(db_session)
    headers = _auth(registered_user["tokens"])

    # Four submitted complaints (all start in 'routed').
    fids = [await _submit_complaint(client, headers) for _ in range(4)]
    a, b, c, d = (uuid.UUID(f) for f in fids)

    now = datetime.now(tz=timezone.utc)
    # b → under_review; c → resolved (1h window); d → escalated.
    await db_session.execute(update(Filing).where(Filing.id == b).values(state=FilingState.under_review))
    await db_session.execute(update(Filing).where(Filing.id == c).values(
        state=FilingState.resolved,
        submitted_at=now - timedelta(hours=1),
        finalized_at=now,
    ))
    await db_session.execute(update(Filing).where(Filing.id == d).values(escalation_level=2))
    await db_session.commit()

    admin_headers = await _make_admin_and_relogin(
        client, db_session, registered_user["email"], registered_user["password"])
    r = await client.get("/v1/admin/analytics", headers=admin_headers)
    assert r.status_code == 200, r.text
    f = r.json()["filings"]

    assert f["total"] == 4
    assert f["open"] == 3          # routed(a) + under_review(b) + routed(d); c excluded
    assert f["under_review"] == 1
    assert f["resolved"] == 1
    assert f["escalated"] == 1
    assert f["resolution_rate"] == 25.0    # 1/4
    assert f["escalation_rate"] == 25.0    # 1/4
    assert f["avg_resolution_secs"] is not None and f["avg_resolution_secs"] > 0
    assert f["by_category"]["complaint"] == 4

    # All four created today → last 14d point reflects them.
    series = r.json()["series"]["filings_14d"]
    assert series[-1]["count"] == 4
    assert sum(pt["count"] for pt in series) == 4


# ── Tenant isolation ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_analytics_tenant_scoped(client, db_session, mock_redis, registered_user):
    await _seed(db_session)
    headers = _auth(registered_user["tokens"])

    fids = [await _submit_complaint(client, headers) for _ in range(3)]
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()

    # Two filings under tenant A (the admin's tenant), one under tenant B.
    await db_session.execute(update(Filing).where(Filing.id == uuid.UUID(fids[0])).values(tenant_id=tenant_a))
    await db_session.execute(update(Filing).where(Filing.id == uuid.UUID(fids[1])).values(tenant_id=tenant_a))
    await db_session.execute(update(Filing).where(Filing.id == uuid.UUID(fids[2])).values(tenant_id=tenant_b))
    await db_session.commit()

    admin_headers = await _make_admin_and_relogin(
        client, db_session, registered_user["email"], registered_user["password"], tenant_id=tenant_a)
    r = await client.get("/v1/admin/analytics", headers=admin_headers)
    assert r.status_code == 200, r.text
    f = r.json()["filings"]

    # Only tenant A's two filings are visible to this admin.
    assert f["total"] == 2
    assert f["by_category"].get("complaint") == 2
