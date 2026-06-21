"""
Tests for the admin filing stats endpoint (GET /v1/admin/filings/stats).

Drives the University Admin dashboard KPIs, inflow chart, and category breakdown.
Uses SQLite in-memory + fakeredis — no Docker required.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import update

from app.deps import get_current_user, require_stepup
from app.main import app as _app
from app.models.filing import Filing, FilingState


@pytest.fixture(autouse=True)
def _bypass_stepup():
    _app.dependency_overrides[require_stepup] = get_current_user
    yield
    _app.dependency_overrides.pop(require_stepup, None)


def _auth(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def _seed(db_session):
    from app.services.filing_svc import seed_templates
    await seed_templates(db_session)


async def _make_admin_and_relogin(client, db_session, email: str, password: str) -> dict:
    from app.models.user import User
    await db_session.execute(update(User).where(User.email == email).values(role="admin"))
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
async def test_filing_stats_requires_admin(client, db_session, mock_redis, registered_user):
    r = await client.get("/v1/admin/filings/stats", headers=_auth(registered_user["tokens"]))
    assert r.status_code in (401, 403)


# ── Empty tenant ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_filing_stats_empty(client, db_session, mock_redis, registered_user):
    headers = await _make_admin_and_relogin(
        client, db_session, registered_user["email"], registered_user["password"])
    r = await client.get("/v1/admin/filings/stats", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["open"] == 0
    assert data["under_review"] == 0
    assert data["resolved"] == 0
    assert data["escalated"] == 0
    assert data["total"] == 0
    assert data["avg_resolution_secs"] is None
    assert data["by_state"] == {}
    assert data["by_category"] == {}
    # Inflow series is always 30 zero-filled days.
    assert len(data["inflow_30d"]) == 30
    assert all(pt["count"] == 0 for pt in data["inflow_30d"])


# ── Counts ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_filing_stats_counts(client, db_session, mock_redis, registered_user):
    await _seed(db_session)
    headers = _auth(registered_user["tokens"])

    # Four submitted complaints (all start in 'routed').
    fids = [await _submit_complaint(client, headers) for _ in range(4)]
    a, b, c, d = (uuid.UUID(f) for f in fids)

    now = datetime.now(tz=timezone.utc)
    # b → under_review; c → resolved (with a 1h resolution window); d → escalated.
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
    r = await client.get("/v1/admin/filings/stats", headers=admin_headers)
    assert r.status_code == 200, r.text
    data = r.json()

    assert data["total"] == 4
    # open = routed(a) + under_review(b) + routed(d) = 3  (c is resolved, excluded)
    assert data["open"] == 3
    assert data["under_review"] == 1
    assert data["resolved"] == 1
    assert data["escalated"] == 1  # d: escalation_level>0 and not finalized
    assert data["by_category"]["complaint"] == 4
    assert data["avg_resolution_secs"] is not None
    assert data["avg_resolution_secs"] > 0

    # All four were created today → last inflow point reflects them.
    assert data["inflow_30d"][-1]["count"] == 4
    assert sum(pt["count"] for pt in data["inflow_30d"]) == 4
