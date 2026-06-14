"""
Tests for /v1/admin/users — super_admin user management endpoints.
Uses SQLite in-memory + fakeredis — no Docker required.
"""
import uuid
import pytest
from sqlalchemy import update

from app.models.user import User, Role


def _auth(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def _make_role(client, db_session, role: str) -> dict:
    email = f"{role}_{uuid.uuid4().hex[:6]}@example.com"
    password = "Secure!Pass99"
    reg = await client.post("/auth/register", json={
        "full_name": "Test User",
        "email": email,
        "password": password,
        "role": "user",
        "terms": True,
        "data_consent": True,
    })
    assert reg.status_code == 201
    otp = reg.json()["dev_otp"]
    await client.post("/auth/verify-email", json={"token": f"{email}:{otp}"})

    await db_session.execute(
        update(User).where(User.email == email).values(role=Role(role))
    )
    await db_session.commit()

    login = await client.post("/auth/login", json={"identifier": email, "password": password})
    assert login.status_code == 200
    return {"email": email, "password": password, "tokens": login.json()}


@pytest.mark.asyncio
async def test_super_admin_can_create_admin(client, db_session, mock_redis):
    sa = await _make_role(client, db_session, "super_admin")
    r = await client.post("/v1/admin/users", json={
        "full_name": "New Admin",
        "email": "newadmin@example.com",
        "password": "AdminPass!88",
        "role": "admin",
    }, headers=_auth(sa["tokens"]))
    assert r.status_code == 201
    body = r.json()
    assert body["role"] == "admin"
    assert body["email"] == "newadmin@example.com"
    assert body["status"] == "active"
    assert body["email_verified"] is True


@pytest.mark.asyncio
async def test_super_admin_can_create_moderator(client, db_session, mock_redis):
    sa = await _make_role(client, db_session, "super_admin")
    r = await client.post("/v1/admin/users", json={
        "full_name": "New Moderator",
        "email": "newmod@example.com",
        "password": "ModPass!88",
        "role": "moderator",
    }, headers=_auth(sa["tokens"]))
    assert r.status_code == 201
    assert r.json()["role"] == "moderator"


@pytest.mark.asyncio
async def test_regular_admin_cannot_create_users(client, db_session, mock_redis):
    admin = await _make_role(client, db_session, "admin")
    r = await client.post("/v1/admin/users", json={
        "full_name": "Rogue",
        "email": "rogue@example.com",
        "password": "RoguePass!88",
        "role": "admin",
    }, headers=_auth(admin["tokens"]))
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_cannot_create_super_admin_via_endpoint(client, db_session, mock_redis):
    sa = await _make_role(client, db_session, "super_admin")
    r = await client.post("/v1/admin/users", json={
        "full_name": "Elevated",
        "email": "elevated@example.com",
        "password": "ElevPass!88",
        "role": "super_admin",
    }, headers=_auth(sa["tokens"]))
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_duplicate_email_returns_409(client, db_session, mock_redis):
    sa = await _make_role(client, db_session, "super_admin")
    payload = {"full_name": "Dup", "email": "dup@example.com", "password": "DupPass!88", "role": "admin"}
    await client.post("/v1/admin/users", json=payload, headers=_auth(sa["tokens"]))
    r = await client.post("/v1/admin/users", json=payload, headers=_auth(sa["tokens"]))
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_new_admin_can_login(client, db_session, mock_redis):
    sa = await _make_role(client, db_session, "super_admin")
    await client.post("/v1/admin/users", json={
        "full_name": "Login Test",
        "email": "logintest@example.com",
        "password": "LoginPass!88",
        "role": "admin",
    }, headers=_auth(sa["tokens"]))
    login = await client.post("/auth/login", json={"identifier": "logintest@example.com", "password": "LoginPass!88"})
    assert login.status_code == 200
    assert login.json()["access_token"]


@pytest.mark.asyncio
async def test_list_users_requires_auth(client, db_session, mock_redis):
    r = await client.get("/v1/admin/users")
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_super_admin_can_list_users(client, db_session, mock_redis, registered_user):
    sa = await _make_role(client, db_session, "super_admin")
    r = await client.get("/v1/admin/users", headers=_auth(sa["tokens"]))
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert "total" in body


@pytest.mark.asyncio
async def test_admin_can_list_users(client, db_session, mock_redis):
    admin = await _make_role(client, db_session, "admin")
    r = await client.get("/v1/admin/users", headers=_auth(admin["tokens"]))
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_super_admin_can_change_role(client, db_session, mock_redis):
    sa = await _make_role(client, db_session, "super_admin")
    # Create a target user
    created = await client.post("/v1/admin/users", json={
        "full_name": "To Demote",
        "email": "demote@example.com",
        "password": "DemotePass!88",
        "role": "admin",
    }, headers=_auth(sa["tokens"]))
    user_id = created.json()["id"]

    r = await client.patch(f"/v1/admin/users/{user_id}/role", json={"role": "moderator"}, headers=_auth(sa["tokens"]))
    assert r.status_code == 200
    assert r.json()["role"] == "moderator"


@pytest.mark.asyncio
async def test_cannot_promote_to_super_admin_via_patch(client, db_session, mock_redis):
    sa = await _make_role(client, db_session, "super_admin")
    created = await client.post("/v1/admin/users", json={
        "full_name": "Escalate",
        "email": "escalate@example.com",
        "password": "EscalPass!88",
        "role": "admin",
    }, headers=_auth(sa["tokens"]))
    user_id = created.json()["id"]

    r = await client.patch(f"/v1/admin/users/{user_id}/role", json={"role": "super_admin"}, headers=_auth(sa["tokens"]))
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_super_admin_can_suspend_user(client, db_session, mock_redis):
    sa = await _make_role(client, db_session, "super_admin")
    created = await client.post("/v1/admin/users", json={
        "full_name": "To Suspend",
        "email": "suspend@example.com",
        "password": "SuspendPass!88",
        "role": "admin",
    }, headers=_auth(sa["tokens"]))
    user_id = created.json()["id"]

    r = await client.patch(f"/v1/admin/users/{user_id}/status", json={"status": "suspended"}, headers=_auth(sa["tokens"]))
    assert r.status_code == 200
    assert r.json()["status"] == "suspended"


@pytest.mark.asyncio
async def test_suspended_admin_cannot_login(client, db_session, mock_redis):
    sa = await _make_role(client, db_session, "super_admin")
    await client.post("/v1/admin/users", json={
        "full_name": "Suspended",
        "email": "susplogin@example.com",
        "password": "SuspLogin!88",
        "role": "admin",
    }, headers=_auth(sa["tokens"]))

    users_resp = await client.get("/v1/admin/users?role=admin", headers=_auth(sa["tokens"]))
    user_id = next(u["id"] for u in users_resp.json()["items"] if u["email"] == "susplogin@example.com")

    await client.patch(f"/v1/admin/users/{user_id}/status", json={"status": "suspended"}, headers=_auth(sa["tokens"]))
    login = await client.post("/auth/login", json={"identifier": "susplogin@example.com", "password": "SuspLogin!88"})
    assert login.status_code == 403


@pytest.mark.asyncio
async def test_cannot_change_own_status(client, db_session, mock_redis):
    sa = await _make_role(client, db_session, "super_admin")
    me = await client.get("/auth/me", headers=_auth(sa["tokens"]))
    my_id = me.json()["id"]
    r = await client.patch(f"/v1/admin/users/{my_id}/status", json={"status": "suspended"}, headers=_auth(sa["tokens"]))
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_list_filter_by_role(client, db_session, mock_redis):
    sa = await _make_role(client, db_session, "super_admin")
    await client.post("/v1/admin/users", json={
        "full_name": "Filter Test",
        "email": "filtertest@example.com",
        "password": "FilterPass!88",
        "role": "moderator",
    }, headers=_auth(sa["tokens"]))

    r = await client.get("/v1/admin/users?role=moderator", headers=_auth(sa["tokens"]))
    assert r.status_code == 200
    for u in r.json()["items"]:
        assert u["role"] == "moderator"
