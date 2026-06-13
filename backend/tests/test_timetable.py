"""Integration tests for the timetable generator API.

Uses SQLite in-memory + fakeredis (no Docker needed).
Run: .venv/Scripts/python.exe -m pytest tests/test_timetable.py -x -v
"""
import uuid
import pytest
from sqlalchemy import update

from app.models.user import User


# ── Helper: elevate user to admin ────────────────────────────────────────────

async def _make_admin(client, db_session, email, password):
    await db_session.execute(update(User).where(User.email == email).values(role="admin"))
    await db_session.commit()
    resp = await client.post("/auth/login", json={"identifier": email, "password": password})
    assert resp.status_code == 200, f"Re-login failed: {resp.json()}"
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
async def admin_headers(client, registered_user, db_session):
    return await _make_admin(client, db_session, registered_user["email"], registered_user["password"])


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_term(client, admin_headers):
    resp = await client.post("/v1/admin/timetable/terms", json={"name": "Spring 2026"}, headers=admin_headers)
    assert resp.status_code == 201, resp.json()
    data = resp.json()
    assert data["name"] == "Spring 2026"
    assert "id" in data
    assert data["is_active"] is False


@pytest.mark.asyncio
async def test_list_terms(client, admin_headers):
    await client.post("/v1/admin/timetable/terms", json={"name": "Spring 2026"}, headers=admin_headers)
    await client.post("/v1/admin/timetable/terms", json={"name": "Summer 2026"}, headers=admin_headers)
    resp = await client.get("/v1/admin/timetable/terms", headers=admin_headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 2


@pytest.mark.asyncio
async def test_patch_term_set_active(client, admin_headers):
    r1 = await client.post("/v1/admin/timetable/terms", json={"name": "Spring 2026"}, headers=admin_headers)
    r2 = await client.post("/v1/admin/timetable/terms", json={"name": "Summer 2026"}, headers=admin_headers)
    term_id = r1.json()["id"]
    resp = await client.patch(f"/v1/admin/timetable/terms/{term_id}", json={"is_active": True}, headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["is_active"] is True


@pytest.mark.asyncio
async def test_create_batch(client, admin_headers):
    resp = await client.post(
        "/v1/admin/timetable/batches",
        json={"name": "Batch 41", "program": "SWE"},
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.json()
    assert resp.json()["name"] == "Batch 41"
    assert resp.json()["program"] == "SWE"


@pytest.mark.asyncio
async def test_generate_structure(client, admin_headers):
    batch_r = await client.post(
        "/v1/admin/timetable/batches",
        json={"name": "Batch 41", "program": "SWE"},
        headers=admin_headers,
    )
    batch_id = batch_r.json()["id"]
    resp = await client.post(
        f"/v1/admin/timetable/batches/{batch_id}/generate-structure",
        json={"count": 3, "lab_split": True},
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.json()
    assert resp.json()["created_sections"] == 3


@pytest.mark.asyncio
async def test_create_room(client, admin_headers):
    resp = await client.post(
        "/v1/admin/timetable/rooms",
        json={"name": "KT-504", "room_type": "THEORY", "capacity": 42},
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.json()
    assert resp.json()["room_type"] == "THEORY"


@pytest.mark.asyncio
async def test_room_type_validation(client, admin_headers):
    resp = await client.post(
        "/v1/admin/timetable/rooms",
        json={"name": "Bad", "room_type": "INVALID", "capacity": 10},
        headers=admin_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_course(client, admin_headers):
    resp = await client.post(
        "/v1/admin/timetable/courses",
        json={"code": "SE223", "name": "Algorithms", "credits": 3, "is_lab": False, "weekly_classes": 2},
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.json()
    assert resp.json()["code"] == "SE223"


@pytest.mark.asyncio
async def test_create_faculty_profile(client, admin_headers, registered_user):
    resp = await client.get("/auth/me", headers=admin_headers)
    user_id = resp.json()["id"]
    r = await client.post(
        "/v1/admin/timetable/faculty",
        json={"user_id": user_id, "rank": "ASSISTANT_PROF", "max_per_day": 3},
        headers=admin_headers,
    )
    assert r.status_code == 201, r.json()
    assert r.json()["rank"] == "ASSISTANT_PROF"


@pytest.mark.asyncio
async def test_create_constraint_and_toggle(client, admin_headers):
    term_r = await client.post(
        "/v1/admin/timetable/terms", json={"name": "Spring 2026"}, headers=admin_headers
    )
    term_id = term_r.json()["id"]

    resp = await client.post(
        "/v1/admin/timetable/constraints",
        json={
            "constraint_type": "max_classes_per_day",
            "scope": {},
            "params": {"limit": 4},
            "enforcement": "hard",
            "term_id": term_id,
        },
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.json()
    con_id = resp.json()["id"]
    assert resp.json()["enabled"] is True

    # Toggle disabled
    patch_r = await client.patch(
        f"/v1/admin/timetable/constraints/{con_id}",
        json={"enabled": False},
        headers=admin_headers,
    )
    assert patch_r.status_code == 200
    assert patch_r.json()["enabled"] is False


@pytest.mark.asyncio
async def test_create_offering(client, admin_headers):
    term_r = await client.post(
        "/v1/admin/timetable/terms", json={"name": "Spring 2026"}, headers=admin_headers
    )
    course_r = await client.post(
        "/v1/admin/timetable/courses",
        json={"code": "SE223", "name": "Algorithms", "credits": 3, "is_lab": False, "weekly_classes": 2},
        headers=admin_headers,
    )
    batch_r = await client.post(
        "/v1/admin/timetable/batches", json={"name": "Batch 41", "program": "SWE"}, headers=admin_headers
    )
    resp = await client.post(
        "/v1/admin/timetable/offerings",
        json={
            "term_id": term_r.json()["id"],
            "course_id": course_r.json()["id"],
            "batch_id": batch_r.json()["id"],
        },
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.json()


@pytest.mark.asyncio
async def test_create_eligibility(client, admin_headers, registered_user):
    me_r = await client.get("/auth/me", headers=admin_headers)
    user_id = me_r.json()["id"]
    fp_r = await client.post(
        "/v1/admin/timetable/faculty",
        json={"user_id": user_id, "rank": "LECTURER"},
        headers=admin_headers,
    )
    course_r = await client.post(
        "/v1/admin/timetable/courses",
        json={"code": "SE223", "name": "Algorithms", "credits": 3, "is_lab": False, "weekly_classes": 2},
        headers=admin_headers,
    )
    resp = await client.post(
        "/v1/admin/timetable/eligibility",
        json={"faculty_id": fp_r.json()["id"], "course_id": course_r.json()["id"]},
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.json()


@pytest.mark.asyncio
async def test_upsert_schedule_config(client, admin_headers):
    term_r = await client.post(
        "/v1/admin/timetable/terms", json={"name": "Spring 2026"}, headers=admin_headers
    )
    term_id = term_r.json()["id"]
    resp = await client.post(
        "/v1/admin/timetable/config",
        json={
            "term_id": term_id,
            "days": ["Sat", "Sun", "Mon", "Tue", "Wed", "Thu"],
            "slots": ["8:30-10:00", "10:00-11:30", "11:30-13:00", "14:00-15:30"],
            "off_days": [],
        },
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.json()
    assert resp.json()["days"] == ["Sat", "Sun", "Mon", "Tue", "Wed", "Thu"]

    # Second upsert updates, doesn't duplicate
    resp2 = await client.post(
        "/v1/admin/timetable/config",
        json={
            "term_id": term_id,
            "days": ["Sat", "Sun", "Mon"],
            "slots": ["8:30-10:00"],
            "off_days": [],
        },
        headers=admin_headers,
    )
    assert resp2.status_code == 200
    assert resp2.json()["days"] == ["Sat", "Sun", "Mon"]


@pytest.mark.asyncio
async def test_solve_job_queued_and_polled(client, admin_headers):
    term_r = await client.post(
        "/v1/admin/timetable/terms", json={"name": "Spring 2026"}, headers=admin_headers
    )
    term_id = term_r.json()["id"]
    # Upsert schedule config so solver doesn't fail on load
    await client.post(
        "/v1/admin/timetable/config",
        json={
            "term_id": term_id,
            "days": ["Sat", "Sun", "Mon", "Tue", "Wed"],
            "slots": ["8:30-10:00", "10:00-11:30"],
            "off_days": [],
        },
        headers=admin_headers,
    )

    resp = await client.post(
        "/v1/admin/timetable/solve",
        json={"term_id": term_id, "time_limit_s": 10},
        headers=admin_headers,
    )
    assert resp.status_code == 202, resp.json()
    job_id = resp.json()["job_id"]
    assert resp.json()["status"] in ("queued", "running", "optimal", "feasible", "failed")

    # Poll
    poll = await client.get(f"/v1/admin/timetable/solve/{job_id}", headers=admin_headers)
    assert poll.status_code == 200
    assert poll.json()["status"] in ("queued", "running", "optimal", "feasible", "failed")


@pytest.mark.asyncio
async def test_validate_no_entries_returns_empty(client, admin_headers):
    term_r = await client.post(
        "/v1/admin/timetable/terms", json={"name": "Spring 2026"}, headers=admin_headers
    )
    term_id = term_r.json()["id"]
    resp = await client.get(
        f"/v1/admin/timetable/validate?term_id={term_id}&version=1",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["conflicts"] == []
    assert resp.json()["hard_count"] == 0


@pytest.mark.asyncio
async def test_entries_list_empty_for_new_term(client, admin_headers):
    term_r = await client.post(
        "/v1/admin/timetable/terms", json={"name": "Spring 2026"}, headers=admin_headers
    )
    term_id = term_r.json()["id"]
    resp = await client.get(
        f"/v1/admin/timetable/entries?term_id={term_id}&version=1",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_publish_fails_without_entries(client, admin_headers):
    term_r = await client.post(
        "/v1/admin/timetable/terms", json={"name": "Spring 2026"}, headers=admin_headers
    )
    term_id = term_r.json()["id"]
    await client.post(
        "/v1/admin/timetable/config",
        json={
            "term_id": term_id,
            "days": ["Sat", "Sun"],
            "slots": ["8:30-10:00"],
            "off_days": [],
        },
        headers=admin_headers,
    )
    resp = await client.post(
        "/v1/admin/timetable/publish",
        json={"term_id": term_id, "version": 1},
        headers=admin_headers,
    )
    # Expect 409 (no entries or no config after validate)
    assert resp.status_code in (409,)


@pytest.mark.asyncio
async def test_unauthorized_returns_401(client):
    resp = await client.get("/v1/admin/timetable/terms")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_student_cannot_access_timetable_admin(client, registered_user):
    login = await client.post("/auth/login", json={
        "identifier": registered_user["email"],
        "password": registered_user["password"],
    })
    student_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    resp = await client.get("/v1/admin/timetable/terms", headers=student_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_term_without_jobs(client, admin_headers):
    r = await client.post(
        "/v1/admin/timetable/terms", json={"name": "Spring 2026"}, headers=admin_headers
    )
    term_id = r.json()["id"]
    del_r = await client.delete(f"/v1/admin/timetable/terms/{term_id}", headers=admin_headers)
    assert del_r.status_code == 204


# ── End-to-end: publish projects to /v1/routines ─────────────────────────────

@pytest.mark.asyncio
async def test_publish_creates_routine_visible_to_students(client, admin_headers, db_session, registered_user):
    """Full pipeline: seed entries → publish → GET /v1/routines shows correct slots."""
    from sqlalchemy import insert
    from app.models.timetable import (
        TimetableTerm, TimetableBatch, TimetableSection,
        TimetableRoom, TimetableCourse, TimetableFacultyProfile,
        TimetableScheduleConfig, TimetableEntry,
    )
    from app.models.user import User

    # Resolve admin user id
    me = await client.get("/auth/me", headers=admin_headers)
    admin_id = me.json()["id"]

    # ── 1. Create master data directly in DB (faster than API round-trips) ──

    term = TimetableTerm(name="Spring 2026")
    db_session.add(term)
    await db_session.flush()

    batch = TimetableBatch(name="Batch 41", program="SWE")
    db_session.add(batch)
    await db_session.flush()

    section = TimetableSection(batch_id=batch.id, name="A")
    db_session.add(section)
    await db_session.flush()

    room = TimetableRoom(name="KT-504", room_type="THEORY", capacity=40)
    db_session.add(room)
    await db_session.flush()

    course = TimetableCourse(code="SE223", name="Algorithms", credits=3, is_lab=False, weekly_classes=2)
    db_session.add(course)
    await db_session.flush()

    import uuid as _uuid
    admin_uuid = _uuid.UUID(admin_id)
    fp = TimetableFacultyProfile(user_id=admin_uuid, rank="LECTURER", max_per_day=4)
    db_session.add(fp)
    await db_session.flush()

    cfg = TimetableScheduleConfig(
        term_id=term.id,
        days=["Sat", "Sun", "Mon", "Tue", "Wed", "Thu"],
        slots=["8:30-10:00", "10:00-11:30", "11:30-13:00"],
        off_days=[],
    )
    db_session.add(cfg)
    await db_session.flush()

    # Two entries for section A: day 0 slot 0 and day 1 slot 1
    entry1 = TimetableEntry(
        term_id=term.id, result_version=1,
        course_id=course.id, section_id=section.id,
        faculty_id=fp.id, room_id=room.id,
        day=0, slot=0, is_lab=False,
    )
    entry2 = TimetableEntry(
        term_id=term.id, result_version=1,
        course_id=course.id, section_id=section.id,
        faculty_id=fp.id, room_id=room.id,
        day=1, slot=1, is_lab=False,
    )
    db_session.add(entry1)
    db_session.add(entry2)
    await db_session.commit()

    # ── 2. Validate — should be clean (no conflicts; same room/faculty but different day+slot) ──
    val = await client.get(
        f"/v1/admin/timetable/validate?term_id={term.id}&version=1",
        headers=admin_headers,
    )
    assert val.status_code == 200, val.json()
    assert val.json()["hard_count"] == 0, val.json()["conflicts"]

    # ── 3. Publish ──
    pub = await client.post(
        "/v1/admin/timetable/publish",
        json={"term_id": str(term.id), "version": 1},
        headers=admin_headers,
    )
    assert pub.status_code == 200, pub.json()
    result = pub.json()
    assert result["published_routines"] == 1  # one section → one AcademicRoutine

    # ── 4. Verify routine is visible via student-facing API ──
    routines = await client.get("/v1/routines?department=SWE&semester=Spring+2026")
    assert routines.status_code == 200, routines.json()
    data = routines.json()
    assert len(data) >= 1

    # Find the one we just published
    our_routine = next(
        (r for r in data if r["batch"] == "Batch 41 (A)" and r["semester"] == "Spring 2026"),
        None,
    )
    assert our_routine is not None, f"Expected 'Batch 41 (A)' in {[r['batch'] for r in data]}"
    assert our_routine["status"] == "published"

    # Check slot content
    slots = our_routine["slots"]
    assert len(slots) == 2
    days_seen = {s["day"] for s in slots}
    assert "Sat" in days_seen  # entry1: day 0 = Sat
    assert "Sun" in days_seen  # entry2: day 1 = Sun

    # Verify time parsing from "8:30-10:00"
    sat_slot = next(s for s in slots if s["day"] == "Sat")
    assert sat_slot["start_time"] == "8:30"
    assert sat_slot["end_time"] == "10:00"
    assert sat_slot["course_code"] == "SE223"
    assert sat_slot["room"] == "KT-504"


@pytest.mark.asyncio
async def test_publish_multiple_sections_each_get_own_routine(client, admin_headers, db_session):
    """Sections A and B of the same batch must each produce a separate AcademicRoutine."""
    from app.models.timetable import (
        TimetableTerm, TimetableBatch, TimetableSection,
        TimetableRoom, TimetableCourse, TimetableFacultyProfile,
        TimetableScheduleConfig, TimetableEntry,
    )
    import uuid as _uuid

    me = await client.get("/auth/me", headers=admin_headers)
    admin_uuid = _uuid.UUID(me.json()["id"])

    term = TimetableTerm(name="Summer 2026")
    batch = TimetableBatch(name="Batch 42", program="CSE")
    db_session.add(term); db_session.add(batch)
    await db_session.flush()

    sec_a = TimetableSection(batch_id=batch.id, name="A")
    sec_b = TimetableSection(batch_id=batch.id, name="B")
    db_session.add(sec_a); db_session.add(sec_b)
    await db_session.flush()

    room = TimetableRoom(name="AB1-201", room_type="THEORY", capacity=35)
    course = TimetableCourse(code="CS101", name="Programming", credits=3, is_lab=False, weekly_classes=2)
    fp = TimetableFacultyProfile(user_id=admin_uuid, rank="LECTURER", max_per_day=4)
    db_session.add(room); db_session.add(course); db_session.add(fp)
    await db_session.flush()

    cfg = TimetableScheduleConfig(
        term_id=term.id,
        days=["Sat", "Sun", "Mon"],
        slots=["8:30-10:00", "10:00-11:30"],
        off_days=[],
    )
    db_session.add(cfg)
    await db_session.flush()

    # Section A: day 0 slot 0
    db_session.add(TimetableEntry(
        term_id=term.id, result_version=1,
        course_id=course.id, section_id=sec_a.id,
        faculty_id=fp.id, room_id=room.id,
        day=0, slot=0, is_lab=False,
    ))
    # Section B: day 1 slot 0 (different day → no overlap on room/faculty)
    db_session.add(TimetableEntry(
        term_id=term.id, result_version=1,
        course_id=course.id, section_id=sec_b.id,
        faculty_id=fp.id, room_id=room.id,
        day=1, slot=0, is_lab=False,
    ))
    await db_session.commit()

    pub = await client.post(
        "/v1/admin/timetable/publish",
        json={"term_id": str(term.id), "version": 1},
        headers=admin_headers,
    )
    assert pub.status_code == 200, pub.json()
    assert pub.json()["published_routines"] == 2  # two sections → two routines

    # Both sections visible via student API
    routines = await client.get("/v1/routines?department=CSE&semester=Summer+2026")
    assert routines.status_code == 200
    batches = {r["batch"] for r in routines.json()}
    assert "Batch 42 (A)" in batches
    assert "Batch 42 (B)" in batches

    # Re-publishing same version overwrites (upsert) — no duplicate rows
    pub2 = await client.post(
        "/v1/admin/timetable/publish",
        json={"term_id": str(term.id), "version": 1},
        headers=admin_headers,
    )
    assert pub2.status_code == 200
    routines2 = await client.get("/v1/routines?department=CSE&semester=Summer+2026")
    count = len([r for r in routines2.json() if r["semester"] == "Summer 2026"])
    assert count == 2  # still exactly 2, not 4
