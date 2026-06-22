import uuid
import pytest
from sqlalchemy import update

from app.models.lawyer import Lawyer
from app.models.user import User


@pytest.mark.anyio
async def test_list_lawyers_empty(client, db_session, mock_redis):
    resp = await client.get("/v1/lawyers")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.anyio
async def test_list_lawyers_returns_all(client, db_session, mock_redis):
    db_session.add_all([
        Lawyer(name="Rahim Uddin", district="Dhaka", specializations=["criminal"], verified=True),
        Lawyer(name="Karim Ali", district="Chittagong", specializations=["civil"], verified=False),
    ])
    await db_session.commit()

    resp = await client.get("/v1/lawyers")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.anyio
async def test_list_lawyers_district_filter(client, db_session, mock_redis):
    db_session.add_all([
        Lawyer(name="Dhaka Lawyer", district="Dhaka", specializations=[], verified=True),
        Lawyer(name="Sylhet Lawyer", district="Sylhet", specializations=[], verified=True),
    ])
    await db_session.commit()

    resp = await client.get("/v1/lawyers?district=Dhaka")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["district"] == "Dhaka"


@pytest.mark.anyio
async def test_list_lawyers_verified_only(client, db_session, mock_redis):
    db_session.add_all([
        Lawyer(name="Verified One", district="Dhaka", specializations=[], verified=True),
        Lawyer(name="Unverified", district="Dhaka", specializations=[], verified=False),
    ])
    await db_session.commit()

    resp = await client.get("/v1/lawyers?verified_only=true")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["verified"] is True


@pytest.mark.anyio
async def test_list_lawyers_specialization_filter(client, db_session, mock_redis):
    db_session.add_all([
        Lawyer(name="Criminal Lawyer", district="Dhaka", specializations=["criminal law", "defense"], verified=True),
        Lawyer(name="Civil Lawyer", district="Dhaka", specializations=["civil litigation"], verified=True),
    ])
    await db_session.commit()

    resp = await client.get("/v1/lawyers?specialization=criminal")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["name"] == "Criminal Lawyer"


# ---------------------------------------------------------------------------
# Lawyer application + super-admin verification
# ---------------------------------------------------------------------------

async def _register(client, mock_redis, role="user"):
    email = f"lawyer_{uuid.uuid4().hex[:8]}@example.com"
    password = "SecurePass!99"
    reg = await client.post("/auth/register", json={
        "full_name": "Test Lawyer",
        "email": email,
        "password": password,
        "role": role,
        "terms": True,
        "data_consent": True,
    })
    assert reg.status_code == 201, reg.text
    otp = reg.json()["dev_otp"]
    verify = await client.post("/auth/verify-email", json={"token": f"{email}:{otp}"})
    assert verify.status_code == 200, verify.text
    return {"email": email, "password": password, "tokens": verify.json()}


def _auth(acct):
    return {"Authorization": f"Bearer {acct['tokens']['access_token']}"}


async def _make_superadmin(client, db_session, acct):
    await db_session.execute(
        update(User).where(User.email == acct["email"]).values(role="super_admin")
    )
    await db_session.commit()
    resp = await client.post("/auth/login", json={
        "identifier": acct["email"], "password": acct["password"],
    })
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


_APPLY = {
    "bar_number": "BAR-12345",
    "district": "Dhaka",
    "specializations": ["Criminal", "Cyber"],
    "bio": "10 years experience.",
}


@pytest.mark.asyncio
async def test_apply_creates_pending_profile(client, mock_redis, db_session):
    acct = await _register(client, mock_redis)
    resp = await client.post("/v1/lawyers/apply", json=_APPLY, headers=_auth(acct))
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "pending"
    assert body["verified"] is False
    assert body["bar_number"] == "BAR-12345"

    me = await client.get("/v1/lawyers/me", headers=_auth(acct))
    assert me.status_code == 200
    assert me.json()["status"] == "pending"


@pytest.mark.asyncio
async def test_duplicate_apply_conflicts(client, mock_redis, db_session):
    acct = await _register(client, mock_redis)
    r1 = await client.post("/v1/lawyers/apply", json=_APPLY, headers=_auth(acct))
    assert r1.status_code == 201
    r2 = await client.post("/v1/lawyers/apply", json=_APPLY, headers=_auth(acct))
    assert r2.status_code == 409


@pytest.mark.asyncio
async def test_non_superadmin_cannot_verify(client, mock_redis, db_session):
    applicant = await _register(client, mock_redis)
    apply = await client.post("/v1/lawyers/apply", json=_APPLY, headers=_auth(applicant))
    lawyer_id = apply.json()["id"]

    other = await _register(client, mock_redis)
    resp = await client.post(f"/v1/admin/lawyers/{lawyer_id}/verify", headers=_auth(other))
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_superadmin_verify_upgrades_role_and_directory(client, mock_redis, db_session):
    applicant = await _register(client, mock_redis)
    apply = await client.post("/v1/lawyers/apply", json=_APPLY, headers=_auth(applicant))
    lawyer_id = apply.json()["id"]

    admin = await _register(client, mock_redis)
    admin_h = await _make_superadmin(client, db_session, admin)

    listing = await client.get("/v1/admin/lawyers?status=pending", headers=admin_h)
    assert listing.status_code == 200
    assert any(item["id"] == lawyer_id for item in listing.json()["items"])

    verify = await client.post(f"/v1/admin/lawyers/{lawyer_id}/verify", headers=admin_h)
    assert verify.status_code == 200, verify.text
    assert verify.json()["status"] == "verified"
    assert verify.json()["verified"] is True

    directory = await client.get("/v1/lawyers?verified_only=true")
    assert directory.status_code == 200
    assert any(l["id"] == lawyer_id for l in directory.json())

    relog = await client.post("/auth/login", json={
        "identifier": applicant["email"], "password": applicant["password"],
    })
    me = await client.get("/auth/me", headers={
        "Authorization": f"Bearer {relog.json()['access_token']}"
    })
    assert me.json()["role"] == "lawyer"


@pytest.mark.asyncio
async def test_reject_keeps_lawyer_out_of_directory(client, mock_redis, db_session):
    applicant = await _register(client, mock_redis)
    apply = await client.post("/v1/lawyers/apply", json=_APPLY, headers=_auth(applicant))
    lawyer_id = apply.json()["id"]

    admin = await _register(client, mock_redis)
    admin_h = await _make_superadmin(client, db_session, admin)

    reject = await client.post(
        f"/v1/admin/lawyers/{lawyer_id}/reject",
        json={"reason": "Bar number could not be verified"},
        headers=admin_h,
    )
    assert reject.status_code == 200
    assert reject.json()["status"] == "rejected"

    directory = await client.get("/v1/lawyers?verified_only=true")
    assert not any(l["id"] == lawyer_id for l in directory.json())

    me = await client.get("/v1/lawyers/me", headers=_auth(applicant))
    assert me.json()["status"] == "rejected"

    resubmit = await client.post("/v1/lawyers/apply", json=_APPLY, headers=_auth(applicant))
    assert resubmit.status_code == 201
    assert resubmit.json()["status"] == "pending"
