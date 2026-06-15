import pytest
from httpx import AsyncClient


async def _active_user_tokens(client: AsyncClient, phone: str) -> dict:
    reg = await client.post("/auth/register", json={
        "full_name": "Rotation User",
        "phone": phone,
        "password": "SecurePass123!",
        "terms": True,
        "data_consent": True,
    })
    otp = reg.json()["dev_otp"]
    await client.post("/auth/verify-phone", json={"phone": phone, "code": otp})
    resp = await client.post("/auth/login", json={"identifier": phone, "password": "SecurePass123!"})
    return resp.json()


@pytest.mark.asyncio
async def test_refresh_issues_new_pair(client: AsyncClient):
    tokens = await _active_user_tokens(client, "01788000001")
    resp = await client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert resp.status_code == 200
    new_tokens = resp.json()
    assert new_tokens["refresh_token"] != tokens["refresh_token"]
    assert new_tokens["access_token"] != tokens["access_token"]


@pytest.mark.asyncio
async def test_old_refresh_blacklisted_after_rotation(client: AsyncClient):
    tokens = await _active_user_tokens(client, "01788000002")
    await client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    # Replay old refresh → should detect theft → 401
    resp = await client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_logout_blacklists_access_token(client: AsyncClient):
    tokens = await _active_user_tokens(client, "01788000003")
    access = tokens["access_token"]
    refresh = tokens["refresh_token"]

    resp = await client.post("/auth/logout", json={"refresh_token": refresh}, headers={"Authorization": f"Bearer {access}"})
    assert resp.status_code == 200

    resp2 = await client.get("/auth/me", headers={"Authorization": f"Bearer {access}"})
    assert resp2.status_code == 401
