"""
Tests for the national-mode Officer Scorecard feature.

SQLite in-memory + fakeredis. Startup seeding doesn't run on the SQLite path, so
stations are inserted directly via db_session.
"""
import uuid
import pytest
from sqlalchemy import update

from app.models.user import User
from app.models.officer_scorecard import Officer, PoliceStation


def _auth(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def _register(client, prefix: str = "user") -> dict:
    email = f"{prefix}_{uuid.uuid4().hex[:8]}@example.com"
    password = "SecurePass!99"
    reg = await client.post("/auth/register", json={
        "full_name": "Score Tester", "email": email, "password": password,
        "role": "user", "terms": True, "data_consent": True,
    })
    assert reg.status_code == 201, reg.json()
    otp = reg.json()["dev_otp"]
    await client.post("/auth/verify-email", json={"token": f"{email}:{otp}"})
    login = await client.post("/auth/login", json={"identifier": email, "password": password})
    return {"email": email, "password": password, "tokens": login.json()}


async def _make_super_admin(client, db_session, email: str, password: str) -> dict:
    await db_session.execute(update(User).where(User.email == email).values(role="super_admin"))
    await db_session.commit()
    resp = await client.post("/auth/login", json={"identifier": email, "password": password})
    assert resp.status_code == 200, resp.json()
    return resp.json()


async def _seed_station(db_session, name="Mirpur Model Thana", with_officer=False):
    """Returns plain (station_id, officer_id) strings — never the ORM objects, so
    tests don't touch attributes that expire after intervening commits on the
    shared session (which would trigger a lazy load outside the async context)."""
    station = PoliceStation(name=name, district="Dhaka", division="Dhaka")
    db_session.add(station)
    await db_session.commit()
    await db_session.refresh(station)
    station_id = str(station.id)
    officer_id = None
    if with_officer:
        officer = Officer(station_id=station.id, name="SI Karim", rank="Sub-Inspector", badge_no="4471")
        db_session.add(officer)
        await db_session.commit()
        await db_session.refresh(officer)
        officer_id = str(officer.id)
    return station_id, officer_id


_RATING = {"responsiveness": 3, "conduct": 4, "integrity": 2, "overall": 3, "comment": "Slow but polite"}


@pytest.mark.asyncio
async def test_list_stations_public(client, db_session):
    await _seed_station(db_session)
    r = await client.get("/v1/officer-scorecards/stations")
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["name"] == "Mirpur Model Thana"
    assert r.json()[0]["total_count"] == 0  # no approved ratings yet


@pytest.mark.asyncio
async def test_rating_pending_not_in_aggregate(client, db_session, registered_user):
    station_id, _ = await _seed_station(db_session)
    h = _auth(registered_user["tokens"])

    r = await client.post("/v1/officer-scorecards/ratings",
                          json={"station_id": station_id, **_RATING}, headers=h)
    assert r.status_code == 201, r.json()
    assert r.json()["status"] == "pending"

    # pending rating must NOT count in the public aggregate
    summary = await client.get(f"/v1/officer-scorecards/stations/{station_id}")
    assert summary.status_code == 200
    assert summary.json()["total_count"] == 0
    assert summary.json()["avg_overall"] is None


@pytest.mark.asyncio
async def test_duplicate_rating_conflict(client, db_session, registered_user):
    station_id, _ = await _seed_station(db_session)
    h = _auth(registered_user["tokens"])
    payload = {"station_id": station_id, **_RATING}
    assert (await client.post("/v1/officer-scorecards/ratings", json=payload, headers=h)).status_code == 201
    dup = await client.post("/v1/officer-scorecards/ratings", json=payload, headers=h)
    assert dup.status_code == 409


@pytest.mark.asyncio
async def test_moderation_approve_counts_in_aggregate(client, db_session, registered_user):
    station_id, officer_id = await _seed_station(db_session, with_officer=True)
    h = _auth(registered_user["tokens"])

    rid = (await client.post("/v1/officer-scorecards/ratings", json={
        "station_id": station_id, "officer_id": officer_id, **_RATING,
    }, headers=h)).json()["id"]

    # role gating: regular user cannot moderate or list
    assert (await client.get("/v1/admin/officer-scorecards/ratings", headers=h)).status_code in (401, 403)
    assert (await client.get("/v1/admin/officer-scorecards/ratings")).status_code in (401, 403)

    admin = await _make_super_admin(client, db_session, registered_user["email"], registered_user["password"])
    ah = _auth(admin)

    pending = await client.get("/v1/admin/officer-scorecards/ratings?status=pending", headers=ah)
    assert pending.status_code == 200
    assert any(item["id"] == rid for item in pending.json())
    assert pending.json()[0]["station_name"] == "Mirpur Model Thana"
    assert pending.json()[0]["officer_name"] == "SI Karim"

    # approve
    mod = await client.post(f"/v1/admin/officer-scorecards/ratings/{rid}/moderate",
                            json={"action": "approve"}, headers=ah)
    assert mod.status_code == 200
    assert mod.json()["status"] == "approved"

    # now counted in the public aggregate
    summary = await client.get(f"/v1/officer-scorecards/stations/{station_id}")
    assert summary.json()["total_count"] == 1
    assert summary.json()["avg_overall"] == 3.0
    assert summary.json()["officers"][0]["total_count"] == 1


@pytest.mark.asyncio
async def test_rate_unknown_station_404(client, registered_user):
    h = _auth(registered_user["tokens"])
    r = await client.post("/v1/officer-scorecards/ratings",
                          json={"station_id": str(uuid.uuid4()), **_RATING}, headers=h)
    assert r.status_code == 404
