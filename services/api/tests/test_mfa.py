import pytest
from httpx import AsyncClient


async def _login_tokens(client, phone):
    reg = await client.post("/auth/register", json={
        "full_name": "MFA User",
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
async def test_totp_enroll_and_verify(client: AsyncClient):
    import pyotp
    tokens = await _login_tokens(client, "01766000001")
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
async def test_mfa_login_flow(client: AsyncClient, mock_redis):
    import pyotp
    tokens = await _login_tokens(client, "01766000002")
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


# ── Additional coverage for the contract the student app depends on ──────────

def _auth(tokens):
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def _enroll_and_activate(client, tokens):
    """Run full enrollment; return (method_id, secret, recovery_codes)."""
    import pyotp
    r = await client.post("/auth/mfa/enroll/totp", headers=_auth(tokens))
    assert r.status_code == 200, r.json()
    body = r.json()
    assert body["otpauth_uri"].startswith("otpauth://totp/")
    assert body["qr_data_url"].startswith("data:image/png;base64,")
    code = pyotp.TOTP(body["secret"]).now()
    v = await client.post("/auth/mfa/enroll/verify", headers=_auth(tokens),
                          json={"method_id": body["method_id"], "code": code})
    assert v.status_code == 200, v.json()
    return body["method_id"], body["secret"], v.json()["recovery_codes"]


@pytest.mark.asyncio
async def test_enroll_requires_auth(client: AsyncClient):
    r = await client.post("/auth/mfa/enroll/totp")
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_enroll_verify_rejects_wrong_code(client: AsyncClient, registered_user):
    r = await client.post("/auth/mfa/enroll/totp", headers=_auth(registered_user["tokens"]))
    method_id = r.json()["method_id"]
    v = await client.post("/auth/mfa/enroll/verify", headers=_auth(registered_user["tokens"]),
                          json={"method_id": method_id, "code": "000000"})
    assert v.status_code == 400


@pytest.mark.asyncio
async def test_me_reflects_mfa_enabled(client: AsyncClient, registered_user):
    await _enroll_and_activate(client, registered_user["tokens"])
    me = await client.get("/auth/me", headers=_auth(registered_user["tokens"]))
    assert me.status_code == 200
    assert me.json()["mfa_enabled"] is True


@pytest.mark.asyncio
async def test_login_gated_no_session_issued(client: AsyncClient, registered_user):
    await _enroll_and_activate(client, registered_user["tokens"])
    login = await client.post("/auth/login", json={
        "identifier": registered_user["email"], "password": registered_user["password"],
    })
    body = login.json()
    assert body.get("mfa_required") is True
    assert body.get("mfa_token")
    assert "access_token" not in body


@pytest.mark.asyncio
async def test_mfa_verify_rejects_wrong_code(client: AsyncClient, registered_user):
    await _enroll_and_activate(client, registered_user["tokens"])
    login = await client.post("/auth/login", json={
        "identifier": registered_user["email"], "password": registered_user["password"],
    })
    mfa_token = login.json()["mfa_token"]
    v = await client.post("/auth/mfa/verify", json={"mfa_token": mfa_token, "code": "000000"})
    assert v.status_code == 400


@pytest.mark.asyncio
async def test_mfa_token_is_single_use(client: AsyncClient, registered_user):
    import pyotp
    _, secret, _ = await _enroll_and_activate(client, registered_user["tokens"])
    login = await client.post("/auth/login", json={
        "identifier": registered_user["email"], "password": registered_user["password"],
    })
    mfa_token = login.json()["mfa_token"]
    first = await client.post("/auth/mfa/verify",
                              json={"mfa_token": mfa_token, "code": pyotp.TOTP(secret).now()})
    assert first.status_code == 200
    again = await client.post("/auth/mfa/verify",
                              json={"mfa_token": mfa_token, "code": pyotp.TOTP(secret).now()})
    assert again.status_code == 401


@pytest.mark.asyncio
async def test_recovery_code_logs_in_once(client: AsyncClient, registered_user):
    _, _, recovery_codes = await _enroll_and_activate(client, registered_user["tokens"])
    code0 = recovery_codes[0]

    login = await client.post("/auth/login", json={
        "identifier": registered_user["email"], "password": registered_user["password"],
    })
    r = await client.post("/auth/mfa/recovery",
                          json={"mfa_token": login.json()["mfa_token"], "recovery_code": code0})
    assert r.status_code == 200, r.json()
    assert r.json()["access_token"]

    login2 = await client.post("/auth/login", json={
        "identifier": registered_user["email"], "password": registered_user["password"],
    })
    again = await client.post("/auth/mfa/recovery",
                              json={"mfa_token": login2.json()["mfa_token"], "recovery_code": code0})
    assert again.status_code == 400


@pytest.mark.asyncio
async def test_recovery_rejects_unknown_code(client: AsyncClient, registered_user):
    await _enroll_and_activate(client, registered_user["tokens"])
    login = await client.post("/auth/login", json={
        "identifier": registered_user["email"], "password": registered_user["password"],
    })
    r = await client.post("/auth/mfa/recovery",
                          json={"mfa_token": login.json()["mfa_token"], "recovery_code": "DEAD-BEEF-0000-1111"})
    assert r.status_code == 400
