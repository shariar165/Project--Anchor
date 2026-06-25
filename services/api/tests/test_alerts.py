"""
Tests for the Emergency Alert System.

Uses the standard fixtures from conftest.py:
  db_session, mock_redis, client, registered_user

FCM and SMS are automatically no-ops in tests because:
  - FCM: no service account configured → graceful fallback to logging
  - SMS: no SMS_API_URL set → console fallback
"""
import pytest
import pytest_asyncio
import uuid
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient
from sqlalchemy import select

from app.models.alert import (
    AlertEvent, AlertPhase1Record, AlertBan, AlertResponse,
    AlertEvidence, UserFCMToken, UserLocationSnapshot, Zone,
    AlertState, ResponseType,
)


def _auth(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest.fixture(autouse=True)
def _mock_notifications(monkeypatch):
    """
    Prevent background notification tasks from opening production DB sessions.
    Background tasks (notify_proctor, notify_nearby_users, notify_contacts) use
    AsyncSessionLocal() which would connect to PostgreSQL in tests — replace them
    with async no-ops.
    """
    async def _noop(*args, **kwargs):
        pass
    monkeypatch.setattr("app.services.alert_svc.notify_proctor", _noop)
    monkeypatch.setattr("app.services.alert_svc.notify_nearby_users", _noop)
    monkeypatch.setattr("app.services.alert_svc.notify_contacts", _noop)
    monkeypatch.setattr("app.services.alert_svc.notify_responders_safe", _noop)


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def second_user(client, mock_redis):
    """A second registered user for responder tests."""
    r, _ = mock_redis
    email = f"second_{uuid.uuid4().hex[:8]}@example.com"
    password = "SecurePass!99"
    reg = await client.post("/auth/register", json={
        "full_name": "Second User",
        "email": email,
        "password": password,
        "role": "user",
        "terms": True,
        "data_consent": True,
    })
    otp = reg.json()["dev_otp"]
    verify = await client.post("/auth/verify-email", json={"token": f"{email}:{otp}"})
    return {"email": email, "password": password, "tokens": verify.json()}


@pytest_asyncio.fixture
async def alert_event_id(client, registered_user):
    """Trigger an alert and return the event_id UUID."""
    resp = await client.post("/v1/alerts/trigger", json={
        "lat": 23.7104, "lng": 90.4074, "gps_status": "ok", "gps_accuracy_m": 10,
    }, headers=_auth(registered_user["tokens"]))
    assert resp.status_code == 200, resp.text
    return resp.json()["event_id"]


# ─── Phase 1 tests ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_phase1_save(client: AsyncClient, registered_user, db_session, mock_redis):
    resp = await client.post("/v1/alerts/phase1", json={
        "threat_description": "Someone is following me.",
        "emergency_contacts": [
            {"name": "Bappa", "phone": "+8801712000001", "relationship": "brother"}
        ],
    }, headers=_auth(registered_user["tokens"]))
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_phase1_upsert_idempotent(client: AsyncClient, registered_user, db_session, mock_redis):
    """Saving Phase 1 twice must not create duplicate rows."""
    for _ in range(2):
        await client.post("/v1/alerts/phase1", json={
            "threat_description": "Updated threat info.",
            "emergency_contacts": [],
        }, headers=_auth(registered_user["tokens"]))

    result = await db_session.execute(select(AlertPhase1Record))
    records = result.scalars().all()
    assert len(records) == 1


# ─── Trigger alert tests ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_trigger_alert_success(client: AsyncClient, registered_user, db_session, mock_redis):
    resp = await client.post("/v1/alerts/trigger", json={
        "lat": 23.7104, "lng": 90.4074, "gps_status": "ok", "gps_accuracy_m": 15,
    }, headers=_auth(registered_user["tokens"]))
    assert resp.status_code == 200
    data = resp.json()
    assert data["state"] == "active"
    assert "event_id" in data

    # Verify event persisted in DB
    result = await db_session.execute(select(AlertEvent))
    events = result.scalars().all()
    assert len(events) == 1
    assert events[0].state == AlertState.active
    assert events[0].lat == pytest.approx(23.7104, abs=0.0001)


@pytest.mark.asyncio
async def test_trigger_alert_no_gps(client: AsyncClient, registered_user, db_session, mock_redis):
    """Alert without GPS should still succeed."""
    resp = await client.post("/v1/alerts/trigger", json={
        "gps_status": "unavailable",
    }, headers=_auth(registered_user["tokens"]))
    assert resp.status_code == 200
    assert resp.json()["state"] == "active"


@pytest.mark.asyncio
async def test_trigger_alert_rate_limit(client: AsyncClient, registered_user, db_session, mock_redis):
    """Second alert on the same day returns state=rate_limited."""
    await client.post("/v1/alerts/trigger", json={"gps_status": "unavailable"},
                      headers=_auth(registered_user["tokens"]))
    resp2 = await client.post("/v1/alerts/trigger", json={"gps_status": "unavailable"},
                               headers=_auth(registered_user["tokens"]))
    assert resp2.status_code == 200
    assert resp2.json()["state"] == "rate_limited"
    assert "rate_limited" in resp2.json()["message"].lower() or "alert" in resp2.json()["message"].lower()


# ─── Alert status + lifecycle ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_alert_status(client: AsyncClient, registered_user, db_session, mock_redis, alert_event_id):
    resp = await client.get(f"/v1/alerts/{alert_event_id}",
                            headers=_auth(registered_user["tokens"]))
    assert resp.status_code == 200
    data = resp.json()
    assert data["state"] == "active"
    assert data["responder_count"] == 0


@pytest.mark.asyncio
async def test_mark_safe(client: AsyncClient, registered_user, db_session, mock_redis, alert_event_id):
    resp = await client.post(f"/v1/alerts/{alert_event_id}/safe",
                             headers=_auth(registered_user["tokens"]))
    assert resp.status_code == 200
    assert resp.json()["state"] == "user_safe"

    # Verify in DB
    result = await db_session.execute(select(AlertEvent))
    event = result.scalars().first()
    assert event.state == AlertState.user_safe
    assert event.closed_by == "user"
    assert event.closed_at is not None


@pytest.mark.asyncio
async def test_mark_safe_wrong_user(client: AsyncClient, registered_user, second_user, db_session, mock_redis, alert_event_id):
    """Another user cannot mark someone else's alert as safe."""
    resp = await client.post(f"/v1/alerts/{alert_event_id}/safe",
                             headers=_auth(second_user["tokens"]))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_lazy_autoclose(client: AsyncClient, registered_user, db_session, mock_redis, alert_event_id):
    """GET status on a >24h-old active alert should auto-close it."""
    # Force created_at to 25 hours ago
    result = await db_session.execute(select(AlertEvent))
    event = result.scalars().first()
    event.created_at = datetime.now(tz=timezone.utc) - timedelta(hours=25)
    await db_session.commit()

    resp = await client.get(f"/v1/alerts/{alert_event_id}",
                            headers=_auth(registered_user["tokens"]))
    assert resp.status_code == 200
    assert resp.json()["state"] == "closed"


# ─── Respond tests ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_respond_to_alert(client: AsyncClient, registered_user, second_user, db_session, mock_redis, alert_event_id):
    resp = await client.post(f"/v1/alerts/{alert_event_id}/respond",
                             json={"response_type": "responding", "distance_m": 450,
                                   "lat": 23.7110, "lng": 90.4080},
                             headers=_auth(second_user["tokens"]))
    assert resp.status_code == 200
    assert resp.json()["response_type"] == "responding"

    result = await db_session.execute(select(AlertResponse))
    responses = result.scalars().all()
    assert len(responses) == 1
    r = responses[0]
    assert r.response_type == ResponseType.responding
    # Responder's real position + identity are persisted (for the live map and the
    # "victim is safe" push back to responders).
    assert r.responder_lat == 23.7110
    assert r.responder_lng == 90.4080
    assert r.responder_user_id is not None


@pytest.mark.asyncio
async def test_respond_cannot_help(client: AsyncClient, registered_user, second_user, db_session, mock_redis, alert_event_id):
    resp = await client.post(f"/v1/alerts/{alert_event_id}/respond",
                             json={"response_type": "cannot_help"},
                             headers=_auth(second_user["tokens"]))
    assert resp.status_code == 200


# ─── Responder listing tests (owner-only, with real responder coordinates) ───

@pytest.mark.asyncio
async def test_list_responders_owner(client: AsyncClient, registered_user, second_user, db_session, mock_redis, alert_event_id):
    """Owner can list responders; response carries zone radius, distance, and the
    responder's real coordinates (shared between the two parties of one alert)."""
    # Second user responds with a known distance + real position
    await client.post(f"/v1/alerts/{alert_event_id}/respond",
                      json={"response_type": "responding", "distance_m": 200,
                            "lat": 23.7120, "lng": 90.4090},
                      headers=_auth(second_user["tokens"]))

    resp = await client.get(f"/v1/alerts/{alert_event_id}/responders",
                            headers=_auth(registered_user["tokens"]))
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert str(data["event_id"]) == alert_event_id
    assert data["zone_radius_m"] is not None  # zone exists (alert was triggered with GPS)
    assert data["responder_count"] == 1
    assert len(data["responders"]) == 1
    item = data["responders"][0]
    assert item["distance_m"] == 200
    assert item["response_type"] == "responding"
    # Responder's real position is now returned so the victim can see who is coming.
    assert item["lat"] == 23.7120
    assert item["lng"] == 90.4090


@pytest.mark.asyncio
async def test_list_responders_non_owner_forbidden(client: AsyncClient, registered_user, second_user, db_session, mock_redis, alert_event_id):
    """A non-owner cannot list another user's responders."""
    resp = await client.get(f"/v1/alerts/{alert_event_id}/responders",
                            headers=_auth(second_user["tokens"]))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_responders_no_zone(client: AsyncClient, registered_user, db_session, mock_redis):
    """Alert triggered without GPS has no zone — endpoint still 200 with null radius and empty list."""
    trigger = await client.post("/v1/alerts/trigger", json={"gps_status": "unavailable"},
                                headers=_auth(registered_user["tokens"]))
    assert trigger.status_code == 200, trigger.text
    event_id = trigger.json()["event_id"]

    resp = await client.get(f"/v1/alerts/{event_id}/responders",
                            headers=_auth(registered_user["tokens"]))
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["zone_radius_m"] is None
    assert data["responder_count"] == 0
    assert data["responders"] == []


# ─── Live-location tracking tests ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_alert_location_owner(client: AsyncClient, registered_user, db_session, mock_redis, alert_event_id):
    """Owner updates live location; event AND its fan-out zone re-centre."""
    new_lat, new_lng = 23.7200, 90.4100
    resp = await client.post(f"/v1/alerts/{alert_event_id}/location",
                             json={"lat": new_lat, "lng": new_lng},
                             headers=_auth(registered_user["tokens"]))
    assert resp.status_code == 200, resp.text
    assert resp.json()["lat"] == new_lat

    db_session.expire_all()
    event = (await db_session.execute(
        select(AlertEvent).where(AlertEvent.event_id == uuid.UUID(alert_event_id))
    )).scalars().first()
    assert event.lat == new_lat and event.lng == new_lng
    assert event.location_updated_at is not None

    zone = (await db_session.execute(
        select(Zone).where(Zone.id == event.alert_zone_id)
    )).scalars().first()
    assert zone.center_lat == new_lat and zone.center_lng == new_lng


@pytest.mark.asyncio
async def test_update_alert_location_non_owner_forbidden(client: AsyncClient, registered_user, second_user, db_session, mock_redis, alert_event_id):
    resp = await client.post(f"/v1/alerts/{alert_event_id}/location",
                             json={"lat": 23.72, "lng": 90.41},
                             headers=_auth(second_user["tokens"]))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_alert_location_rejected_after_safe(client: AsyncClient, registered_user, db_session, mock_redis, alert_event_id):
    """Once the alert is no longer active, live-location updates are rejected."""
    safe = await client.post(f"/v1/alerts/{alert_event_id}/safe",
                             headers=_auth(registered_user["tokens"]))
    assert safe.status_code == 200
    resp = await client.post(f"/v1/alerts/{alert_event_id}/location",
                             json={"lat": 23.72, "lng": 90.41},
                             headers=_auth(registered_user["tokens"]))
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_mark_safe_notifies_responders(client: AsyncClient, registered_user, db_session, mock_redis, alert_event_id, monkeypatch):
    """Marking safe schedules the 'victim is safe' push back to responders."""
    called = {}

    async def _spy(event_id):
        called["event_id"] = event_id

    monkeypatch.setattr("app.services.alert_svc.notify_responders_safe", _spy)
    resp = await client.post(f"/v1/alerts/{alert_event_id}/safe",
                             headers=_auth(registered_user["tokens"]))
    assert resp.status_code == 200
    assert str(called.get("event_id")) == alert_event_id


# ─── Evidence upload tests ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_evidence_upload(client: AsyncClient, registered_user, db_session, mock_redis, alert_event_id):
    resp = await client.post(f"/v1/alerts/{alert_event_id}/evidence", json={
        "encrypted_blob_ref": "s3://anchor-evidence/enc-file-001.enc",
        "sha256_hash": "a" * 64,
        "capture_timestamp": "2026-06-01T12:00:00Z",
        "media_type": "photo",
    }, headers=_auth(registered_user["tokens"]))
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data
    assert data["sha256_hash"] == "a" * 64

    result = await db_session.execute(select(AlertEvidence))
    evidence = result.scalars().all()
    assert len(evidence) == 1


@pytest.mark.asyncio
async def test_evidence_upload_wrong_user(client: AsyncClient, registered_user, second_user, db_session, mock_redis, alert_event_id):
    resp = await client.post(f"/v1/alerts/{alert_event_id}/evidence", json={
        "encrypted_blob_ref": "s3://bucket/file.enc",
        "sha256_hash": "b" * 64,
        "capture_timestamp": "2026-06-01T12:00:00Z",
        "media_type": "video",
    }, headers=_auth(second_user["tokens"]))
    assert resp.status_code == 403


# ─── Panic (unauthenticated) tests ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_panic_unauthenticated(client: AsyncClient, db_session, mock_redis):
    resp = await client.post("/v1/alerts/panic", json={
        "device_fingerprint": "test-device-fp-001",
        "lat": 23.7104, "lng": 90.4074,
        "gps_status": "ok",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "claim_token" in data
    assert len(data["claim_token"]) == 12
    assert data["state"] == "active"

    result = await db_session.execute(select(AlertEvent))
    events = result.scalars().all()
    assert len(events) == 1
    assert events[0].encrypted_actor_link is None  # no user identity for unauth


@pytest.mark.asyncio
async def test_panic_rate_limit(client: AsyncClient, db_session, mock_redis):
    """Second panic from same device fingerprint returns 429."""
    for _ in range(1):
        await client.post("/v1/alerts/panic", json={
            "device_fingerprint": "rate-limit-device-002",
            "gps_status": "unavailable",
        })
    resp2 = await client.post("/v1/alerts/panic", json={
        "device_fingerprint": "rate-limit-device-002",
        "gps_status": "unavailable",
    })
    assert resp2.status_code == 429


@pytest.mark.asyncio
async def test_panic_claim_token(client: AsyncClient, registered_user, db_session, mock_redis):
    """Authenticated user can claim an unauthenticated panic alert."""
    panic_resp = await client.post("/v1/alerts/panic", json={
        "device_fingerprint": "claim-test-device-003",
        "gps_status": "unavailable",
    })
    assert panic_resp.status_code == 200
    claim_token = panic_resp.json()["claim_token"]
    event_id = panic_resp.json()["event_id"]

    claim_resp = await client.post("/v1/alerts/panic/claim",
                                   json={"claim_token": claim_token},
                                   headers=_auth(registered_user["tokens"]))
    assert claim_resp.status_code == 200
    assert str(claim_resp.json()["event_id"]) == event_id

    # Claim token should be consumed — second use fails
    claim_resp2 = await client.post("/v1/alerts/panic/claim",
                                    json={"claim_token": claim_token},
                                    headers=_auth(registered_user["tokens"]))
    assert claim_resp2.status_code == 404


@pytest.mark.asyncio
async def test_panic_invalid_claim_token(client: AsyncClient, registered_user, db_session, mock_redis):
    resp = await client.post("/v1/alerts/panic/claim",
                             json={"claim_token": "AAAAAAAAAAAAA"[:12]},
                             headers=_auth(registered_user["tokens"]))
    assert resp.status_code == 404


# ─── Ban tests ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ban_blocks_trigger(client: AsyncClient, registered_user, db_session, mock_redis):
    """A banned device fingerprint cannot trigger an alert."""
    from app.services.alert_svc import compute_anonymous_hash
    from app.services.token import decode_token

    # Decode the user_id from the token
    tokens = registered_user["tokens"]
    payload = decode_token(tokens["access_token"])
    user_id = payload["sub"]

    # Compute the device fp hash that the server will compute from the test request
    # In tests, the device fp is derived from the UA + Accept-Language + IP
    # We insert a ban matching a known device_fingerprint_hash (we'll use a direct DB ban)
    import hashlib
    # The test client sends a default user-agent; compute what fingerprint() returns
    # We ban by user hash instead of fp hash so the check triggers regardless of request headers
    user_hash = compute_anonymous_hash(uuid.UUID(user_id))
    ban = AlertBan(
        device_fingerprint_hash=user_hash,  # used as both user and device hash identifier
        ban_reason="test ban",
        banned_at=datetime.now(tz=timezone.utc),
        expires_at=datetime.now(tz=timezone.utc) + timedelta(days=30),
    )
    db_session.add(ban)
    await db_session.commit()

    resp = await client.post("/v1/alerts/trigger", json={"gps_status": "unavailable"},
                             headers=_auth(tokens))
    assert resp.status_code == 403


# ─── Nearby alerts tests ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_nearby_alerts(client: AsyncClient, registered_user, second_user, db_session, mock_redis):
    # Second user shares location
    await client.post("/v1/users/me/location", json={
        "lat": 23.7110, "lng": 90.4074, "geofence_consent": True,
    }, headers=_auth(second_user["tokens"]))

    # First user triggers alert
    trigger = await client.post("/v1/alerts/trigger", json={
        "lat": 23.7104, "lng": 90.4074, "gps_status": "ok",
    }, headers=_auth(registered_user["tokens"]))
    assert trigger.status_code == 200

    # Second user queries nearby
    resp = await client.get("/v1/alerts/nearby?lat=23.7110&lng=90.4074",
                            headers=_auth(second_user["tokens"]))
    assert resp.status_code == 200
    items = resp.json()
    assert isinstance(items, list)
    assert len(items) >= 1
    assert items[0]["state"] == "active"


# ─── FCM token + location endpoint tests ─────────────────────────────────────

@pytest.mark.asyncio
async def test_register_fcm_token(client: AsyncClient, registered_user, db_session, mock_redis):
    resp = await client.post("/v1/users/me/fcm-token", json={
        "fcm_token": "dGVzdF90b2tlbl8x",
        "device_id": "device-abc-123",
        "platform": "android",
    }, headers=_auth(registered_user["tokens"]))
    assert resp.status_code == 200

    result = await db_session.execute(select(UserFCMToken))
    tokens = result.scalars().all()
    assert len(tokens) == 1
    assert tokens[0].fcm_token == "dGVzdF90b2tlbl8x"


@pytest.mark.asyncio
async def test_update_location(client: AsyncClient, registered_user, db_session, mock_redis):
    resp = await client.post("/v1/users/me/location", json={
        "lat": 23.7104, "lng": 90.4074, "geofence_consent": True,
    }, headers=_auth(registered_user["tokens"]))
    assert resp.status_code == 200

    # Second update should upsert, not create a second row
    await client.post("/v1/users/me/location", json={
        "lat": 23.7200, "lng": 90.4100, "geofence_consent": False,
    }, headers=_auth(registered_user["tokens"]))

    result = await db_session.execute(select(UserLocationSnapshot))
    snapshots = result.scalars().all()
    assert len(snapshots) == 1
    assert snapshots[0].lat == pytest.approx(23.7200, abs=0.0001)
    assert snapshots[0].geofence_consent is False


@pytest.mark.asyncio
async def test_register_fcm_token_replaces_same_device(client: AsyncClient, registered_user, db_session, mock_redis):
    """Re-registering the same device disables the previous token, keeps one active."""
    h = _auth(registered_user["tokens"])
    await client.post("/v1/users/me/fcm-token", json={
        "fcm_token": "tok-old", "device_id": "dev-1", "platform": "web"}, headers=h)
    await client.post("/v1/users/me/fcm-token", json={
        "fcm_token": "tok-new", "device_id": "dev-1", "platform": "web"}, headers=h)
    rows = (await db_session.execute(select(UserFCMToken))).scalars().all()
    active = [t for t in rows if t.disabled_at is None]
    assert len(rows) == 2
    assert len(active) == 1
    assert active[0].fcm_token == "tok-new"


@pytest.mark.asyncio
async def test_deregister_fcm_token(client: AsyncClient, registered_user, db_session, mock_redis):
    """DELETE disables the device's active token (used on logout)."""
    h = _auth(registered_user["tokens"])
    await client.post("/v1/users/me/fcm-token", json={
        "fcm_token": "tok-x", "device_id": "dev-9", "platform": "web"}, headers=h)
    resp = await client.delete("/v1/users/me/fcm-token", params={"device_id": "dev-9"}, headers=h)
    assert resp.status_code == 200, resp.text
    assert resp.json()["disabled"] == 1
    rows = (await db_session.execute(select(UserFCMToken))).scalars().all()
    assert len(rows) == 1 and rows[0].disabled_at is not None


@pytest.mark.asyncio
async def test_fcm_test_push_no_devices(client: AsyncClient, registered_user, db_session, mock_redis):
    """Test-push on an account with no registered device reports tokens=0."""
    resp = await client.post("/v1/users/me/fcm-token/test", headers=_auth(registered_user["tokens"]))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["tokens"] == 0
    assert body["delivered"] == 0


@pytest.mark.asyncio
async def test_fcm_test_push_reports_and_disables_dead(
    client: AsyncClient, registered_user, db_session, mock_redis, monkeypatch
):
    """Test-push returns per-device results and disables permanently-invalid tokens."""
    h = _auth(registered_user["tokens"])
    await client.post("/v1/users/me/fcm-token", json={
        "fcm_token": "tok-good", "device_id": "dev-good", "platform": "web"}, headers=h)
    await client.post("/v1/users/me/fcm-token", json={
        "fcm_token": "tok-bad", "device_id": "dev-bad", "platform": "android"}, headers=h)

    async def _fake_send_batch(tokens, title, body, data=None):
        return {
            "tok-good": {"message_id": "m1", "ok": True, "error": None},
            "tok-bad": {"message_id": None, "ok": False, "error": "sender_id_mismatch"},
        }
    monkeypatch.setattr("app.services.fcm.send_batch", _fake_send_batch)

    resp = await client.post("/v1/users/me/fcm-token/test", headers=h)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["tokens"] == 2
    assert body["delivered"] == 1
    assert len(body["results"]) == 2

    # The sender_id_mismatch token must be auto-disabled (PERMANENT_ERRORS self-heal).
    rows = (await db_session.execute(select(UserFCMToken))).scalars().all()
    by_token = {r.fcm_token: r for r in rows}
    assert by_token["tok-bad"].disabled_at is not None
    assert by_token["tok-good"].disabled_at is None


@pytest.mark.asyncio
async def test_fcm_test_push_targets_only_requested_device(
    client: AsyncClient, registered_user, db_session, mock_redis, monkeypatch
):
    """With ?device_id=, the test must send to ONLY that device's token — not every
    device on the account. This is the cross-device misfire fix: tapping 'test' on the
    phone must not buzz the PC."""
    h = _auth(registered_user["tokens"])
    await client.post("/v1/users/me/fcm-token", json={
        "fcm_token": "tok-pc", "device_id": "web-pc", "platform": "web"}, headers=h)
    await client.post("/v1/users/me/fcm-token", json={
        "fcm_token": "tok-phone", "device_id": "web-phone", "platform": "web"}, headers=h)

    sent_tokens = []

    async def _fake_send_batch(tokens, title, body, data=None):
        sent_tokens.extend(tokens)
        return {t: {"message_id": "m", "ok": True, "error": None} for t in tokens}
    monkeypatch.setattr("app.services.fcm.send_batch", _fake_send_batch)

    resp = await client.post(
        "/v1/users/me/fcm-token/test?device_id=web-phone", headers=h)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["tokens"] == 1
    assert body["delivered"] == 1
    assert sent_tokens == ["tok-phone"]
    assert [r["device_id"] for r in body["results"]] == ["web-phone"]


@pytest.mark.asyncio
async def test_fcm_test_push_unknown_device_reports_zero(
    client: AsyncClient, registered_user, db_session, mock_redis
):
    """A device_id with no active token reports tokens=0 with an actionable message —
    instead of silently delivering to a different device."""
    h = _auth(registered_user["tokens"])
    await client.post("/v1/users/me/fcm-token", json={
        "fcm_token": "tok-pc", "device_id": "web-pc", "platform": "web"}, headers=h)

    resp = await client.post(
        "/v1/users/me/fcm-token/test?device_id=web-ghost", headers=h)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["tokens"] == 0
    assert body["delivered"] == 0
    assert "isn't registered" in body["message"]


def test_fcm_classify_and_permanent_errors():
    """Send-error classification maps the permanently-invalid token cases."""
    from app.services.fcm import _classify, PERMANENT_ERRORS

    class UnregisteredError(Exception): pass
    class SenderIdMismatchError(Exception): pass

    assert _classify(UnregisteredError("x")) == "unregistered"
    assert _classify(SenderIdMismatchError("x")) == "sender_id_mismatch"
    assert _classify(Exception("Requested entity was not found")) == "unregistered"
    assert _classify(ValueError("transient boom")) == "error"
    assert {"unregistered", "sender_id_mismatch"} <= PERMANENT_ERRORS


@pytest.mark.asyncio
async def test_fcm_send_unconfigured_returns_structured_result(monkeypatch):
    """When FCM is unconfigured, sends degrade to a structured result."""
    from app.services import fcm
    monkeypatch.setattr(fcm, "_get_app", lambda: None)  # force the unconfigured path
    one = await fcm.send_to_token("tok", "title", "body")
    assert one == {"message_id": None, "ok": False, "error": "unconfigured"}
    batch = await fcm.send_batch(["a", "b"], "title", "body")
    assert batch["a"] == {"message_id": None, "ok": False, "error": "unconfigured"}
    assert batch["b"]["ok"] is False


async def _make_admin_and_relogin(client, db_session, email: str, password: str) -> dict:
    from sqlalchemy import update
    from app.models.user import User
    await db_session.execute(update(User).where(User.email == email).values(role="admin"))
    await db_session.commit()
    resp = await client.post("/auth/login", json={"identifier": email, "password": password})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.mark.asyncio
async def test_push_health_requires_admin(client: AsyncClient, registered_user, db_session, mock_redis):
    resp = await client.get("/v1/admin/alerts/push-health", headers=_auth(registered_user["tokens"]))
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_push_health_admin_shape(client: AsyncClient, registered_user, db_session, mock_redis):
    headers = await _make_admin_and_relogin(
        client, db_session, registered_user["email"], registered_user["password"])
    resp = await client.get("/v1/admin/alerts/push-health", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    for key in ("fcm_configured", "active_tokens", "disabled_tokens",
                "consenting_recent_devices", "staleness_minutes", "recent_push",
                "credential_project_id", "expected_client_project", "project_match"):
        assert key in body
    assert set(body["recent_push"].keys()) == {"sent", "failed"}
    # Unconfigured in tests → no credential project, so it cannot match the client.
    assert body["credential_project_id"] is None
    assert body["project_match"] is False


@pytest.mark.asyncio
async def test_push_health_project_match(client: AsyncClient, registered_user, db_session, mock_redis, monkeypatch):
    """The core regression guard: project_match is true ONLY when the backend's
    credential project equals the client's project, and false on a mismatch
    (the SenderIdMismatch bug that broke every push)."""
    from app.services import fcm as fcm_svc
    headers = await _make_admin_and_relogin(
        client, db_session, registered_user["email"], registered_user["password"])

    # Simulate a configured credential whose project matches the client.
    monkeypatch.setattr(fcm_svc, "_get_app", lambda: object())
    monkeypatch.setattr(fcm_svc, "get_credential_project_id", lambda: "project-anchor-e008b")
    resp = await client.get("/v1/admin/alerts/push-health", headers=headers)
    body = resp.json()
    assert body["fcm_configured"] is True
    assert body["credential_project_id"] == "project-anchor-e008b"
    assert body["project_match"] is True

    # Simulate the original bug: credential for the OLD project.
    monkeypatch.setattr(fcm_svc, "get_credential_project_id", lambda: "project-anchor-76170")
    resp = await client.get("/v1/admin/alerts/push-health", headers=headers)
    body = resp.json()
    assert body["credential_project_id"] == "project-anchor-76170"
    assert body["project_match"] is False


# ─── Unit tests for alert_svc helpers ────────────────────────────────────────

def test_haversine():
    from app.services.geofence import haversine
    # Two points ~111m apart (roughly 0.001 degree lat)
    d = haversine(23.7100, 90.4074, 23.7109, 90.4074)
    assert 90 < d < 120  # ~100m


def test_anonymous_hash_deterministic():
    from app.services.alert_svc import compute_anonymous_hash
    uid = uuid.uuid4()
    h1 = compute_anonymous_hash(uid)
    h2 = compute_anonymous_hash(uid)
    assert h1 == h2
    assert len(h1) == 64


def test_encrypt_decrypt_roundtrip():
    from app.services.alert_svc import encrypt_payload, decrypt_payload
    data = b"hello world test payload"
    ct = encrypt_payload(data)
    assert ct != data
    pt = decrypt_payload(ct)
    assert pt == data


def test_generate_claim_token():
    from app.services.alert_svc import generate_claim_token
    tok = generate_claim_token()
    assert len(tok) == 12
    import string
    valid_chars = set(string.ascii_uppercase + "234567")
    assert all(c in valid_chars for c in tok)


# ─── GET /v1/alerts/me ────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_me_requires_auth(client, db_session, mock_redis):
    r = await client.get("/v1/alerts/me")
    assert r.status_code in (401, 403)


@pytest.mark.anyio
async def test_me_empty_when_no_alerts(client, db_session, mock_redis, registered_user):
    token = registered_user["tokens"]["access_token"]
    r = await client.get("/v1/alerts/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.anyio
async def test_me_returns_own_alert(client, db_session, mock_redis, registered_user):
    token = registered_user["tokens"]["access_token"]
    trigger = await client.post(
        "/v1/alerts/trigger",
        json={"lat": 23.8759, "lng": 90.3795, "gps_status": "ok"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert trigger.status_code == 200

    r = await client.get("/v1/alerts/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["state"] == "active"
    assert data[0]["event_id"] is not None
    assert data[0]["lat"] == pytest.approx(23.8759)


@pytest.mark.anyio
async def test_me_does_not_return_other_users_alerts(client, db_session, mock_redis, registered_user, second_user):
    user1_token = registered_user["tokens"]["access_token"]
    user2_token = second_user["tokens"]["access_token"]

    # User1 triggers an alert
    await client.post(
        "/v1/alerts/trigger",
        json={"lat": 23.8759, "lng": 90.3795, "gps_status": "ok"},
        headers={"Authorization": f"Bearer {user1_token}"},
    )

    # User2 should see empty list
    r = await client.get("/v1/alerts/me", headers={"Authorization": f"Bearer {user2_token}"})
    assert r.status_code == 200
    assert r.json() == []
