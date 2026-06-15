import pytest
from httpx import AsyncClient
from app.models.user import AccountStatus


async def _register_and_activate(client: AsyncClient, mock_redis_store: dict, phone: str = "01799000001"):
    await client.post("/auth/register", json={
        "full_name": "Login User",
        "phone": phone,
        "password": "SecurePass123!",
        "terms": True,
        "data_consent": True,
    })
    # Find the OTP from mock redis store
    otp_key = f"otp:{phone}:registration"
    # In test, OTP is stored hashed — we need to bypass by directly activating
    # Patch the user status directly via the DB
    from sqlalchemy import select, update
    from app.models.user import User
    return phone


@pytest.mark.asyncio
async def test_login_unverified_rejected(client: AsyncClient, mock_redis, db_session):
    phone = "01799000002"
    await client.post("/auth/register", json={
        "full_name": "Unverified",
        "phone": phone,
        "password": "SecurePass123!",
        "terms": True,
        "data_consent": True,
    })
    # No DB row exists until verify — unverified user looks like unknown user to login.
    resp = await client.post("/auth/login", json={"identifier": phone, "password": "SecurePass123!"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, db_session):
    from sqlalchemy import select, update
    from app.models.user import User, AccountStatus

    phone = "01799000003"
    await client.post("/auth/register", json={
        "full_name": "WrongPw",
        "phone": phone,
        "password": "SecurePass123!",
        "terms": True,
        "data_consent": True,
    })
    await db_session.execute(update(User).where(User.phone == phone).values(status=AccountStatus.active, phone_verified=True))
    await db_session.commit()

    resp = await client.post("/auth/login", json={"identifier": phone, "password": "WrongPassword!"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    phone = "01799000004"
    reg = await client.post("/auth/register", json={
        "full_name": "Active User",
        "phone": phone,
        "password": "SecurePass123!",
        "terms": True,
        "data_consent": True,
    })
    otp = reg.json()["dev_otp"]
    await client.post("/auth/verify-phone", json={"phone": phone, "code": otp})

    resp = await client.post("/auth/login", json={"identifier": phone, "password": "SecurePass123!"})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
