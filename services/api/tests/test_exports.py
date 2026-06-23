"""
Tests for the student download/export endpoints (PDF / DOCX / CSV) across
applications, filings, routines and notices.

SQLite in-memory + fakeredis — no Docker required. Templates are inserted
directly since migrations/startup seeding don't run on the SQLite path.
"""
import uuid
import pytest
from sqlalchemy import update

from app.models.user import User
from app.models.application import Application, ApplicationState, ApplicationTemplate


PDF_CT = "application/pdf"
DOCX_CT = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
CSV_CT = "text/csv"
CT = {"pdf": PDF_CT, "docx": DOCX_CT, "csv": CSV_CT}


def _auth(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def _make_admin_tokens(client, db_session, email: str, password: str) -> dict:
    await db_session.execute(update(User).where(User.email == email).values(role="admin"))
    await db_session.commit()
    resp = await client.post("/auth/login", json={"identifier": email, "password": password})
    assert resp.status_code == 200, resp.json()
    return resp.json()


async def _register(client, prefix: str = "user") -> dict:
    email = f"{prefix}_{uuid.uuid4().hex[:8]}@example.com"
    password = "SecurePass!99"
    reg = await client.post("/auth/register", json={
        "full_name": "Export Tester", "email": email, "password": password,
        "role": "user", "terms": True, "data_consent": True,
    })
    assert reg.status_code == 201, reg.json()
    otp = reg.json()["dev_otp"]
    await client.post("/auth/verify-email", json={"token": f"{email}:{otp}"})
    login = await client.post("/auth/login", json={"identifier": email, "password": password})
    return {"email": email, "password": password, "tokens": login.json()}


async def _make_template(db_session) -> ApplicationTemplate:
    tmpl = ApplicationTemplate(
        key=f"tmpl-{uuid.uuid4().hex[:6]}", name="Late Fee Payment",
        name_bn="", skill_reference="generic", requires_accounts_approval=False,
    )
    db_session.add(tmpl)
    await db_session.commit()
    await db_session.refresh(tmpl)
    return tmpl


def _assert_download(resp, fmt: str):
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith(CT[fmt])
    assert "attachment" in resp.headers.get("content-disposition", "")
    assert f".{fmt}" in resp.headers.get("content-disposition", "")
    assert len(resp.content) > 0
    if fmt == "pdf":
        assert resp.content[:4] == b"%PDF"
    elif fmt == "docx":
        assert resp.content[:2] == b"PK"  # docx is a zip


# ── Applications ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize("fmt", ["pdf", "docx", "csv"])
async def test_export_application_each_format(client, db_session, mock_redis, registered_user, fmt):
    tmpl = await _make_template(db_session)
    create = await client.post("/v1/applications", json={
        "template_id": str(tmpl.id), "field_values": {"reason": "x"}, "language": "en",
    }, headers=_auth(registered_user["tokens"]))
    assert create.status_code == 201, create.json()
    app_id = create.json()["id"]

    resp = await client.get(f"/v1/applications/{app_id}/export?format={fmt}",
                            headers=_auth(registered_user["tokens"]))
    _assert_download(resp, fmt)


@pytest.mark.asyncio
async def test_export_application_bad_format(client, db_session, mock_redis, registered_user):
    tmpl = await _make_template(db_session)
    create = await client.post("/v1/applications", json={
        "template_id": str(tmpl.id), "field_values": {}, "language": "en",
    }, headers=_auth(registered_user["tokens"]))
    app_id = create.json()["id"]
    resp = await client.get(f"/v1/applications/{app_id}/export?format=xls",
                            headers=_auth(registered_user["tokens"]))
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_export_application_other_user_404(client, db_session, mock_redis, registered_user):
    tmpl = await _make_template(db_session)
    create = await client.post("/v1/applications", json={
        "template_id": str(tmpl.id), "field_values": {}, "language": "en",
    }, headers=_auth(registered_user["tokens"]))
    app_id = create.json()["id"]

    other = await _register(client, "other")
    resp = await client.get(f"/v1/applications/{app_id}/export?format=pdf",
                            headers=_auth(other["tokens"]))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_export_approved_application_returns_signed_pdf(client, db_session, mock_redis, registered_user):
    tmpl = await _make_template(db_session)
    create = await client.post("/v1/applications", json={
        "template_id": str(tmpl.id), "field_values": {}, "language": "en",
    }, headers=_auth(registered_user["tokens"]))
    app_id = create.json()["id"]

    # Force-approve in the DB; the signed-PDF branch should still serve a PDF.
    await db_session.execute(
        update(Application).where(Application.id == uuid.UUID(app_id))
        .values(state=ApplicationState.approved, letter_body="Dear Sir, ...")
    )
    await db_session.commit()

    resp = await client.get(f"/v1/applications/{app_id}/export?format=pdf",
                            headers=_auth(registered_user["tokens"]))
    _assert_download(resp, "pdf")


# ── Filings ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize("fmt", ["pdf", "docx", "csv"])
async def test_export_filing_each_format(client, db_session, mock_redis, registered_user, fmt):
    from app.services.filing_svc import seed_templates
    await seed_templates(db_session)

    create = await client.post("/v1/filings", json={"template_key": "academic_rank1", "language": "en"},
                               headers=_auth(registered_user["tokens"]))
    assert create.status_code == 201, create.json()
    fid = create.json()["id"]
    await client.patch(f"/v1/filings/{fid}", json={"body": "Something happened in CSE-205 lab."},
                       headers=_auth(registered_user["tokens"]))

    resp = await client.get(f"/v1/filings/{fid}/export?format={fmt}",
                            headers=_auth(registered_user["tokens"]))
    _assert_download(resp, fmt)


@pytest.mark.asyncio
async def test_export_filing_other_user_404(client, db_session, mock_redis, registered_user):
    from app.services.filing_svc import seed_templates
    await seed_templates(db_session)
    create = await client.post("/v1/filings", json={"template_key": "academic_rank1", "language": "en"},
                               headers=_auth(registered_user["tokens"]))
    fid = create.json()["id"]

    other = await _register(client, "other")
    resp = await client.get(f"/v1/filings/{fid}/export?format=pdf", headers=_auth(other["tokens"]))
    assert resp.status_code == 404


# ── Routines ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize("fmt", ["pdf", "docx", "csv"])
async def test_export_routine_each_format(client, db_session, mock_redis, registered_user, fmt):
    admin = await _make_admin_tokens(client, db_session, registered_user["email"], registered_user["password"])
    create = await client.post("/v1/routines", json={
        "title": "CSE Spring 2026", "department": "CSE", "batch": "2022", "semester": "Spring 2026",
        "slots": [{"day": "Monday", "start_time": "09:00", "end_time": "10:30",
                   "course_code": "CSE-301", "course_name": "Algorithms", "room": "KT-601", "teacher": "Dr. Rahman"}],
    }, headers=_auth(admin))
    rid = create.json()["id"]
    await client.post(f"/v1/routines/{rid}/publish", headers=_auth(admin))

    resp = await client.get(f"/v1/routines/{rid}/export?format={fmt}")  # published → public
    _assert_download(resp, fmt)
    if fmt == "csv":
        assert b"CSE-301" in resp.content


@pytest.mark.asyncio
async def test_export_unpublished_routine_hidden_from_public(client, db_session, mock_redis, registered_user):
    admin = await _make_admin_tokens(client, db_session, registered_user["email"], registered_user["password"])
    create = await client.post("/v1/routines", json={"title": "Draft", "slots": []}, headers=_auth(admin))
    rid = create.json()["id"]
    resp = await client.get(f"/v1/routines/{rid}/export?format=pdf")
    assert resp.status_code == 404


# ── Notices ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize("fmt", ["pdf", "docx", "csv"])
async def test_export_notice_each_format(client, db_session, mock_redis, registered_user, fmt):
    admin = await _make_admin_tokens(client, db_session, registered_user["email"], registered_user["password"])
    create = await client.post("/v1/notices", json={
        "scope": "university", "title": "Exam Schedule", "body": "Finals start next week.",
    }, headers=_auth(admin))
    nid = create.json()["id"]
    await client.post(f"/v1/notices/{nid}/publish", headers=_auth(admin))

    resp = await client.get(f"/v1/notices/{nid}/export?format={fmt}")  # published → public
    _assert_download(resp, fmt)


@pytest.mark.asyncio
async def test_export_draft_notice_hidden_from_student(client, db_session, mock_redis, registered_user):
    admin = await _make_admin_tokens(client, db_session, registered_user["email"], registered_user["password"])
    create = await client.post("/v1/notices", json={
        "scope": "university", "title": "Secret", "body": "Not yet.",
    }, headers=_auth(admin))
    nid = create.json()["id"]

    # Student (non-admin) cannot export an unpublished notice.
    student = await _register(client, "stud")
    resp = await client.get(f"/v1/notices/{nid}/export?format=pdf", headers=_auth(student["tokens"]))
    assert resp.status_code == 404
