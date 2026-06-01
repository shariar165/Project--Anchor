import pytest
from httpx import AsyncClient
from sqlalchemy import update
from app.models.user import User, AccountStatus


async def _active_user_tokens(client: AsyncClient, db_session, phone: str) -> dict:
    await client.post("/auth/register", json={
        "full_name": "Rotation User",
        "phone": phone,
        "password": "SecurePass123!",
        "terms": True,
        "data_consent": True,
    })
    await db_session.execute(update(User).where(User.phone == phone).values(status=AccountStatus.active, phone_verified=True))
    await db_session.commit()
    resp = await client.post("/auth/login", json={"identifier": phone, "password": "SecurePass123!"})
    return resp.json()


@pytest.mark.asyncio
async def test_refresh_issues_new_pair(client: AsyncClient, db_session):
    tokens = await _active_user_tokens(client, db_session, "01788000001")
    resp = await client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert resp.status_code == 200
    new_tokens = resp.json()
    assert new_tokens["refresh_token"] != tokens["refresh_token"]
    assert new_tokens["access_token"] != tokens["access_token"]


@pytest.mark.asyncio
async def test_old_refresh_blacklisted_after_rotation(client: AsyncClient, db_session):
    tokens = await _active_user_tokens(client, db_session, "01788000002")
    await client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    # Replay old refresh → should detect theft → 401
    resp = await client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_logout_blacklists_access_token(client: AsyncClient, db_session):
    tokens = await _active_user_tokens(client, db_session, "01788000003")
    access = tokens["access_token"]
    refresh = tokens["refresh_token"]

    resp = await client.post("/auth/logout", json={"refresh_token": refresh}, headers={"Authorization": f"Bearer {access}"})
    assert resp.status_code == 200

    resp2 = await client.get("/auth/me", headers={"Authorization": f"Bearer {access}"})
    assert resp2.status_code == 401
