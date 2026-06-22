"""Tests for E2EE public-key exchange + user<->lawyer encrypted messaging."""
import uuid
import pytest
from sqlalchemy import update

from app.models.user import User
from app.models.lawyer import Lawyer


async def _register(client, mock_redis):
    email = f"msg_{uuid.uuid4().hex[:8]}@example.com"
    password = "SecurePass!99"
    reg = await client.post("/auth/register", json={
        "full_name": "Msg User",
        "email": email,
        "password": password,
        "role": "user",
        "terms": True,
        "data_consent": True,
    })
    assert reg.status_code == 201, reg.text
    otp = reg.json()["dev_otp"]
    verify = await client.post("/auth/verify-email", json={"token": f"{email}:{otp}"})
    assert verify.status_code == 200, verify.text
    tokens = verify.json()
    me = await client.get("/auth/me", headers={
        "Authorization": f"Bearer {tokens['access_token']}"
    })
    return {
        "email": email, "password": password, "tokens": tokens,
        "id": me.json()["id"],
    }


def _auth(acct):
    return {"Authorization": f"Bearer {acct['tokens']['access_token']}"}


async def _make_verified_lawyer(client, db_session, acct, bar="BAR-9"):
    """Promote an account to a verified, account-linked lawyer directly in the DB."""
    lawyer = Lawyer(
        user_id=uuid.UUID(acct["id"]),
        name="Verified Lawyer",
        bar_number=bar,
        district="Dhaka",
        specializations=["Criminal"],
        status="verified",
        verified=True,
    )
    db_session.add(lawyer)
    await db_session.execute(
        update(User).where(User.email == acct["email"]).values(role="lawyer")
    )
    await db_session.commit()
    return lawyer.id


@pytest.mark.asyncio
async def test_e2ee_key_roundtrip(client, mock_redis, db_session):
    acct = await _register(client, mock_redis)
    put = await client.put("/v1/e2ee/keys", json={
        "public_key_jwk": '{"kty":"EC","crv":"P-256","x":"abc","y":"def"}',
        "key_fingerprint": "fp123",
    }, headers=_auth(acct))
    assert put.status_code == 200, put.text

    get = await client.get(f"/v1/e2ee/keys/{acct['id']}", headers=_auth(acct))
    assert get.status_code == 200
    assert get.json()["key_fingerprint"] == "fp123"
    assert "P-256" in get.json()["public_key_jwk"]


@pytest.mark.asyncio
async def test_get_missing_key_404(client, mock_redis, db_session):
    acct = await _register(client, mock_redis)
    other = await _register(client, mock_redis)
    resp = await client.get(f"/v1/e2ee/keys/{other['id']}", headers=_auth(acct))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_start_conversation_with_verified_lawyer(client, mock_redis, db_session):
    user = await _register(client, mock_redis)
    lawyer_acct = await _register(client, mock_redis)
    lawyer_id = await _make_verified_lawyer(client, db_session, lawyer_acct)

    # Give the lawyer a public key so the response carries it.
    await client.put("/v1/e2ee/keys", json={
        "public_key_jwk": '{"kty":"EC"}', "key_fingerprint": "lk",
    }, headers=_auth(lawyer_acct))

    resp = await client.post("/v1/conversations", json={"lawyer_id": str(lawyer_id)}, headers=_auth(user))
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["counterpart_user_id"] == lawyer_acct["id"]
    assert body["counterpart_role"] == "lawyer"
    assert body["counterpart_public_key"] is not None

    # Idempotent: starting again returns the same conversation.
    resp2 = await client.post("/v1/conversations", json={"lawyer_id": str(lawyer_id)}, headers=_auth(user))
    assert resp2.status_code == 201
    assert resp2.json()["id"] == body["id"]


@pytest.mark.asyncio
async def test_cannot_start_with_unverified_lawyer(client, mock_redis, db_session):
    user = await _register(client, mock_redis)
    # Standalone (no user_id), unverified directory row.
    lawyer = Lawyer(name="Ghost", district="Dhaka", specializations=[], verified=False, status="pending")
    db_session.add(lawyer)
    await db_session.commit()

    resp = await client.post("/v1/conversations", json={"lawyer_id": str(lawyer.id)}, headers=_auth(user))
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_send_and_list_messages(client, mock_redis, db_session):
    user = await _register(client, mock_redis)
    lawyer_acct = await _register(client, mock_redis)
    lawyer_id = await _make_verified_lawyer(client, db_session, lawyer_acct)

    conv = await client.post("/v1/conversations", json={"lawyer_id": str(lawyer_id)}, headers=_auth(user))
    conv_id = conv.json()["id"]

    send = await client.post(f"/v1/conversations/{conv_id}/messages", json={
        "ciphertext": "ENCRYPTED_BLOB", "iv": "aabbcc",
    }, headers=_auth(user))
    assert send.status_code == 201, send.text
    assert send.json()["ciphertext"] == "ENCRYPTED_BLOB"

    # Lawyer side sees the conversation and can read the message.
    convs = await client.get("/v1/conversations", headers=_auth(lawyer_acct))
    assert any(c["id"] == conv_id for c in convs.json())

    msgs = await client.get(f"/v1/conversations/{conv_id}/messages", headers=_auth(lawyer_acct))
    assert msgs.status_code == 200
    assert len(msgs.json()) == 1
    assert msgs.json()[0]["ciphertext"] == "ENCRYPTED_BLOB"


@pytest.mark.asyncio
async def test_non_participant_forbidden(client, mock_redis, db_session):
    user = await _register(client, mock_redis)
    lawyer_acct = await _register(client, mock_redis)
    lawyer_id = await _make_verified_lawyer(client, db_session, lawyer_acct)
    conv = await client.post("/v1/conversations", json={"lawyer_id": str(lawyer_id)}, headers=_auth(user))
    conv_id = conv.json()["id"]

    intruder = await _register(client, mock_redis)
    resp = await client.get(f"/v1/conversations/{conv_id}/messages", headers=_auth(intruder))
    assert resp.status_code == 403

    send = await client.post(f"/v1/conversations/{conv_id}/messages", json={
        "ciphertext": "x", "iv": "y",
    }, headers=_auth(intruder))
    assert send.status_code == 403
