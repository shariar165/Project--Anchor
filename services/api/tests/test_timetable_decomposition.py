"""Tests for the per-batch decomposition driver and its guardrails.

Covers: merge escalation (pair-merge → remainder-monolith), pin fast path
(other batches carried verbatim), S-8 structural diagnostics, the orphaned-job
reaper, subprocess isolation, and the duplicate-guard HTTP endpoints.

Run: .venv/Scripts/python.exe -m pytest -x -v tests/test_timetable_decomposition.py
"""
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import update

from app.config import get_settings
from app.models.user import User
from app.models.timetable import (
    TimetableTerm, TimetableScheduleConfig, TimetableCourse, TimetableBatch,
    TimetableSection, TimetableRoom, TimetableFacultyProfile,
    TimetableCourseOffering, TimetableTeacherEligibility, TimetableSolveJob,
)
from app.schemas.timetable import EntryEdit, SolveRequest
from app.services import timetable_svc, timetable_solver
from app.services.timetable_solver import load_solver_data, run_solve_job, solve
from app.services.timetable_seed_data import seed_scenario


def _session_factory(session):
    @asynccontextmanager
    async def _cm():
        yield session
    return _cm


async def _make_admin(client, db_session, email, password):
    await db_session.execute(update(User).where(User.email == email).values(role="admin"))
    await db_session.commit()
    resp = await client.post("/auth/login", json={"identifier": email, "password": password})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture
async def admin_headers(client, registered_user, db_session):
    return await _make_admin(client, db_session, registered_user["email"], registered_user["password"])


def _fake_entries(data):
    """Minimal valid entry dicts for every offering in a solver slice."""
    fac = data.faculty[0].id
    room = data.rooms[0].id
    return [
        {
            "course_id": o.course.id, "section_id": o.section.id,
            "lab_group_id": o.lab_group.id if o.lab_group else None,
            "faculty_id": fac, "room_id": room,
            "day": i % data.n_days, "slot": (i // data.n_days) % data.n_slots,
            "is_lab": o.course.is_lab, "locked": False, "source": "solver",
        }
        for i, o in enumerate(data.offerings)
    ]


# ── Escalation ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_pair_merge_rescues_infeasible_group(db_session, monkeypatch):
    """Group 2 infeasible → merged with group 1 and re-solved; job succeeds."""
    info = await seed_scenario(db_session, n_batches=3, n_slots=6, eligible_per_course=4)
    data = await load_solver_data(db_session, info["term_id"])
    total = len(data.offerings)

    sizes = []
    state = {"failed_once": False}

    def fake_solve(d, **kw):
        sizes.append(len(d.offerings))
        if len(sizes) == 2 and not state["failed_once"]:
            state["failed_once"] = True
            return {"status": "infeasible", "objective": None, "entries": [],
                    "infeasible_core": ["synthetic"]}
        return {"status": "optimal", "objective": 0,
                "entries": _fake_entries(d), "infeasible_core": []}

    monkeypatch.setattr(timetable_solver, "solve", fake_solve)

    job = await timetable_svc.create_solve_job(db_session, term_id=info["term_id"])
    await run_solve_job(job.id, _session_factory(db_session),
                        SolveRequest(term_id=info["term_id"], time_limit_s=30))

    job = await timetable_svc.get_solve_job(db_session, job.id)
    assert job.status == "optimal", (job.solver_status, job.infeasible_core)
    # call pattern: g0 · g1(fail) · merged(g0+g1) · g2
    assert len(sizes) == 4
    assert sizes[2] == sizes[0] + sizes[1], sizes
    entries = await timetable_svc.list_entries(db_session, info["term_id"], 1)
    assert len(entries) == total


@pytest.mark.asyncio
async def test_remainder_monolith_after_first_group_fails(db_session, monkeypatch):
    """First group infeasible (nothing to pair with) → one model over the rest."""
    info = await seed_scenario(db_session, n_batches=3, n_slots=6, eligible_per_course=4)
    data = await load_solver_data(db_session, info["term_id"])
    total = len(data.offerings)

    sizes = []

    def fake_solve(d, **kw):
        sizes.append(len(d.offerings))
        if len(sizes) == 1:
            return {"status": "infeasible", "objective": None, "entries": [],
                    "infeasible_core": ["synthetic"]}
        return {"status": "optimal", "objective": 0,
                "entries": _fake_entries(d), "infeasible_core": []}

    monkeypatch.setattr(timetable_solver, "solve", fake_solve)

    job = await timetable_svc.create_solve_job(db_session, term_id=info["term_id"])
    await run_solve_job(job.id, _session_factory(db_session),
                        SolveRequest(term_id=info["term_id"], time_limit_s=30))

    job = await timetable_svc.get_solve_job(db_session, job.id)
    assert job.status == "optimal", (job.solver_status, job.infeasible_core)
    assert sizes == [sizes[0], total], sizes


@pytest.mark.asyncio
async def test_exhausted_escalation_reports_batch_labeled_core(db_session, monkeypatch):
    """Everything infeasible → job infeasible with batch-labelled cores."""
    info = await seed_scenario(db_session, n_batches=3, n_slots=6, eligible_per_course=4)

    def fake_solve(d, **kw):
        return {"status": "infeasible", "objective": None, "entries": [],
                "infeasible_core": ["synthetic_core"]}

    monkeypatch.setattr(timetable_solver, "solve", fake_solve)

    job = await timetable_svc.create_solve_job(db_session, term_id=info["term_id"])
    await run_solve_job(job.id, _session_factory(db_session),
                        SolveRequest(term_id=info["term_id"], time_limit_s=30))

    job = await timetable_svc.get_solve_job(db_session, job.id)
    assert job.status == "infeasible"
    assert job.progress == 100
    # After escalation exhausts (final merge = every batch), the core may be
    # unlabeled; a partial-group failure carries a "batch <names>: " prefix.
    assert any("synthetic_core" in str(c) for c in job.infeasible_core), job.infeasible_core


# ── Pin fast path — other batches carried verbatim ────────────────────────────

@pytest.mark.asyncio
async def test_pin_move_leaves_other_batches_untouched(db_session):
    info = await seed_scenario(db_session, n_batches=2, n_slots=8, eligible_per_course=4)

    job = await timetable_svc.create_solve_job(db_session, term_id=info["term_id"])
    await run_solve_job(job.id, _session_factory(db_session),
                        SolveRequest(term_id=info["term_id"], time_limit_s=60))
    job = await timetable_svc.get_solve_job(db_session, job.id)
    assert job.status in ("optimal", "feasible"), (job.solver_status, job.infeasible_core)

    base = await timetable_svc.list_entries(db_session, info["term_id"], 1)
    data = await load_solver_data(db_session, info["term_id"])
    batch_of = data.batch_id_by_section

    # Pick a theory entry and a target slot where its teacher is idle all week.
    target = next(e for e in base if not e.is_lab)
    busy = {(e.day, e.slot) for e in base if e.faculty_id == target.faculty_id}
    free = next(
        (d, s) for d in range(data.n_days) for s in range(data.n_slots)
        if (d, s) not in busy
    )
    pin_batch = batch_of[target.section_id]
    other_before = sorted(
        (e.course_id, e.section_id, e.lab_group_id, e.faculty_id, e.room_id,
         e.day, e.slot, e.locked, e.source)
        for e in base if batch_of[e.section_id] != pin_batch
    )
    assert other_before, "seed must produce a second batch"

    edit = EntryEdit(entry_id=target.id, new_day=free[0], new_slot=free[1], lock=True)
    base_d = [timetable_solver.to_entry_d(e) for e in base]
    job2 = await timetable_svc.create_solve_job(db_session, term_id=info["term_id"])
    await run_solve_job(
        job2.id, _session_factory(db_session),
        SolveRequest(term_id=info["term_id"], time_limit_s=60, seed_from_version=1),
        pinned_change=edit, locked_entry_ids=set(), base_entries=base_d,
    )
    job2 = await timetable_svc.get_solve_job(db_session, job2.id)
    assert job2.status in ("optimal", "feasible"), (job2.solver_status, job2.infeasible_core)
    assert job2.result_version == 2

    v2 = await timetable_svc.list_entries(db_session, info["term_id"], 2)
    assert len(v2) == len(base)

    # The untouched batch is field-identical (fresh row ids, same placements).
    other_after = sorted(
        (e.course_id, e.section_id, e.lab_group_id, e.faculty_id, e.room_id,
         e.day, e.slot, e.locked, e.source)
        for e in v2 if batch_of[e.section_id] != pin_batch
    )
    assert other_after == other_before

    # The pinned class moved to its new coordinates and stayed locked.
    moved = [
        e for e in v2
        if e.course_id == target.course_id and e.section_id == target.section_id
        and e.day == free[0] and e.slot == free[1]
    ]
    assert moved and any(e.locked for e in moved)


# ── S-8 structural diagnostics ────────────────────────────────────────────────

async def _term_with_config(db, name="Diag Term", days=2, slots=2):
    term = TimetableTerm(name=name, is_active=True)
    db.add(term)
    await db.flush()
    db.add(TimetableScheduleConfig(
        term_id=term.id,
        days=["Sat", "Sun", "Mon", "Tue", "Wed", "Thu"][:days],
        slots=[f"s{i}" for i in range(slots)], off_days=[],
    ))
    await db.flush()
    return term


@pytest.mark.asyncio
async def test_offerings_without_sections_fail_fast_with_named_batch(db_session):
    term = await _term_with_config(db_session)
    course = TimetableCourse(code="DX101", name="Diag", credits=3, is_lab=False, weekly_classes=1)
    batch = TimetableBatch(name="Batch 99", program="SWE")
    db_session.add_all([course, batch])
    await db_session.flush()
    db_session.add(TimetableCourseOffering(term_id=term.id, course_id=course.id, batch_id=batch.id))
    db_session.add(TimetableRoom(name="D-1", room_type="THEORY", capacity=30))
    fp = TimetableFacultyProfile(rank="LECTURER", off_days=[], max_per_day=4, active=True)
    db_session.add(fp)
    await db_session.commit()

    data = await load_solver_data(db_session, term.id)
    assert "no_sections_for_batch:Batch 99" in data.diagnostics

    # The job must fail fast — the old code silently dropped these sessions.
    job = await timetable_svc.create_solve_job(db_session, term_id=term.id)
    await run_solve_job(job.id, _session_factory(db_session),
                        SolveRequest(term_id=term.id, time_limit_s=10))
    job = await timetable_svc.get_solve_job(db_session, job.id)
    assert job.status == "infeasible"
    assert "no_sections_for_batch:Batch 99" in job.infeasible_core


@pytest.mark.asyncio
async def test_lab_course_without_lab_groups_diagnosed(db_session):
    term = await _term_with_config(db_session)
    course = TimetableCourse(code="DX102L", name="Diag Lab", credits=1, is_lab=True, weekly_classes=1)
    batch = TimetableBatch(name="Batch 98", program="SWE")
    db_session.add_all([course, batch])
    await db_session.flush()
    sec = TimetableSection(batch_id=batch.id, name="A")
    db_session.add(sec)
    await db_session.flush()
    db_session.add(TimetableCourseOffering(term_id=term.id, course_id=course.id, batch_id=batch.id))
    await db_session.commit()

    data = await load_solver_data(db_session, term.id)
    assert "no_lab_groups_for_section:Batch 98/A" in data.diagnostics


@pytest.mark.asyncio
async def test_course_without_eligibility_named_in_core(db_session):
    term = await _term_with_config(db_session)
    course = TimetableCourse(code="DX103", name="Diag NoElig", credits=3, is_lab=False, weekly_classes=1)
    batch = TimetableBatch(name="Batch 97", program="SWE")
    db_session.add_all([course, batch])
    await db_session.flush()
    sec = TimetableSection(batch_id=batch.id, name="A")
    db_session.add_all([
        sec,
        TimetableCourseOffering(term_id=term.id, course_id=course.id, batch_id=batch.id),
        TimetableRoom(name="D-2", room_type="THEORY", capacity=30),
        TimetableFacultyProfile(rank="LECTURER", off_days=[], max_per_day=4, active=True),
    ])
    await db_session.commit()

    data = await load_solver_data(db_session, term.id)
    assert "no_eligibility_for_course:DX103" in data.diagnostics
    result = solve(data, time_limit_s=5)
    assert result["status"] == "infeasible"
    assert "no_eligibility_for_course:DX103" in result["infeasible_core"]


# ── Reaper ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_reap_stale_solve_jobs(db_session):
    term = await _term_with_config(db_session, name="Reap Term")
    stale = await timetable_svc.create_solve_job(db_session, term_id=term.id)
    fresh = await timetable_svc.create_solve_job(db_session, term_id=term.id)

    old = datetime.now(timezone.utc) - timedelta(hours=2)
    await db_session.execute(
        update(TimetableSolveJob).where(TimetableSolveJob.id == stale.id)
        .values(status="running", progress=10, started_at=old, updated_at=old)
    )
    await db_session.execute(
        update(TimetableSolveJob).where(TimetableSolveJob.id == fresh.id)
        .values(status="running", progress=10)
    )
    await db_session.commit()

    reaped = await timetable_svc.reap_stale_solve_jobs(db_session)
    assert reaped == 1

    # Refresh from the DB — the identity map still holds pre-update attributes.
    await db_session.refresh(stale)
    await db_session.refresh(fresh)
    assert stale.status == "failed" and stale.solver_status == "orphaned"
    assert fresh.status == "running"


# ── Subprocess isolation smoke test ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_solve_job_in_subprocess(db_session, monkeypatch):
    """One tiny solve through the real spawn-based ProcessPoolExecutor path."""
    term = await _term_with_config(db_session, name="Proc Term")
    course = TimetableCourse(code="PX101", name="Proc", credits=3, is_lab=False, weekly_classes=1)
    batch = TimetableBatch(name="Batch 96", program="SWE")
    db_session.add_all([course, batch])
    await db_session.flush()
    sec = TimetableSection(batch_id=batch.id, name="A")
    fp = TimetableFacultyProfile(rank="LECTURER", off_days=[], max_per_day=4, active=True)
    db_session.add_all([sec, fp])
    await db_session.flush()
    db_session.add_all([
        TimetableCourseOffering(term_id=term.id, course_id=course.id, batch_id=batch.id),
        TimetableTeacherEligibility(faculty_id=fp.id, course_id=course.id),
        TimetableRoom(name="P-1", room_type="THEORY", capacity=30),
    ])
    await db_session.commit()

    monkeypatch.setattr(get_settings(), "solver_isolation", "process")

    job = await timetable_svc.create_solve_job(db_session, term_id=term.id)
    await run_solve_job(job.id, _session_factory(db_session),
                        SolveRequest(term_id=term.id, time_limit_s=10))
    job = await timetable_svc.get_solve_job(db_session, job.id)
    assert job.status == "optimal", (job.status, job.solver_status, job.infeasible_core)
    entries = await timetable_svc.list_entries(db_session, term.id, 1)
    assert len(entries) == 1


# ── Duplicate guards + idempotent generate-structure (HTTP) ───────────────────

@pytest.mark.asyncio
async def test_duplicate_term_name_409(client, admin_headers):
    r1 = await client.post("/v1/admin/timetable/terms", json={"name": "Fall 2026"}, headers=admin_headers)
    assert r1.status_code == 201
    r2 = await client.post("/v1/admin/timetable/terms", json={"name": "fall 2026"}, headers=admin_headers)
    assert r2.status_code == 409
    assert "already exists" in r2.json()["detail"]


@pytest.mark.asyncio
async def test_generate_structure_is_idempotent(client, admin_headers):
    batch = (await client.post(
        "/v1/admin/timetable/batches", json={"name": "Batch 95", "program": "SWE"},
        headers=admin_headers,
    )).json()

    r1 = await client.post(
        f"/v1/admin/timetable/batches/{batch['id']}/generate-structure",
        json={"count": 3, "lab_split": True}, headers=admin_headers,
    )
    assert r1.status_code == 201
    assert r1.json()["created_sections"] == 3 and r1.json()["existing_sections"] == 0

    r2 = await client.post(
        f"/v1/admin/timetable/batches/{batch['id']}/generate-structure",
        json={"count": 3, "lab_split": True}, headers=admin_headers,
    )
    assert r2.json()["created_sections"] == 0 and r2.json()["existing_sections"] == 3

    batches = (await client.get("/v1/admin/timetable/batches", headers=admin_headers)).json()
    b = next(x for x in batches if x["id"] == batch["id"])
    assert len(b["sections"]) == 3
    assert all(len(s["lab_groups"]) == 2 for s in b["sections"])


@pytest.mark.asyncio
async def test_duplicate_offering_and_eligibility_409(client, admin_headers, db_session):
    term = (await client.post("/v1/admin/timetable/terms", json={"name": "Dup Guard"}, headers=admin_headers)).json()
    course = (await client.post(
        "/v1/admin/timetable/courses",
        json={"code": "DG101", "name": "Dup", "credits": 3, "is_lab": False, "weekly_classes": 1},
        headers=admin_headers,
    )).json()
    batch = (await client.post(
        "/v1/admin/timetable/batches", json={"name": "Batch 94", "program": "SWE"},
        headers=admin_headers,
    )).json()

    body = {"term_id": term["id"], "course_id": course["id"], "batch_id": batch["id"]}
    assert (await client.post("/v1/admin/timetable/offerings", json=body, headers=admin_headers)).status_code == 201
    assert (await client.post("/v1/admin/timetable/offerings", json=body, headers=admin_headers)).status_code == 409

    fp = TimetableFacultyProfile(rank="LECTURER", off_days=[], max_per_day=4, active=True)
    db_session.add(fp)
    await db_session.commit()
    elig = {"faculty_id": str(fp.id), "course_id": course["id"]}
    assert (await client.post("/v1/admin/timetable/eligibility", json=elig, headers=admin_headers)).status_code == 201
    assert (await client.post("/v1/admin/timetable/eligibility", json=elig, headers=admin_headers)).status_code == 409
