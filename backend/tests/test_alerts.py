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
    AlertEvidence, UserFCMToken, UserLocationSnapshot,
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
                             json={"response_type": "responding", "distance_m": 450},
                             headers=_auth(second_user["tokens"]))
    assert resp.status_code == 200
    assert resp.json()["response_type"] == "responding"

    result = await db_session.execute(select(AlertResponse))
    responses = result.scalars().all()
    assert len(responses) == 1
    assert responses[0].response_type == ResponseType.responding


@pytest.mark.asyncio
async def test_respond_cannot_help(client: AsyncClient, registered_user, second_user, db_session, mock_redis, alert_event_id):
    resp = await client.post(f"/v1/alerts/{alert_event_id}/respond",
                             json={"response_type": "cannot_help"},
                             headers=_auth(second_user["tokens"]))
    assert resp.status_code == 200


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
