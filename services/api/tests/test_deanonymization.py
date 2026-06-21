"""
Tests for /v1/admin/deanonymization — the two-person identity-release workflow.
SQLite in-memory + fakeredis, no Docker required.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, update

from app.models.filing import Filing, FilingTemplate
from app.models.user import User, Role
from app.services import deanon_svc
from app.services.filing_svc import _encrypt_actor


def _auth(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def _make_role(client, db_session, role: str) -> dict:
    email = f"{role}_{uuid.uuid4().hex[:6]}@example.com"
    password = "Secure!Pass99"
    reg = await client.post("/auth/register", json={
        "full_name": f"Test {role}",
        "email": email,
        "password": password,
        "role": "user",
        "terms": True,
        "data_consent": True,
    })
    assert reg.status_code == 201
    otp = reg.json()["dev_otp"]
    await client.post("/auth/verify-email", json={"token": f"{email}:{otp}"})
    await db_session.execute(update(User).where(User.email == email).values(role=Role(role)))
    await db_session.commit()
    login = await client.post("/auth/login", json={"identifier": email, "password": password})
    assert login.status_code == 200
    return {"email": email, "password": password, "tokens": login.json()}


async def _anon_filing(db_session, complainant_id: uuid.UUID) -> str:
    """Insert an anonymous filing whose actor link encrypts `complainant_id`.
    Returns its filing_number."""
    template = FilingTemplate(
        key=f"tmpl_{uuid.uuid4().hex[:6]}", name="Anon complaint",
        name_bn="", category="complaint", anonymity_mode="anonymous",
    )
    db_session.add(template)
    await db_session.flush()
    number = f"DIU-CMP-2026-{uuid.uuid4().hex[:5].upper()}"
    filing = Filing(
        filing_number=number, category="complaint", template_id=template.id,
        encrypted_actor_link=_encrypt_actor(complainant_id),
        anonymous_tracking_code=uuid.uuid4().hex[:12].upper(),
        state="routed",
    )
    db_session.add(filing)
    await db_session.commit()
    return number


async def _seed_request(client, db_session, requester_tokens) -> tuple[str, uuid.UUID]:
    """Create a complainant + anonymous filing + open a deanon request. Returns
    (request_id, complainant_id)."""
    complainant = await _make_role(client, db_session, "user")
    crow = (await db_session.execute(
        select(User).where(User.email == complainant["email"]))).scalars().first()
    number = await _anon_filing(db_session, crow.id)
    r = await client.post("/v1/admin/deanonymization", json={
        "target_type": "filing", "target_ref": number,
        "legal_basis": "Penal Code §509", "reason": "Police investigation, formal letter attached.",
        "formal_letter_ref": "PROV/2026/118",
    }, headers=_auth(requester_tokens))
    assert r.status_code == 201, r.text
    return r.json()["id"], crow.id


@pytest.mark.asyncio
async def test_create_request_appears_in_queue(client, db_session, mock_redis):
    sa = await _make_role(client, db_session, "super_admin")
    req_id, _ = await _seed_request(client, db_session, sa["tokens"])

    q = await client.get("/v1/admin/deanonymization", headers=_auth(sa["tokens"]))
    assert q.status_code == 200
    body = q.json()
    assert body["total"] >= 1
    found = next(x for x in body["items"] if x["id"] == req_id)
    assert found["status"] == "pending_review"
    assert found["request_number"].startswith("DAR-")
    assert found["legal_basis"] == "Penal Code §509"


@pytest.mark.asyncio
async def test_non_super_admin_blocked_from_queue(client, db_session, mock_redis):
    admin = await _make_role(client, db_session, "admin")
    r = await client.get("/v1/admin/deanonymization", headers=_auth(admin["tokens"]))
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_two_person_control(client, db_session, mock_redis):
    sa1 = await _make_role(client, db_session, "super_admin")
    sa2 = await _make_role(client, db_session, "super_admin")
    req_id, _ = await _seed_request(client, db_session, sa1["tokens"])

    # First approval -> awaiting_second_approval
    r1 = await client.post(f"/v1/admin/deanonymization/{req_id}/approve", headers=_auth(sa1["tokens"]))
    assert r1.status_code == 200
    assert r1.json()["status"] == "awaiting_second_approval"
    assert r1.json()["first_approval"]["user_id"]

    # Same admin cannot give the second approval
    r2 = await client.post(f"/v1/admin/deanonymization/{req_id}/approve", headers=_auth(sa1["tokens"]))
    assert r2.status_code == 409

    # A different super admin completes the release
    r3 = await client.post(f"/v1/admin/deanonymization/{req_id}/approve", headers=_auth(sa2["tokens"]))
    assert r3.status_code == 200
    assert r3.json()["status"] == "approved"
    assert r3.json()["access_expires_at"]


@pytest.mark.asyncio
async def test_deny_path(client, db_session, mock_redis):
    sa = await _make_role(client, db_session, "super_admin")
    req_id, _ = await _seed_request(client, db_session, sa["tokens"])
    r = await client.post(f"/v1/admin/deanonymization/{req_id}/deny",
                          json={"reason": "No formal letter."}, headers=_auth(sa["tokens"]))
    assert r.status_code == 200
    assert r.json()["status"] == "denied"
    assert r.json()["denied_reason"] == "No formal letter."

    # Denied request can no longer be approved
    r2 = await client.post(f"/v1/admin/deanonymization/{req_id}/approve", headers=_auth(sa["tokens"]))
    assert r2.status_code == 409


@pytest.mark.asyncio
async def test_reveal_only_after_approval(client, db_session, mock_redis):
    sa1 = await _make_role(client, db_session, "super_admin")
    sa2 = await _make_role(client, db_session, "super_admin")
    req_id, complainant_id = await _seed_request(client, db_session, sa1["tokens"])

    # Cannot reveal before approval
    pre = await client.post(f"/v1/admin/deanonymization/{req_id}/reveal", headers=_auth(sa1["tokens"]))
    assert pre.status_code == 409

    await client.post(f"/v1/admin/deanonymization/{req_id}/approve", headers=_auth(sa1["tokens"]))
    await client.post(f"/v1/admin/deanonymization/{req_id}/approve", headers=_auth(sa2["tokens"]))

    rev = await client.post(f"/v1/admin/deanonymization/{req_id}/reveal", headers=_auth(sa1["tokens"]))
    assert rev.status_code == 200
    assert rev.json()["user_id"] == str(complainant_id)
    assert rev.json()["email"]
    assert rev.json()["masked_email"]


@pytest.mark.asyncio
async def test_reveal_blocked_after_window_expires(client, db_session, mock_redis):
    sa1 = await _make_role(client, db_session, "super_admin")
    sa2 = await _make_role(client, db_session, "super_admin")
    req_id, _ = await _seed_request(client, db_session, sa1["tokens"])
    await client.post(f"/v1/admin/deanonymization/{req_id}/approve", headers=_auth(sa1["tokens"]))
    await client.post(f"/v1/admin/deanonymization/{req_id}/approve", headers=_auth(sa2["tokens"]))

    # Force the access window into the past
    from app.models.deanonymization import DeanonymizationRequest
    await db_session.execute(
        update(DeanonymizationRequest)
        .where(DeanonymizationRequest.id == uuid.UUID(req_id))
        .values(access_expires_at=datetime.now(timezone.utc) - timedelta(minutes=1))
    )
    await db_session.commit()

    rev = await client.post(f"/v1/admin/deanonymization/{req_id}/reveal", headers=_auth(sa1["tokens"]))
    assert rev.status_code == 409
    # Request is now marked expired
    got = await client.get(f"/v1/admin/deanonymization/{req_id}", headers=_auth(sa1["tokens"]))
    assert got.json()["status"] == "expired"


@pytest.mark.asyncio
async def test_stats_and_audit_trail(client, db_session, mock_redis):
    sa1 = await _make_role(client, db_session, "super_admin")
    sa2 = await _make_role(client, db_session, "super_admin")
    req_id, _ = await _seed_request(client, db_session, sa1["tokens"])
    await client.post(f"/v1/admin/deanonymization/{req_id}/approve", headers=_auth(sa1["tokens"]))
    await client.post(f"/v1/admin/deanonymization/{req_id}/approve", headers=_auth(sa2["tokens"]))
    await client.post(f"/v1/admin/deanonymization/{req_id}/reveal", headers=_auth(sa1["tokens"]))

    stats = await client.get("/v1/admin/deanonymization/stats", headers=_auth(sa1["tokens"]))
    assert stats.status_code == 200
    assert stats.json()["approved"] >= 1

    # Audit chain carries the workflow events
    from app.models.audit import AuditLog
    rows = (await db_session.execute(select(AuditLog.event_type))).scalars().all()
    for ev in ("DEANON_REQUEST_CREATED", "DEANON_FIRST_APPROVAL",
               "DEANON_APPROVED_RELEASED", "DEANON_IDENTITY_REVEALED"):
        assert ev in rows
