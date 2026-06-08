"""
Tests for super_admin role: login, JWT claims, and role-bypass access control.

Uses SQLite in-memory + fakeredis — no Docker required.
"""
import pytest
import uuid
from sqlalchemy import update

from app.models.user import User, Role


def _auth(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def _make_super_admin(client, db_session) -> dict:
    """Register a user, elevate to super_admin, re-login, return credentials."""
    email = f"superadmin_{uuid.uuid4().hex[:8]}@example.com"
    password = "SuperSecure!99"

    reg = await client.post("/auth/register", json={
        "full_name": "AiVion Platform Team",
        "email": email,
        "password": password,
        "role": "user",
        "terms": True,
        "data_consent": True,
    })
    assert reg.status_code == 201, reg.json()
    otp = reg.json()["dev_otp"]

    verify = await client.post("/auth/verify-email", json={"token": f"{email}:{otp}"})
    assert verify.status_code == 200, verify.json()

    # Elevate role in DB
    await db_session.execute(
        update(User).where(User.email == email).values(role=Role.super_admin)
    )
    await db_session.commit()

    # Re-login to get a fresh JWT with the new role
    login = await client.post("/auth/login", json={"identifier": email, "password": password})
    assert login.status_code == 200, login.json()

    return {"email": email, "password": password, "tokens": login.json()}


@pytest.mark.asyncio
async def test_super_admin_me_shows_correct_role(client, db_session, mock_redis):
    """/auth/me returns role=super_admin after elevation."""
    sa = await _make_super_admin(client, db_session)
    r = await client.get("/auth/me", headers=_auth(sa["tokens"]))
    assert r.status_code == 200
    assert r.json()["role"] == "super_admin"


@pytest.mark.asyncio
async def test_super_admin_jwt_carries_role_claim(client, db_session, mock_redis):
    """Decoded JWT payload carries role=super_admin."""
    sa = await _make_super_admin(client, db_session)
    from app.services.token import decode_token
    payload = decode_token(sa["tokens"]["access_token"])
    assert payload["role"] == "super_admin"


@pytest.mark.asyncio
async def test_super_admin_bypasses_admin_only_gate(client, db_session, mock_redis):
    """super_admin can call endpoints gated with require_role('admin', 'moderator')."""
    sa = await _make_super_admin(client, db_session)
    r = await client.get("/v1/admin/alerts", headers=_auth(sa["tokens"]))
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_super_admin_bypasses_moderator_gate(client, db_session, mock_redis):
    """super_admin can call endpoints gated with require_role('moderator')."""
    sa = await _make_super_admin(client, db_session)
    r = await client.get("/v1/feed/admin/stats", headers=_auth(sa["tokens"]))
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_regular_user_blocked_from_admin_routes(client, db_session, mock_redis, registered_user):
    """Regular user (role=user) cannot access admin-gated endpoints."""
    r = await client.get("/v1/admin/alerts", headers=_auth(registered_user["tokens"]))
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_super_admin_refresh_preserves_role(client, db_session, mock_redis):
    """Token refresh issues a new JWT that still carries super_admin role."""
    sa = await _make_super_admin(client, db_session)
    r = await client.post("/auth/refresh", json={"refresh_token": sa["tokens"]["refresh_token"]})
    assert r.status_code == 200
    from app.services.token import decode_token
    payload = decode_token(r.json()["access_token"])
    assert payload["role"] == "super_admin"
