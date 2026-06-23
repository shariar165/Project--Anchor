"""
Tests for the Routine Builder editing surface — XLSX export, Excel/CSV import
(round-trip), slot conflict validation, and the AI-edit contract.

SQLite in-memory + fakeredis — no Docker required.
"""
import uuid
import pytest
from sqlalchemy import update

from app.models.user import User
from app.services import routine_svc


XLSX_CT = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _auth(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def _make_admin_tokens(client, db_session, email: str, password: str) -> dict:
    await db_session.execute(update(User).where(User.email == email).values(role="admin"))
    await db_session.commit()
    resp = await client.post("/auth/login", json={"identifier": email, "password": password})
    assert resp.status_code == 200, resp.json()
    return resp.json()


async def _create_routine(client, admin, slots):
    resp = await client.post("/v1/routines", json={
        "title": "CSE Spring 2026", "department": "CSE", "batch": "2022 (A)",
        "semester": "Spring 2026", "slots": slots,
    }, headers=_auth(admin))
    assert resp.status_code == 201, resp.json()
    return resp.json()


_SLOTS = [
    {"day": "Monday", "start_time": "09:00", "end_time": "10:30",
     "course_code": "CSE-301", "course_name": "Algorithms", "room": "KT-601", "teacher": "Dr. Rahman"},
    {"day": "Tuesday", "start_time": "11:00", "end_time": "12:30",
     "course_code": "CSE-302", "course_name": "Operating Systems", "room": "KT-602", "teacher": "Dr. Karim"},
]


# ── XLSX export ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_export_routine_xlsx(client, db_session, mock_redis, registered_user):
    admin = await _make_admin_tokens(client, db_session, registered_user["email"], registered_user["password"])
    routine = await _create_routine(client, admin, _SLOTS)
    await client.post(f"/v1/routines/{routine['id']}/publish", headers=_auth(admin))

    resp = await client.get(f"/v1/routines/{routine['id']}/export?format=xlsx")  # published → public
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith(XLSX_CT)
    assert ".xlsx" in resp.headers.get("content-disposition", "")
    assert resp.content[:2] == b"PK"  # xlsx is a zip


# ── Excel/CSV import ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_import_routine_csv_replaces_slots(client, db_session, mock_redis, registered_user):
    admin = await _make_admin_tokens(client, db_session, registered_user["email"], registered_user["password"])
    routine = await _create_routine(client, admin, [])  # start empty

    csv_bytes = (
        b"Day,Time,Course,Name,Room,Teacher\r\n"
        b"Monday,09:00-10:30,CSE-301,Algorithms,KT-601,Dr. Rahman\r\n"
        b"Tuesday,11:00-12:30,CSE-302,Operating Systems,KT-602,Dr. Karim\r\n"
    )
    resp = await client.post(
        f"/v1/routines/{routine['id']}/import",
        files={"file": ("routine.csv", csv_bytes, "text/csv")},
        headers=_auth(admin),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["imported"] == 2
    assert body["routine"]["status"] == "draft"

    got = await client.get(f"/v1/routines/{routine['id']}", headers=_auth(admin))
    slots = got.json()["slots"]
    assert len(slots) == 2
    assert slots[0]["course_code"] == "CSE-301"
    assert slots[0]["start_time"] == "09:00" and slots[0]["end_time"] == "10:30"


@pytest.mark.asyncio
async def test_export_then_import_xlsx_round_trip(client, db_session, mock_redis, registered_user):
    admin = await _make_admin_tokens(client, db_session, registered_user["email"], registered_user["password"])
    routine = await _create_routine(client, admin, _SLOTS)

    # Admin can export a draft via the optional-auth export endpoint.
    exported = await client.get(f"/v1/routines/{routine['id']}/export?format=xlsx", headers=_auth(admin))
    assert exported.status_code == 200, exported.text

    reimport = await client.post(
        f"/v1/routines/{routine['id']}/import",
        files={"file": ("routine.xlsx", exported.content, XLSX_CT)},
        headers=_auth(admin),
    )
    assert reimport.status_code == 200, reimport.text
    assert reimport.json()["imported"] == len(_SLOTS)


@pytest.mark.asyncio
async def test_import_requires_admin(client, db_session, mock_redis, registered_user):
    # Owner creates as admin, then a plain user is rejected.
    admin = await _make_admin_tokens(client, db_session, registered_user["email"], registered_user["password"])
    routine = await _create_routine(client, admin, [])
    # Demote back to a normal user and re-login.
    await db_session.execute(update(User).where(User.email == registered_user["email"]).values(role="user"))
    await db_session.commit()
    relog = await client.post("/auth/login", json={
        "identifier": registered_user["email"], "password": registered_user["password"]})
    user_tokens = relog.json()

    resp = await client.post(
        f"/v1/routines/{routine['id']}/import",
        files={"file": ("routine.csv", b"Day,Time\nMonday,09:00", "text/csv")},
        headers=_auth(user_tokens),
    )
    assert resp.status_code in (401, 403)


# ── Validation ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_validate_detects_teacher_clash(client, db_session, mock_redis, registered_user):
    admin = await _make_admin_tokens(client, db_session, registered_user["email"], registered_user["password"])
    clashing = [
        {"day": "Monday", "start_time": "09:00", "end_time": "10:30",
         "course_code": "CSE-301", "room": "R1", "teacher": "Dr. X"},
        {"day": "Monday", "start_time": "09:00", "end_time": "10:30",
         "course_code": "CSE-302", "room": "R2", "teacher": "Dr. X"},
    ]
    routine = await _create_routine(client, admin, clashing)
    resp = await client.get(f"/v1/routines/{routine['id']}/validate", headers=_auth(admin))
    assert resp.status_code == 200, resp.text
    types = {c["type"] for c in resp.json()["conflicts"]}
    assert "teacher_double_booked" in types
    assert "section_overlap" in types


def test_validate_slots_clean():
    # Pure-function path: distinct teachers/rooms/times → no conflicts.
    assert routine_svc.validate_slots(_SLOTS) == []


# ── AI edit contract (works whether or not Ollama is reachable) ────────────────

@pytest.mark.asyncio
async def test_ai_edit_returns_contract(client, db_session, mock_redis, registered_user):
    admin = await _make_admin_tokens(client, db_session, registered_user["email"], registered_user["password"])
    routine = await _create_routine(client, admin, _SLOTS)
    resp = await client.post(
        f"/v1/routines/{routine['id']}/ai-edit",
        json={"text": "move CSE-301 to Wednesday 10:00"},
        headers=_auth(admin),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert isinstance(body.get("ok"), bool)
    if body["ok"]:
        assert isinstance(body["new_slots"], list)
        assert body.get("summary")
    else:
        assert body.get("reason")


@pytest.mark.asyncio
async def test_ai_edit_offline_returns_reason(client, db_session, mock_redis, registered_user, monkeypatch):
    # Force the Ollama base URL to a dead port so the graceful-offline path runs.
    from app.config import get_settings
    settings = get_settings()
    monkeypatch.setattr(settings, "ollama_base_url", "http://127.0.0.1:1", raising=False)

    admin = await _make_admin_tokens(client, db_session, registered_user["email"], registered_user["password"])
    routine = await _create_routine(client, admin, _SLOTS)
    resp = await client.post(
        f"/v1/routines/{routine['id']}/ai-edit",
        json={"text": "move CSE-301 to Wednesday 10:00"},
        headers=_auth(admin),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is False
    assert "offline" in body["reason"].lower()
