"""
Tests for the admin / proctor dashboard endpoints.

Access levels:
  - user      → 403 on all /v1/admin/* endpoints
  - moderator → list, detail, ack, resolve (own tenant only)
  - admin     → everything + false-alert
"""
import pytest
import pytest_asyncio
import uuid
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient
from sqlalchemy import select

from app.models.alert import AlertEvent, AlertBan, Zone, AlertState, ZoneStatus, ZoneType


def _auth(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


# ─── Extra role fixtures ──────────────────────────────────────────────────────

async def _make_privileged_user(client, db_session, mock_redis, role: str) -> dict:
    """
    Register as 'user', then promote role directly in DB (register only allows user/student).
    Re-login after promotion so the JWT carries the correct role.
    """
    from sqlalchemy import select, update
    from app.models.user import User, Role

    email = f"{role}_{uuid.uuid4().hex[:8]}@example.com"
    password = "SecurePass!99"

    reg = await client.post("/auth/register", json={
        "full_name": f"{role.title()} User", "email": email,
        "password": password, "role": "user", "terms": True, "data_consent": True,
    })
    otp = reg.json()["dev_otp"]
    await client.post("/auth/verify-email", json={"token": f"{email}:{otp}"})

    # Promote role in DB
    await db_session.execute(
        update(User).where(User.email == email).values(role=Role(role))
    )
    await db_session.commit()

    # Re-login to get a JWT with the new role
    login = await client.post("/auth/login", json={"identifier": email, "password": password})
    tokens = login.json()
    return {"email": email, "password": password, "tokens": tokens}


@pytest_asyncio.fixture
async def moderator_user(client, db_session, mock_redis):
    return await _make_privileged_user(client, db_session, mock_redis, "moderator")


@pytest_asyncio.fixture
async def admin_user(client, db_session, mock_redis):
    return await _make_privileged_user(client, db_session, mock_redis, "admin")


@pytest.fixture(autouse=True)
def _mock_notifications(monkeypatch):
    """Prevent background tasks from opening production DB sessions in tests."""
    async def _noop(*args, **kwargs):
        pass
    monkeypatch.setattr("app.services.alert_svc.notify_proctor", _noop)
    monkeypatch.setattr("app.services.alert_svc.notify_nearby_users", _noop)
    monkeypatch.setattr("app.services.alert_svc.notify_contacts", _noop)


# ─── Helper: create an alert via the API ─────────────────────────────────────

async def _trigger(client, tokens, lat=23.7104, lng=90.4074):
    resp = await client.post("/v1/alerts/trigger", json={
        "lat": lat, "lng": lng, "gps_status": "ok", "gps_accuracy_m": 10,
    }, headers=_auth(tokens))
    assert resp.status_code == 200, resp.text
    return resp.json()["event_id"]


# ─── Access control ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_user_cannot_access_admin_list(client: AsyncClient, registered_user, db_session, mock_redis):
    """Regular users get 403 on all admin endpoints."""
    await _trigger(client, registered_user["tokens"])
    resp = await client.get("/v1/admin/alerts", headers=_auth(registered_user["tokens"]))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_moderator_can_list_alerts(client: AsyncClient, registered_user, moderator_user, db_session, mock_redis):
    await _trigger(client, registered_user["tokens"])
    resp = await client.get("/v1/admin/alerts", headers=_auth(moderator_user["tokens"]))
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert len(data["items"]) >= 1


@pytest.mark.asyncio
async def test_admin_can_list_alerts(client: AsyncClient, registered_user, admin_user, db_session, mock_redis):
    await _trigger(client, registered_user["tokens"])
    resp = await client.get("/v1/admin/alerts", headers=_auth(admin_user["tokens"]))
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


# ─── List filtering ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_filter_by_state_active(client: AsyncClient, registered_user, admin_user, db_session, mock_redis):
    await _trigger(client, registered_user["tokens"])
    resp = await client.get("/v1/admin/alerts?state=active", headers=_auth(admin_user["tokens"]))
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert all(i["state"] == "active" for i in items)


@pytest.mark.asyncio
async def test_list_filter_by_invalid_state(client: AsyncClient, admin_user, db_session, mock_redis):
    resp = await client.get("/v1/admin/alerts?state=invalid_state", headers=_auth(admin_user["tokens"]))
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_list_pagination(client: AsyncClient, registered_user, admin_user, db_session, mock_redis):
    # Trigger two alerts (need to reset rate limit between them)
    await _trigger(client, registered_user["tokens"])
    # Reset rate limit in Redis to allow a second trigger
    r, _ = mock_redis
    from app.services.alert_svc import compute_anonymous_hash
    from app.services.token import decode_token
    payload = decode_token(registered_user["tokens"]["access_token"])
    user_hash = compute_anonymous_hash(uuid.UUID(payload["sub"]))
    from datetime import datetime
    today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    await r.delete(f"alert_daily:{user_hash}:{today}")

    await _trigger(client, registered_user["tokens"])

    # Limit=1 should return only 1 item but total >= 2
    resp = await client.get("/v1/admin/alerts?limit=1&offset=0", headers=_auth(admin_user["tokens"]))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 1
    assert data["total"] >= 2


# ─── Alert detail ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_alert_detail(client: AsyncClient, registered_user, admin_user, db_session, mock_redis):
    event_id = await _trigger(client, registered_user["tokens"])

    # Add a response so detail includes it
    await client.post(f"/v1/alerts/{event_id}/respond",
                      json={"response_type": "responding", "distance_m": 200},
                      headers=_auth(admin_user["tokens"]))

    resp = await client.get(f"/v1/admin/alerts/{event_id}", headers=_auth(admin_user["tokens"]))
    assert resp.status_code == 200
    data = resp.json()
    assert data["event_id"] == event_id
    assert data["state"] == "active"
    assert "notifications" in data
    assert "responses" in data
    assert "evidence_count" in data
    assert len(data["responses"]) == 1
    assert data["responses"][0]["response_type"] == "responding"


@pytest.mark.asyncio
async def test_get_alert_detail_not_found(client: AsyncClient, admin_user, db_session, mock_redis):
    fake_id = str(uuid.uuid4())
    resp = await client.get(f"/v1/admin/alerts/{fake_id}", headers=_auth(admin_user["tokens"]))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_detail_with_zone(client: AsyncClient, registered_user, admin_user, db_session, mock_redis):
    """Alert with GPS should have a linked zone in the detail."""
    event_id = await _trigger(client, registered_user["tokens"])
    resp = await client.get(f"/v1/admin/alerts/{event_id}", headers=_auth(admin_user["tokens"]))
    assert resp.status_code == 200
    data = resp.json()
    # Zone should be present because trigger included lat/lng
    assert data["zone"] is not None
    assert data["zone"]["zone_type"] == "alert"
    assert data["zone"]["radius_m"] == 1000


# ─── Ack ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ack_alert_as_moderator(client: AsyncClient, registered_user, moderator_user, db_session, mock_redis):
    event_id = await _trigger(client, registered_user["tokens"])
    resp = await client.post(f"/v1/admin/alerts/{event_id}/ack",
                             headers=_auth(moderator_user["tokens"]))
    assert resp.status_code == 200
    assert resp.json()["event_id"] == event_id

    # Redis key should be set
    r, _ = mock_redis
    val = await r.get(f"alert_acked:{event_id}")
    assert val is not None


@pytest.mark.asyncio
async def test_ack_alert_not_found(client: AsyncClient, moderator_user, db_session, mock_redis):
    resp = await client.post(f"/v1/admin/alerts/{uuid.uuid4()}/ack",
                             headers=_auth(moderator_user["tokens"]))
    assert resp.status_code == 404


# ─── Resolve ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_resolve_alert_as_admin(client: AsyncClient, registered_user, admin_user, db_session, mock_redis):
    event_id = await _trigger(client, registered_user["tokens"])
    resp = await client.post(f"/v1/admin/alerts/{event_id}/resolve",
                             headers=_auth(admin_user["tokens"]))
    assert resp.status_code == 200
    assert resp.json()["state"] == "resolved"

    # DB state should be resolved
    result = await db_session.execute(select(AlertEvent))
    event = result.scalars().first()
    assert event.state == AlertState.resolved
    assert event.closed_by == "admin"


@pytest.mark.asyncio
async def test_resolve_alert_as_moderator(client: AsyncClient, registered_user, moderator_user, db_session, mock_redis):
    event_id = await _trigger(client, registered_user["tokens"])
    resp = await client.post(f"/v1/admin/alerts/{event_id}/resolve",
                             headers=_auth(moderator_user["tokens"]))
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_resolve_already_closed_alert(client: AsyncClient, registered_user, admin_user, db_session, mock_redis):
    """Cannot resolve an alert that is already closed/false_alert."""
    event_id = await _trigger(client, registered_user["tokens"])
    await client.post(f"/v1/admin/alerts/{event_id}/resolve", headers=_auth(admin_user["tokens"]))
    # Second resolve should fail
    resp = await client.post(f"/v1/admin/alerts/{event_id}/resolve",
                             headers=_auth(admin_user["tokens"]))
    assert resp.status_code == 400


# ─── False alert ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_false_alert_as_admin(client: AsyncClient, registered_user, admin_user, db_session, mock_redis):
    event_id = await _trigger(client, registered_user["tokens"])
    resp = await client.post(f"/v1/admin/alerts/{event_id}/false",
                             headers=_auth(admin_user["tokens"]))
    assert resp.status_code == 200
    assert resp.json()["state"] == "false_alert"

    # DB: event state = false_alert
    result = await db_session.execute(select(AlertEvent))
    event = result.scalars().first()
    assert event.state == AlertState.false_alert

    # DB: ban created for device fingerprint
    ban_result = await db_session.execute(select(AlertBan))
    bans = ban_result.scalars().all()
    assert len(bans) == 1
    assert bans[0].device_fingerprint_hash == event.device_fingerprint_hash


@pytest.mark.asyncio
async def test_false_alert_forbidden_for_moderator(client: AsyncClient, registered_user, moderator_user, db_session, mock_redis):
    event_id = await _trigger(client, registered_user["tokens"])
    resp = await client.post(f"/v1/admin/alerts/{event_id}/false",
                             headers=_auth(moderator_user["tokens"]))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_false_alert_already_false(client: AsyncClient, registered_user, admin_user, db_session, mock_redis):
    event_id = await _trigger(client, registered_user["tokens"])
    await client.post(f"/v1/admin/alerts/{event_id}/false", headers=_auth(admin_user["tokens"]))
    resp = await client.post(f"/v1/admin/alerts/{event_id}/false",
                             headers=_auth(admin_user["tokens"]))
    assert resp.status_code == 400


# ─── Zone list ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_zones_as_admin(client: AsyncClient, registered_user, admin_user, db_session, mock_redis):
    # Trigger an alert to create an alert zone
    await _trigger(client, registered_user["tokens"])
    resp = await client.get("/v1/admin/zones", headers=_auth(admin_user["tokens"]))
    assert resp.status_code == 200
    zones = resp.json()
    assert isinstance(zones, list)
    assert len(zones) >= 1
    assert zones[0]["zone_type"] == "alert"


@pytest.mark.asyncio
async def test_list_zones_filter_by_type(client: AsyncClient, registered_user, admin_user, db_session, mock_redis):
    await _trigger(client, registered_user["tokens"])
    resp = await client.get("/v1/admin/zones?zone_type=alert", headers=_auth(admin_user["tokens"]))
    assert resp.status_code == 200
    zones = resp.json()
    assert all(z["zone_type"] == "alert" for z in zones)


@pytest.mark.asyncio
async def test_list_zones_invalid_type(client: AsyncClient, admin_user, db_session, mock_redis):
    resp = await client.get("/v1/admin/zones?zone_type=invalid", headers=_auth(admin_user["tokens"]))
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_user_cannot_list_zones(client: AsyncClient, registered_user, db_session, mock_redis):
    resp = await client.get("/v1/admin/zones", headers=_auth(registered_user["tokens"]))
    assert resp.status_code == 403


# ─── Stats endpoint ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_stats_requires_auth(client: AsyncClient, db_session, mock_redis):
    resp = await client.get("/v1/admin/alerts/stats")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_stats_requires_admin_role(client: AsyncClient, registered_user, db_session, mock_redis):
    resp = await client.get("/v1/admin/alerts/stats", headers=_auth(registered_user["tokens"]))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_stats_empty_db(client: AsyncClient, admin_user, db_session, mock_redis):
    resp = await client.get("/v1/admin/alerts/stats", headers=_auth(admin_user["tokens"]))
    assert resp.status_code == 200
    data = resp.json()
    assert data["active_count"] == 0
    assert data["resolved_24h"] == 0
    assert data["false_alarms_30d"] == 0
    assert data["avg_response_secs_24h"] is None
    assert data["by_tenant_30d"] == []
    assert data["by_zone_type_30d"] == []
    assert len(data["resolution_histogram_30d"]) == 5
    assert all(b["count"] == 0 for b in data["resolution_histogram_30d"])


@pytest.mark.asyncio
async def test_stats_active_count(client: AsyncClient, registered_user, admin_user, db_session, mock_redis):
    await _trigger(client, registered_user["tokens"])
    resp = await client.get("/v1/admin/alerts/stats", headers=_auth(admin_user["tokens"]))
    assert resp.status_code == 200
    assert resp.json()["active_count"] == 1


@pytest.mark.asyncio
async def test_stats_resolved_24h(client: AsyncClient, registered_user, admin_user, db_session, mock_redis):
    event_id = await _trigger(client, registered_user["tokens"])
    await client.post(f"/v1/admin/alerts/{event_id}/resolve", headers=_auth(admin_user["tokens"]))

    resp = await client.get("/v1/admin/alerts/stats", headers=_auth(admin_user["tokens"]))
    assert resp.status_code == 200
    assert resp.json()["resolved_24h"] == 1


@pytest.mark.asyncio
async def test_stats_false_alarms_30d(client: AsyncClient, registered_user, admin_user, db_session, mock_redis):
    event_id = await _trigger(client, registered_user["tokens"])
    await client.post(f"/v1/admin/alerts/{event_id}/false", headers=_auth(admin_user["tokens"]))

    resp = await client.get("/v1/admin/alerts/stats", headers=_auth(admin_user["tokens"]))
    assert resp.status_code == 200
    assert resp.json()["false_alarms_30d"] == 1


@pytest.mark.asyncio
async def test_stats_histogram_buckets(client: AsyncClient, registered_user, admin_user, db_session, mock_redis):
    event_id = await _trigger(client, registered_user["tokens"])
    await client.post(f"/v1/admin/alerts/{event_id}/resolve", headers=_auth(admin_user["tokens"]))

    resp = await client.get("/v1/admin/alerts/stats", headers=_auth(admin_user["tokens"]))
    assert resp.status_code == 200
    hist = resp.json()["resolution_histogram_30d"]
    assert len(hist) == 5
    buckets = [b["bucket"] for b in hist]
    assert buckets == ["<2m", "2–5m", "5–10m", "10–30m", ">30m"]
    # Just-resolved alert (sub-second) lands in "<2m"
    assert hist[0]["count"] == 1


@pytest.mark.asyncio
async def test_stats_by_zone_type(client: AsyncClient, registered_user, admin_user, db_session, mock_redis):
    await _trigger(client, registered_user["tokens"])
    resp = await client.get("/v1/admin/alerts/stats", headers=_auth(admin_user["tokens"]))
    assert resp.status_code == 200
    by_zone = resp.json()["by_zone_type_30d"]
    # Trigger creates an "alert" zone, so we expect one entry
    assert len(by_zone) == 1
    assert by_zone[0]["zone_type"] == "alert"
    assert by_zone[0]["count"] == 1


@pytest.mark.asyncio
async def test_stats_moderator_can_access(client: AsyncClient, registered_user, moderator_user, db_session, mock_redis):
    await _trigger(client, registered_user["tokens"])
    resp = await client.get("/v1/admin/alerts/stats", headers=_auth(moderator_user["tokens"]))
    assert resp.status_code == 200
    # Moderator sees stats (possibly scoped to their tenant)
    assert "active_count" in resp.json()


# ─── Admin actions: dispatch / notify-university / anonymous-call ─────────────

@pytest.mark.asyncio
async def test_dispatch_records_action(client: AsyncClient, registered_user, admin_user, db_session, mock_redis):
    event_id = await _trigger(client, registered_user["tokens"])
    resp = await client.post(f"/v1/admin/alerts/{event_id}/dispatch",
                             json={"note": "Team Bravo en route"}, headers=_auth(admin_user["tokens"]))
    assert resp.status_code == 200, resp.text
    assert resp.json()["action_type"] == "dispatch"

    # Action surfaces in the detail endpoint
    detail = await client.get(f"/v1/admin/alerts/{event_id}", headers=_auth(admin_user["tokens"]))
    actions = detail.json()["admin_actions"]
    assert len(actions) == 1
    assert actions[0]["action_type"] == "dispatch"
    assert actions[0]["note"] == "Team Bravo en route"
    # Actor email is masked, never plaintext
    assert "***" in actions[0]["actor"]


@pytest.mark.asyncio
async def test_notify_university_and_anonymous_call(client: AsyncClient, registered_user, admin_user, db_session, mock_redis):
    event_id = await _trigger(client, registered_user["tokens"])
    r1 = await client.post(f"/v1/admin/alerts/{event_id}/notify-university", json={},
                           headers=_auth(admin_user["tokens"]))
    r2 = await client.post(f"/v1/admin/alerts/{event_id}/anonymous-call", json={},
                           headers=_auth(admin_user["tokens"]))
    assert r1.status_code == 200 and r1.json()["action_type"] == "notify_university"
    assert r2.status_code == 200 and r2.json()["action_type"] == "anonymous_call"

    detail = await client.get(f"/v1/admin/alerts/{event_id}", headers=_auth(admin_user["tokens"]))
    types = {a["action_type"] for a in detail.json()["admin_actions"]}
    assert types == {"notify_university", "anonymous_call"}


@pytest.mark.asyncio
async def test_moderator_can_dispatch(client: AsyncClient, registered_user, moderator_user, db_session, mock_redis):
    event_id = await _trigger(client, registered_user["tokens"])
    resp = await client.post(f"/v1/admin/alerts/{event_id}/dispatch", json={},
                             headers=_auth(moderator_user["tokens"]))
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_user_cannot_dispatch(client: AsyncClient, registered_user, db_session, mock_redis):
    event_id = await _trigger(client, registered_user["tokens"])
    resp = await client.post(f"/v1/admin/alerts/{event_id}/dispatch", json={},
                             headers=_auth(registered_user["tokens"]))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_dispatch_unknown_event_404(client: AsyncClient, admin_user, db_session, mock_redis):
    resp = await client.post(f"/v1/admin/alerts/{uuid.uuid4()}/dispatch", json={},
                             headers=_auth(admin_user["tokens"]))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_detail_acked_reflects_ack(client: AsyncClient, registered_user, admin_user, db_session, mock_redis):
    event_id = await _trigger(client, registered_user["tokens"])
    before = await client.get(f"/v1/admin/alerts/{event_id}", headers=_auth(admin_user["tokens"]))
    assert before.json()["acked"] is False
    await client.post(f"/v1/admin/alerts/{event_id}/ack", headers=_auth(admin_user["tokens"]))
    after = await client.get(f"/v1/admin/alerts/{event_id}", headers=_auth(admin_user["tokens"]))
    assert after.json()["acked"] is True


# ─── Alert CSV export ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_export_alerts_csv(client: AsyncClient, registered_user, admin_user, db_session, mock_redis):
    event_id = await _trigger(client, registered_user["tokens"])
    resp = await client.get("/v1/admin/alerts/export?window=24h", headers=_auth(admin_user["tokens"]))
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "attachment" in resp.headers.get("content-disposition", "")
    body = resp.text
    assert "event_id,state,created_at" in body
    assert event_id in body


@pytest.mark.asyncio
async def test_export_alerts_bad_window(client: AsyncClient, admin_user, db_session, mock_redis):
    resp = await client.get("/v1/admin/alerts/export?window=99y", headers=_auth(admin_user["tokens"]))
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_export_route_not_shadowed_by_detail(client: AsyncClient, admin_user, db_session, mock_redis):
    """Regression: GET /alerts/export must resolve to the export route, not /alerts/{event_id}."""
    resp = await client.get("/v1/admin/alerts/export", headers=_auth(admin_user["tokens"]))
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
