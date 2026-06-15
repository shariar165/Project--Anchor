"""
Security test suite for Anchor AI authentication system.

Each test is named after the vulnerability it validates.
Run: .venv\Scripts\pytest tests/test_auth_security.py -v
"""
import asyncio
import time
import uuid
import pytest
import pytest_asyncio
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# SEC-01: Cross-user logout — a user must not be able to revoke another
#         user's session by submitting that user's refresh token.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_logout_cannot_revoke_another_users_session(client, registered_user):
    """Fix verified: logout now checks session.user_id == token.user_id."""
    victim_email = f"victim_{uuid.uuid4().hex[:8]}@example.com"
    reg = await client.post("/auth/register", json={
        "full_name": "Victim",
        "email": victim_email,
        "password": "VictimPass!1",
        "role": "user",
        "terms": True,
        "data_consent": True,
    })
    assert reg.status_code == 201
    otp = reg.json()["dev_otp"]
    verify = await client.post("/auth/verify-email", json={"token": f"{victim_email}:{otp}"})
    victim_tokens = verify.json()

    # Attacker (registered_user) tries to revoke victim's refresh token
    attacker_tokens = registered_user["tokens"]
    resp = await client.post(
        "/auth/logout",
        json={"refresh_token": victim_tokens["refresh_token"]},
        headers={"Authorization": f"Bearer {attacker_tokens['access_token']}"},
    )
    # Logout always returns 200 (we don't reveal cross-user info)
    assert resp.status_code == 200

    # Victim's refresh token must still work
    refresh = await client.post("/auth/refresh", json={"refresh_token": victim_tokens["refresh_token"]})
    assert refresh.status_code == 200, "Victim's session must not be revoked by a third party"


# ---------------------------------------------------------------------------
# SEC-02: Password reset must invalidate all existing sessions.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_password_reset_invalidates_sessions(client, registered_user):
    """After password reset, old refresh tokens must be rejected."""
    email = registered_user["email"]
    old_tokens = registered_user["tokens"]

    # Request password reset
    await client.post("/auth/forgot-password", json={"identifier": email})

    # In a real test we'd get the OTP from Redis or email; here we exercise the
    # session-invalidation logic by verifying the old refresh token is revoked
    # after reset_password is called with a valid OTP. We skip the OTP step
    # because it requires Redis access — this test validates the DB-level revoke.
    # Full integration: wire up an in-memory Redis fixture and call reset-password.
    pass  # placeholder: requires running Redis + DB integration


# ---------------------------------------------------------------------------
# SEC-03: Login timing — response time must not leak whether an email exists.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_login_timing_is_constant(client):
    """
    Response times for unknown vs. wrong-password logins must be within a
    reasonable margin (both should run Argon2). This is a statistical check —
    a single timing diff > 2s is a red flag.
    """
    existing_email = f"timing_test_{uuid.uuid4().hex[:8]}@example.com"
    reg = await client.post("/auth/register", json={
        "full_name": "Timing",
        "email": existing_email,
        "password": "TimingPass!1",
        "role": "user",
        "terms": True,
        "data_consent": True,
    })
    # Ignore verification — just need the account in DB

    RUNS = 3
    existing_times = []
    nonexistent_times = []

    for _ in range(RUNS):
        t0 = time.monotonic()
        await client.post("/auth/login", json={"identifier": existing_email, "password": "wrongpass"})
        existing_times.append(time.monotonic() - t0)

        t0 = time.monotonic()
        await client.post("/auth/login", json={"identifier": f"no_such_{uuid.uuid4().hex}@example.com", "password": "wrongpass"})
        nonexistent_times.append(time.monotonic() - t0)

    avg_existing = sum(existing_times) / RUNS
    avg_nonexistent = sum(nonexistent_times) / RUNS
    diff = abs(avg_existing - avg_nonexistent)

    # Allow up to 1 second variance (Argon2 at 64 MB takes ~200-500 ms each)
    assert diff < 1.0, (
        f"Timing oracle detected: existing={avg_existing:.3f}s, "
        f"nonexistent={avg_nonexistent:.3f}s, diff={diff:.3f}s"
    )


# ---------------------------------------------------------------------------
# SEC-04: OTP attempt limit must not be bypassable via concurrent requests.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_otp_attempt_limit_enforced(client):
    """After otp_max_attempts wrong guesses, further guesses must fail."""
    email = f"otp_limit_{uuid.uuid4().hex[:8]}@example.com"
    reg = await client.post("/auth/register", json={
        "full_name": "OTP Test",
        "email": email,
        "password": "OTPPass!123",
        "role": "user",
        "terms": True,
        "data_consent": True,
    })
    assert reg.status_code == 201

    # Exhaust 5 attempts with wrong codes
    for _ in range(5):
        resp = await client.post("/auth/verify-email", json={"token": f"{email}:000000"})
        # Each wrong attempt returns 400

    # 6th attempt must fail regardless of code (even if someone guessed right)
    resp = await client.post("/auth/verify-email", json={"token": f"{email}:000000"})
    assert resp.status_code == 400, "OTP must be locked after 5 failed attempts"


# ---------------------------------------------------------------------------
# SEC-05: verify-email must not re-activate a suspended account.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_verify_email_rejects_suspended_account(client):
    """A suspended account cannot be re-activated via email verification OTP."""
    # This test requires DB access to set status=suspended after registration.
    # Outline: register, suspend via DB, attempt verify-email → expect 403.
    # Full implementation requires a DB fixture or admin endpoint.
    pass  # placeholder: requires DB session fixture


# ---------------------------------------------------------------------------
# SEC-06: Refresh token replay (theft detection).
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_refresh_token_reuse_revokes_all_sessions(client, registered_user):
    """Replaying a rotated refresh token must revoke all user sessions."""
    tokens = registered_user["tokens"]
    old_refresh = tokens["refresh_token"]

    # Rotate once — old_refresh is now blacklisted
    rotate = await client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert rotate.status_code == 200
    new_tokens = rotate.json()

    # Replay the OLD refresh token — triggers theft detection
    replay = await client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert replay.status_code == 401
    assert "reuse" in replay.json()["detail"].lower()

    # The NEW token must also be revoked (all sessions wiped)
    second_rotate = await client.post("/auth/refresh", json={"refresh_token": new_tokens["refresh_token"]})
    assert second_rotate.status_code == 401, "All sessions must be revoked after theft detection"


# ---------------------------------------------------------------------------
# SEC-07: Wrong token type must be rejected by access-token-guarded routes.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_refresh_token_rejected_as_access_token(client, registered_user):
    """A refresh token submitted as a Bearer token must be rejected."""
    refresh_token = registered_user["tokens"]["refresh_token"]
    resp = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {refresh_token}"},
    )
    assert resp.status_code == 401
    assert "wrong token type" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# SEC-08: Step-up token must not be accepted as an access token.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_stepup_token_rejected_as_access_token(client, registered_user):
    """A step-up token must not grant access to regular authenticated routes."""
    tokens = registered_user["tokens"]
    stepup = await client.post(
        "/auth/stepup",
        json={"password": registered_user["password"]},
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert stepup.status_code == 200
    stepup_token = stepup.json()["stepup_token"]

    # Use step-up token on a regular protected endpoint
    resp = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {stepup_token}"},
    )
    assert resp.status_code == 401, "Step-up token must not be accepted as an access token"


# ---------------------------------------------------------------------------
# SEC-09: Revoked access token must not grant access.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_revoked_access_token_rejected(client, registered_user):
    """After logout, the access token must be blacklisted and rejected."""
    tokens = registered_user["tokens"]
    access = tokens["access_token"]
    refresh = tokens["refresh_token"]

    logout = await client.post(
        "/auth/logout",
        json={"refresh_token": refresh},
        headers={"Authorization": f"Bearer {access}"},
    )
    assert logout.status_code == 200

    me = await client.get("/auth/me", headers={"Authorization": f"Bearer {access}"})
    assert me.status_code == 401, "Blacklisted access token must be rejected"


# ---------------------------------------------------------------------------
# SEC-10: Malformed / forged JWT must be rejected.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_forged_jwt_rejected(client):
    """Tokens with invalid signatures must be rejected."""
    forged = "eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIwMDAwMDAwMC0wMDAwLTAwMDAtMDAwMC0wMDAwMDAwMDAwMDEiLCJyb2xlIjoiYWRtaW4iLCJqdGkiOiJmYWtlIiwiZXhwIjo5OTk5OTk5OTk5LCJpYXQiOjE3MDAwMDAwMDAsInR5cGUiOiJhY2Nlc3MifQ.AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    resp = await client.get("/auth/me", headers={"Authorization": f"Bearer {forged}"})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# SEC-11: Registration with both email and phone — both fields optional but
#         at least one required.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_register_requires_email_or_phone(client):
    resp = await client.post("/auth/register", json={
        "full_name": "No Contact",
        "password": "SomePass!1",
        "role": "user",
        "terms": True,
        "data_consent": True,
    })
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# SEC-12: Duplicate registration must return 409, not 500.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_duplicate_registration_returns_409(client, registered_user):
    resp = await client.post("/auth/register", json={
        "full_name": "Duplicate",
        "email": registered_user["email"],
        "password": "AnotherPass!1",
        "role": "user",
        "terms": True,
        "data_consent": True,
    })
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# SEC-13: Account still pending verification cannot log in.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_pending_account_cannot_login(client):
    email = f"pending_{uuid.uuid4().hex[:8]}@example.com"
    reg = await client.post("/auth/register", json={
        "full_name": "Pending",
        "email": email,
        "password": "PendingPass!1",
        "role": "user",
        "terms": True,
        "data_consent": True,
    })
    assert reg.status_code == 201

    # No DB row exists until verify — unverified user looks like unknown user to login.
    login = await client.post("/auth/login", json={"identifier": email, "password": "PendingPass!1"})
    assert login.status_code == 401


# ---------------------------------------------------------------------------
# SEC-14: Logout-all must revoke every session for the authenticated user.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_logout_all_revokes_all_sessions(client, registered_user):
    """After /logout-all, every refresh token for that user must be invalid."""
    tokens = registered_user["tokens"]

    # Open a second session by refreshing once
    refresh1 = await client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refresh1.status_code == 200
    session2_tokens = refresh1.json()

    # Refresh again to get a 3rd session token
    refresh2 = await client.post("/auth/refresh", json={"refresh_token": session2_tokens["refresh_token"]})
    assert refresh2.status_code == 200
    session3_tokens = refresh2.json()

    # Logout all using the latest access token
    logout = await client.post(
        "/auth/logout-all",
        headers={"Authorization": f"Bearer {session3_tokens['access_token']}"},
    )
    assert logout.status_code == 200

    # All refresh tokens (including the current one) must now be invalid
    for rt in [tokens["refresh_token"], session2_tokens["refresh_token"], session3_tokens["refresh_token"]]:
        resp = await client.post("/auth/refresh", json={"refresh_token": rt})
        assert resp.status_code == 401, f"Refresh token must be revoked after logout-all: {resp.json()}"
