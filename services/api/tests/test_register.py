import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_phone_success(client: AsyncClient):
    resp = await client.post("/auth/register", json={
        "full_name": "Test User",
        "phone": "01712345678",
        "password": "SecurePass123!",
        "terms": True,
        "data_consent": True,
    })
    assert resp.status_code == 201
    assert "verification" in resp.json()["message"].lower()


@pytest.mark.asyncio
async def test_register_resend_while_pending(client: AsyncClient):
    # Re-registering before verifying resends the OTP — no ghost account, returns 201.
    payload = {
        "full_name": "Dup User",
        "phone": "01712345679",
        "password": "SecurePass123!",
        "terms": True,
        "data_consent": True,
    }
    await client.post("/auth/register", json=payload)
    resp = await client.post("/auth/register", json=payload)
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_register_duplicate_active_account(client: AsyncClient):
    # Re-registering after successful verification → 409.
    payload = {
        "full_name": "Dup User",
        "phone": "01799990001",
        "password": "SecurePass123!",
        "terms": True,
        "data_consent": True,
    }
    reg = await client.post("/auth/register", json=payload)
    otp = reg.json()["dev_otp"]
    await client.post("/auth/verify-phone", json={"phone": "01799990001", "code": otp})

    resp = await client.post("/auth/register", json=payload)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_register_missing_identifier(client: AsyncClient):
    resp = await client.post("/auth/register", json={
        "full_name": "No ID",
        "password": "SecurePass123!",
        "terms": True,
        "data_consent": True,
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_no_terms(client: AsyncClient):
    resp = await client.post("/auth/register", json={
        "full_name": "No Terms",
        "phone": "01712345680",
        "password": "SecurePass123!",
        "terms": False,
        "data_consent": True,
    })
    assert resp.status_code == 422
