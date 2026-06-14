import pytest
from httpx import AsyncClient
from sqlalchemy import update
from app.models.user import User, AccountStatus


async def _login_tokens(client, db_session, phone):
    await client.post("/auth/register", json={
        "full_name": "MFA User",
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
async def test_totp_enroll_and_verify(client: AsyncClient, db_session):
    import pyotp
    tokens = await _login_tokens(client, db_session, "01766000001")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    # Enroll
    resp = await client.post("/auth/mfa/enroll/totp", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "secret" in data
    assert "qr_data_url" in data

    method_id = data["method_id"]
    secret = data["secret"]

    # Verify enroll with live TOTP code
    code = pyotp.TOTP(secret).now()
    resp2 = await client.post("/auth/mfa/enroll/verify", json={"method_id": method_id, "code": code}, headers=headers)
    assert resp2.status_code == 200
    verify_data = resp2.json()
    assert verify_data["activated"] is True
    assert len(verify_data["recovery_codes"]) == 10


@pytest.mark.asyncio
async def test_mfa_login_flow(client: AsyncClient, db_session, mock_redis):
    import pyotp
    redis_mock, redis_store = mock_redis  # mock_redis yields (FakeRedis, dict)
    tokens = await _login_tokens(client, db_session, "01766000002")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    # Enroll MFA
    resp = await client.post("/auth/mfa/enroll/totp", headers=headers)
    data = resp.json()
    method_id, secret = data["method_id"], data["secret"]
    code = pyotp.TOTP(secret).now()
    await client.post("/auth/mfa/enroll/verify", json={"method_id": method_id, "code": code}, headers=headers)

    # Login now requires MFA
    resp2 = await client.post("/auth/login", json={"identifier": "01766000002", "password": "SecurePass123!"})
    assert resp2.status_code == 200
    login_data = resp2.json()
    assert login_data.get("mfa_required") is True
    mfa_token = login_data["mfa_token"]

    # Complete MFA
    live_code = pyotp.TOTP(secret).now()
    resp3 = await client.post("/auth/mfa/verify", json={"mfa_token": mfa_token, "code": live_code})
    assert resp3.status_code == 200
    assert "access_token" in resp3.json()
