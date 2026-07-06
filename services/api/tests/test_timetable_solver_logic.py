"""Regression tests for the timetable-solver audit fixes.

Covers: soft constraints no longer enforced hard, penalty-based soft builders,
lock carry-over across re-solves, pin-failure surfacing, empty-data infeasible,
UNKNOWN→failed job mapping, entry-edit bounds validation, lab-group validator,
and the routine editor's interval-overlap conflict detection.

Run: .venv/Scripts/python.exe -m pytest -x -v tests/test_timetable_solver_logic.py
"""
from contextlib import asynccontextmanager

import pytest
from sqlalchemy import update

from app.models.user import User, Role, AccountStatus
from app.models.timetable import (
    TimetableTerm, TimetableScheduleConfig, TimetableCourse, TimetableBatch,
    TimetableSection, TimetableLabGroup, TimetableFacultyProfile, TimetableRoom,
    TimetableEntry, TimetableConstraint,
)
from app.schemas.timetable import EntryEdit, SolveRequest
from app.services import timetable_svc, timetable_solver
from app.services.timetable_solver import load_solver_data, solve, run_solve_job
from app.services.timetable_seed_data import seed_scenario
from app.services.routine_svc import validate_slots
from app.services.llm_json import extract_json_object


# ── Fixtures / helpers ────────────────────────────────────────────────────────

async def _make_admin(client, db_session, email, password):
    await db_session.execute(update(User).where(User.email == email).values(role="admin"))
    await db_session.commit()
    resp = await client.post("/auth/login", json={"identifier": email, "password": password})
    assert resp.status_code == 200, f"Re-login failed: {resp.json()}"
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture
async def admin_headers(client, registered_user, db_session):
    return await _make_admin(client, db_session, registered_user["email"], registered_user["password"])


def _session_factory(session):
    """Factory yielding the test session, shaped like AsyncSessionLocal."""
    @asynccontextmanager
    async def _cm():
        yield session
    return _cm


async def _seed_minimal_entry_graph(db):
    """Term + 2-day × 2-slot config + one theory entry (full FK graph)."""
    term = TimetableTerm(name="Mini Term", is_active=True)
    db.add(term)
    await db.flush()
    db.add(TimetableScheduleConfig(
        term_id=term.id, days=["Sat", "Sun"],
        slots=["8:30-10:00", "10:00-11:30"], off_days=[],
    ))
    course = TimetableCourse(code="SE101", name="Intro SE", credits=3, is_lab=False, weekly_classes=1)
    lab_course = TimetableCourse(code="SE102", name="Intro Lab", credits=1, is_lab=True, weekly_classes=1)
    batch = TimetableBatch(name="Batch 50", program="SWE")
    db.add_all([course, lab_course, batch])
    await db.flush()
    section = TimetableSection(batch_id=batch.id, name="A")
    db.add(section)
    await db.flush()
    lab_group = TimetableLabGroup(section_id=section.id, name="A1")
    user = User(
        full_name="Prof Mini", email="prof.mini@seed.test",
        password_hash="seed-no-login", role=Role.moderator,
        status=AccountStatus.active, email_verified=True,
    )
    db.add_all([lab_group, user])
    await db.flush()
    fp = TimetableFacultyProfile(user_id=user.id, rank="LECTURER", off_days=[], max_per_day=4, active=True)
    theory_room = TimetableRoom(name="R-101", room_type="THEORY", capacity=30)
    lab_room = TimetableRoom(name="L-201", room_type="LAB", capacity=30)
    db.add_all([fp, theory_room, lab_room])
    await db.flush()
    entry = TimetableEntry(
        term_id=term.id, result_version=1,
        course_id=course.id, section_id=section.id,
        faculty_id=fp.id, room_id=theory_room.id,
        day=0, slot=0, is_lab=False, locked=False, source="solver",
    )
    db.add(entry)
    await db.commit()
    return {
        "term_id": term.id, "course_id": course.id, "lab_course_id": lab_course.id,
        "section_id": section.id, "lab_group_id": lab_group.id,
        "faculty_id": fp.id, "theory_room_id": theory_room.id,
        "lab_room_id": lab_room.id, "entry_id": entry.id,
    }


# ── Soft vs hard constraint enforcement ───────────────────────────────────────

@pytest.mark.asyncio
async def test_soft_constraint_is_not_enforced_hard(db_session):
    """A soft max_classes_per_day with an impossible limit must not make the
    model infeasible — it becomes a penalty the solver can trade off."""
    info = await seed_scenario(db_session, n_batches=1, n_slots=8, eligible_per_course=4)
    db_session.add(TimetableConstraint(
        term_id=info["term_id"], constraint_type="max_classes_per_day",
        scope={}, params={"limit": 0}, enforcement="soft", weight=2, enabled=True,
    ))
    await db_session.commit()

    data = await load_solver_data(db_session, info["term_id"])
    result = solve(data, time_limit_s=30)
    assert result["status"] in ("optimal", "feasible"), result.get("infeasible_core")
    assert len(result["entries"]) == len(data.offerings)


@pytest.mark.asyncio
async def test_hard_constraint_still_enforced(db_session):
    """The same impossible limit as HARD must make the model infeasible and
    name the constraint in the infeasible core."""
    info = await seed_scenario(db_session, n_batches=1, n_slots=8, eligible_per_course=4)
    con = TimetableConstraint(
        term_id=info["term_id"], constraint_type="max_classes_per_day",
        scope={}, params={"limit": 0}, enforcement="hard", weight=None, enabled=True,
    )
    db_session.add(con)
    await db_session.commit()

    data = await load_solver_data(db_session, info["term_id"])
    result = solve(data, time_limit_s=30)
    assert result["status"] == "infeasible"
    assert str(con.id) in (result["infeasible_core"] or [])


# ── Lock carry-over & pin handling ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_locked_entry_survives_resolve_with_lock_flag(db_session):
    info = await seed_scenario(db_session, n_batches=1, n_slots=8, eligible_per_course=4)
    data = await load_solver_data(db_session, info["term_id"])
    result = solve(data, time_limit_s=30)
    assert result["status"] in ("optimal", "feasible")

    entries = [
        TimetableEntry(term_id=info["term_id"], result_version=1, **e)
        for e in result["entries"]
    ]
    entries[0].locked = True
    await timetable_svc.bulk_insert_entries(db_session, entries)

    base = await timetable_svc.list_entries(db_session, info["term_id"], 1)
    locked_base = next(e for e in base if e.locked)
    locked_ids = {locked_base.id}

    data2 = await load_solver_data(db_session, info["term_id"], seed_version=1)
    result2 = solve(data2, time_limit_s=30, locked_entry_ids=locked_ids, base_entries=base)
    assert result2["status"] in ("optimal", "feasible")

    # The locked class stays at its pinned coordinates AND keeps locked=True
    # in the new version, so a subsequent re-solve honors it again.
    matches = [
        e for e in result2["entries"]
        if e["course_id"] == locked_base.course_id
        and e["section_id"] == locked_base.section_id
        and e["lab_group_id"] == locked_base.lab_group_id
        and e["day"] == locked_base.day
        and e["slot"] == locked_base.slot
        and e["faculty_id"] == locked_base.faculty_id
    ]
    assert matches, "locked entry was moved by the re-solve"
    assert any(e["locked"] for e in matches), "locked flag was dropped in the new version"


@pytest.mark.asyncio
async def test_impossible_pin_fails_loudly(db_session):
    info = await seed_scenario(db_session, n_batches=1, n_slots=8, eligible_per_course=4)
    data = await load_solver_data(db_session, info["term_id"])
    result = solve(data, time_limit_s=30)
    entries = [
        TimetableEntry(term_id=info["term_id"], result_version=1, **e)
        for e in result["entries"]
    ]
    await timetable_svc.bulk_insert_entries(db_session, entries)
    base = await timetable_svc.list_entries(db_session, info["term_id"], 1)

    edit = EntryEdit(entry_id=base[0].id, new_slot=999)  # slot far out of range
    data2 = await load_solver_data(db_session, info["term_id"], seed_version=1)
    result2 = solve(data2, time_limit_s=10, pinned_change=edit, base_entries=base)
    assert result2["status"] == "infeasible"
    assert any(str(c).startswith("pin_impossible") for c in result2["infeasible_core"])


# ── Empty data & terminal status mapping ──────────────────────────────────────

@pytest.mark.asyncio
async def test_empty_data_reports_infeasible_not_feasible(db_session):
    term = TimetableTerm(name="Empty Term", is_active=True)
    db_session.add(term)
    await db_session.flush()
    db_session.add(TimetableScheduleConfig(
        term_id=term.id, days=["Sat"], slots=["8:30-10:00"], off_days=[],
    ))
    await db_session.commit()

    data = await load_solver_data(db_session, term.id)
    result = solve(data, time_limit_s=10)
    assert result["status"] == "infeasible"
    assert "no_offerings_for_term" in result["infeasible_core"]


@pytest.mark.asyncio
async def test_unknown_solver_status_maps_job_to_failed(db_session, monkeypatch):
    """CP-SAT UNKNOWN (time limit, no solution) must terminate the job as
    'failed' — clients poll only for optimal/feasible/infeasible/failed."""
    term = TimetableTerm(name="Stub Term", is_active=True)
    db_session.add(term)
    await db_session.flush()
    db_session.add(TimetableScheduleConfig(
        term_id=term.id, days=["Sat"], slots=["8:30-10:00"], off_days=[],
    ))
    await db_session.commit()

    monkeypatch.setattr(
        timetable_solver, "solve",
        lambda *a, **k: {"status": "unknown", "objective": None, "entries": [], "infeasible_core": []},
    )

    job = await timetable_svc.create_solve_job(db_session, term_id=term.id)
    await run_solve_job(job.id, _session_factory(db_session), SolveRequest(term_id=term.id, time_limit_s=10))

    job = await timetable_svc.get_solve_job(db_session, job.id)
    assert job.status == "failed"
    assert job.solver_status == "unknown"


# ── Entry-edit bounds + validator gaps (HTTP level) ───────────────────────────

@pytest.mark.asyncio
async def test_patch_entry_out_of_range_rejected(client, admin_headers, db_session):
    ids = await _seed_minimal_entry_graph(db_session)

    r = await client.patch(
        f"/v1/admin/timetable/entries/{ids['entry_id']}",
        json={"new_slot": 99}, headers=admin_headers,
    )
    assert r.status_code == 422, r.json()

    r = await client.patch(
        f"/v1/admin/timetable/entries/{ids['entry_id']}",
        json={"new_day": 5}, headers=admin_headers,  # config has 2 days
    )
    assert r.status_code == 422, r.json()

    r = await client.patch(
        f"/v1/admin/timetable/entries/{ids['entry_id']}",
        json={"new_slot": 1}, headers=admin_headers,
    )
    assert r.status_code == 200, r.json()
    assert r.json()["slot"] == 1


@pytest.mark.asyncio
async def test_entries_list_resolves_names(client, admin_headers, db_session):
    ids = await _seed_minimal_entry_graph(db_session)
    r = await client.get(
        f"/v1/admin/timetable/entries?term_id={ids['term_id']}&version=1",
        headers=admin_headers,
    )
    assert r.status_code == 200
    (e,) = r.json()
    assert e["course_code"] == "SE101"
    assert e["batch_name"] == "Batch 50"
    assert e["section_name"] == "A"
    assert e["faculty_name"] == "Prof Mini"
    assert e["room_name"] == "R-101"


@pytest.mark.asyncio
async def test_validate_flags_lab_group_double_booking(client, admin_headers, db_session):
    ids = await _seed_minimal_entry_graph(db_session)
    for room_id in (ids["lab_room_id"], ids["theory_room_id"]):
        db_session.add(TimetableEntry(
            term_id=ids["term_id"], result_version=1,
            course_id=ids["lab_course_id"], section_id=ids["section_id"],
            lab_group_id=ids["lab_group_id"], faculty_id=ids["faculty_id"],
            room_id=room_id, day=1, slot=1, is_lab=True, locked=False, source="manual",
        ))
    await db_session.commit()

    r = await client.get(
        f"/v1/admin/timetable/validate?term_id={ids['term_id']}&version=1",
        headers=admin_headers,
    )
    assert r.status_code == 200
    types = {c["conflict_type"] for c in r.json()["conflicts"]}
    assert "lab_group_overlap" in types
    # one of the two lab entries sits in a THEORY room — must be flagged too
    assert "room_type_mismatch" in types


# ── Routine editor: interval-overlap conflict detection ───────────────────────

def test_validate_slots_normalizes_time_formats():
    slots = [
        {"day": "Monday", "start_time": "08:30", "end_time": "10:00", "teacher": "Dr. A", "room": "R1"},
        {"day": "Monday", "start_time": "8:30", "end_time": "10:00", "teacher": "Dr. A", "room": "R2"},
    ]
    types = {c["type"] for c in validate_slots(slots)}
    assert "teacher_double_booked" in types
    assert "section_overlap" in types


def test_validate_slots_detects_partial_overlap():
    slots = [
        {"day": "Monday", "start_time": "8:30", "end_time": "10:00", "room": "KT-1"},
        {"day": "Monday", "start_time": "9:00", "end_time": "9:45", "room": "KT-1"},
    ]
    assert any(c["type"] == "room_double_booked" for c in validate_slots(slots))


def test_validate_slots_pm_heuristic_matches_24h():
    slots = [
        {"day": "Tuesday", "start_time": "1:00", "end_time": "2:30", "room": "KT-2"},
        {"day": "Tuesday", "start_time": "13:00", "end_time": "14:30", "room": "KT-2"},
    ]
    assert any(c["type"] == "room_double_booked" for c in validate_slots(slots))


def test_validate_slots_back_to_back_is_clean():
    slots = [
        {"day": "Monday", "start_time": "8:30", "end_time": "10:00", "teacher": "Dr. A", "room": "R1"},
        {"day": "Monday", "start_time": "10:00", "end_time": "11:30", "teacher": "Dr. A", "room": "R1"},
        {"day": "Tuesday", "start_time": "8:30", "end_time": "10:00", "teacher": "Dr. A", "room": "R1"},
    ]
    assert validate_slots(slots) == []


# ── LLM JSON extraction ───────────────────────────────────────────────────────

def test_extract_json_object_strips_think_blocks():
    raw = (
        '<think>Maybe {"wrong": true} — no, reconsidering…</think>\n'
        'Answer: {"target_index": 1, "changes": {"day": "Monday"}}'
    )
    obj = extract_json_object(raw)
    assert obj == {"target_index": 1, "changes": {"day": "Monday"}}


def test_extract_json_object_skips_unparseable_candidates():
    raw = "prose {not json} more prose {\"entry_id\": null, \"new_day\": 2} tail"
    obj = extract_json_object(raw)
    assert obj == {"entry_id": None, "new_day": 2}
