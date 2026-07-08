"""End-to-end solver test on realistic DIU-SWE data.

Seeds the scenario from app.services.timetable_seed_data, runs the CP-SAT solver
directly (synchronous, no background job), persists the result, and asserts the
produced routine has ZERO hard conflicts (room / teacher / section double-booking,
room-type mismatch, and theory↔own-lab clashes). Advisory section-spacing rules
(max/day, consecutive, same-course-per-day) are high-weight *soft* rules — a tight
or time-limited solve may relax them — so `_hard_conflicts` filters them out here.

Run (fast subset, part of the default suite):
    .venv/Scripts/python.exe -m pytest -x -v tests/test_timetable_generator_scale.py

Run the full 9-batch × 8-section case (heavy — opt in):
    RUN_FULL_SCALE=1 .venv/Scripts/python.exe -m pytest -s -v \
        tests/test_timetable_generator_scale.py::test_full_scale_solver_no_overlaps
"""
import os
import time
from contextlib import asynccontextmanager

import pytest

from app.schemas.timetable import SolveRequest
from app.services.timetable_seed_data import seed_scenario
from app.services.timetable_solver import load_solver_data, solve, run_solve_job
from app.services import timetable_svc
from app.models.timetable import TimetableEntry


def _session_factory(session):
    """Factory yielding the test session, shaped like AsyncSessionLocal."""
    @asynccontextmanager
    async def _cm():
        yield session
    return _cm


async def _run_job_and_validate(db, term_id, *, time_limit_s, n_sessions):
    """Drive the real background-job path (per-batch decomposition) and
    validate the merged result version globally — faculty/room/section clashes
    across batch groups are exactly what this catches."""
    job = await timetable_svc.create_solve_job(db, term_id=term_id)
    t0 = time.perf_counter()
    await run_solve_job(
        job.id, _session_factory(db),
        SolveRequest(term_id=term_id, time_limit_s=time_limit_s),
    )
    elapsed = time.perf_counter() - t0

    job = await timetable_svc.get_solve_job(db, job.id)
    print(f"\n[job] status={job.status} solver_status={job.solver_status} "
          f"version={job.result_version} core={job.infeasible_core} wall={elapsed:.1f}s")
    assert job.status in ("optimal", "feasible"), (job.solver_status, job.infeasible_core)
    assert job.progress == 100
    assert job.result_version == 1

    entries = await timetable_svc.list_entries(db, term_id, 1)
    assert len(entries) == n_sessions, (
        f"expected {n_sessions} placed sessions, got {len(entries)}"
    )
    return await timetable_svc.validate_entries(db, term_id, 1)


def _hard_conflicts(conflicts):
    """Drop advisory section-spacing conflicts — those are acceptable, high-weight
    soft relaxations (a tight/time-limited solve may not space perfectly), not the
    room/teacher/section overlaps these tests exist to catch."""
    return [c for c in conflicts if c.conflict_type not in timetable_svc.ADVISORY_CONFLICT_TYPES]


async def _run_and_validate(db, term_id, *, time_limit_s):
    """Load data → solve → persist entries → validate. Returns (result, conflicts)."""
    data = await load_solver_data(db, term_id)
    n_sessions = len(data.offerings)

    t0 = time.perf_counter()
    result = solve(data, time_limit_s=time_limit_s)
    elapsed = time.perf_counter() - t0

    print(
        f"\n[solver] offerings(sessions)={n_sessions} faculty={len(data.faculty)} "
        f"rooms={len(data.rooms)} days={data.n_days} slots={data.n_slots} "
        f"=> status={result['status']} entries={len(result['entries'])} "
        f"objective={result.get('objective')} wall={elapsed:.1f}s"
    )

    assert result["status"] in ("optimal", "feasible"), (
        f"solver returned {result['status']}; core={result.get('infeasible_core')}"
    )
    # Every class session must be placed exactly once.
    assert len(result["entries"]) == n_sessions

    entries = [
        TimetableEntry(term_id=term_id, result_version=1, **e)
        for e in result["entries"]
    ]
    await timetable_svc.bulk_insert_entries(db, entries)

    conflicts = await timetable_svc.validate_entries(db, term_id, 1)
    return result, conflicts


@pytest.mark.asyncio
async def test_subset_solver_no_overlaps(db_session):
    """2 batches × 8 sections, 6 days × 6 slots — must solve clash-free quickly."""
    info = await seed_scenario(db_session, n_batches=2, n_slots=6, eligible_per_course=4)
    assert info["n_sections"] == 16

    _, conflicts = await _run_and_validate(db_session, info["term_id"], time_limit_s=30)

    hard = _hard_conflicts(conflicts)
    assert hard == [], f"expected no hard conflicts, got: {[c.description for c in hard]}"


@pytest.mark.asyncio
async def test_unplaceable_offering_reports_infeasible(db_session):
    """A course with no eligible faculty must fail loudly, not silently break the model."""
    from app.models.timetable import TimetableCourse, TimetableCourseOffering, TimetableBatch
    from app.services import timetable_svc as svc

    info = await seed_scenario(db_session, n_batches=2, n_slots=6, eligible_per_course=4)

    # Add a course with an offering but no eligibility rows.
    orphan = TimetableCourse(code="ZZZ999", name="Orphan", credits=3, is_lab=False, weekly_classes=2)
    db_session.add(orphan)
    await db_session.flush()
    batches = await svc.list_batches(db_session)
    db_session.add(TimetableCourseOffering(
        term_id=info["term_id"], course_id=orphan.id, batch_id=batches[0].id,
    ))
    await db_session.commit()

    data = await load_solver_data(db_session, info["term_id"])
    result = solve(data, time_limit_s=10)
    assert result["status"] == "infeasible"
    assert any("ZZZ999" in str(c) for c in (result["infeasible_core"] or []))


@pytest.mark.asyncio
async def test_decomposed_solver_4_batches_no_overlaps(db_session):
    """4 batches → per-batch decomposition (threshold is 2). This is the S-1
    regression proof: the old monolith could no longer solve 4+ batches."""
    info = await seed_scenario(db_session, n_batches=4, n_slots=8, eligible_per_course=4)

    data = await load_solver_data(db_session, info["term_id"])
    n_sessions = len(data.offerings)

    conflicts = await _run_job_and_validate(
        db_session, info["term_id"], time_limit_s=120, n_sessions=n_sessions,
    )
    hard = _hard_conflicts(conflicts)
    assert hard == [], f"expected no hard conflicts, got: {[c.description for c in hard]}"


@pytest.mark.skipif(
    os.environ.get("RUN_FULL_SCALE") != "1",
    reason="heavy full-scale solve; set RUN_FULL_SCALE=1 to run",
)
@pytest.mark.asyncio
async def test_full_scale_solver_no_overlaps(db_session):
    """Full 9 batches × 8 sections (72 sections, ~850 weekly sessions),
    through the decomposed background-job driver."""
    info = await seed_scenario(db_session, n_batches=9, n_slots=8, eligible_per_course=4)
    assert info["n_sections"] == 72
    print(f"\n[seed] {info}")

    data = await load_solver_data(db_session, info["term_id"])
    n_sessions = len(data.offerings)

    conflicts = await _run_job_and_validate(
        db_session, info["term_id"], time_limit_s=180, n_sessions=n_sessions,
    )

    by_type: dict[str, int] = {}
    for c in conflicts:
        by_type[c.conflict_type] = by_type.get(c.conflict_type, 0) + 1
    hard = _hard_conflicts(conflicts)
    assert hard == [], f"hard conflicts by type: {by_type}"
