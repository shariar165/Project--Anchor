"""End-to-end solver test on realistic DIU-SWE data.

Seeds the scenario from app.services.timetable_seed_data, runs the CP-SAT solver
directly (synchronous, no background job), persists the result, and asserts the
produced routine has ZERO hard conflicts (room / teacher / section double-booking,
room-type mismatch, and theory↔own-lab clashes).

Run (fast subset, part of the default suite):
    .venv/Scripts/python.exe -m pytest -x -v tests/test_timetable_generator_scale.py

Run the full 9-batch × 8-section case (heavy — opt in):
    RUN_FULL_SCALE=1 .venv/Scripts/python.exe -m pytest -s -v \
        tests/test_timetable_generator_scale.py::test_full_scale_solver_no_overlaps
"""
import os
import time

import pytest

from app.services.timetable_seed_data import seed_scenario
from app.services.timetable_solver import load_solver_data, solve
from app.services import timetable_svc
from app.models.timetable import TimetableEntry


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

    assert conflicts == [], f"expected no conflicts, got: {[c.description for c in conflicts]}"


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


@pytest.mark.skipif(
    os.environ.get("RUN_FULL_SCALE") != "1",
    reason="heavy full-scale solve; set RUN_FULL_SCALE=1 to run",
)
@pytest.mark.asyncio
async def test_full_scale_solver_no_overlaps(db_session):
    """Full 9 batches × 8 sections (72 sections, ~850 weekly sessions)."""
    info = await seed_scenario(db_session, n_batches=9, n_slots=8, eligible_per_course=4)
    assert info["n_sections"] == 72
    print(f"\n[seed] {info}")

    _, conflicts = await _run_and_validate(db_session, info["term_id"], time_limit_s=180)

    by_type: dict[str, int] = {}
    for c in conflicts:
        by_type[c.conflict_type] = by_type.get(c.conflict_type, 0) + 1
    assert conflicts == [], f"conflicts by type: {by_type}"
