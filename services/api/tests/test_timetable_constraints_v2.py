"""Tests for the constraint-upgrade work: online-room overflow, weekly active-day
caps, teacher credit-load bounds, professor preferred slot, and registry wiring.

Run: .venv/Scripts/python.exe -m pytest -x -v tests/test_timetable_constraints_v2.py
"""
from contextlib import asynccontextmanager

import pytest

from app.models.timetable import (
    TimetableTerm, TimetableScheduleConfig, TimetableCourse, TimetableBatch,
    TimetableSection, TimetableFacultyProfile, TimetableRoom, TimetableEntry,
    TimetableTeacherEligibility, TimetableCourseOffering,
)
from app.schemas.timetable import SolveRequest
from app.services import timetable_svc
from app.services.timetable_solver import (
    load_solver_data, solve, run_solve_job, rank_credit_bounds,
    default_credit_bounds, CONSTRAINT_BUILDERS, SOFT_BUILDERS,
)


def _session_factory(session):
    @asynccontextmanager
    async def _cm():
        yield session
    return _cm


# ── seed helpers ──────────────────────────────────────────────────────────────

async def _term(db, days, slots):
    term = TimetableTerm(name="V2 Term", is_active=True)
    db.add(term)
    await db.flush()
    db.add(TimetableScheduleConfig(term_id=term.id, days=list(days), slots=list(slots), off_days=[]))
    return term


async def _section(db, batch_id, name):
    s = TimetableSection(batch_id=batch_id, name=name)
    db.add(s)
    await db.flush()
    return s


async def _faculty(db, rank="LECTURER", **kw):
    fp = TimetableFacultyProfile(rank=rank, off_days=[], active=True,
                                 max_per_day=kw.pop("max_per_day", 6), **kw)
    db.add(fp)
    await db.flush()
    return fp


def _room_type_map(data):
    return {r.id: r.room_type for r in data.rooms}


# ── 1. Online overflow ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_online_overflow_places_excess_classes(db_session):
    """3 sections need a theory class in the single slot, but only 1 THEORY room
    exists (+2 ONLINE). All are placed; exactly 2 land in ONLINE rooms."""
    term = await _term(db_session, ["Sat"], ["8:30-10:00"])
    batch = TimetableBatch(name="B", program="SWE")
    db_session.add(batch)
    await db_session.flush()
    for n in ("A", "B", "C"):
        await _section(db_session, batch.id, n)
    course = TimetableCourse(code="C1", name="C1", credits=3, is_lab=False, weekly_classes=1)
    db_session.add_all([
        course,
        TimetableRoom(name="T1", room_type="THEORY", capacity=40),
        TimetableRoom(name="O1", room_type="ONLINE", capacity=999),
        TimetableRoom(name="O2", room_type="ONLINE", capacity=999),
    ])
    await db_session.flush()
    for _ in range(3):                       # one teacher per section (no overlap)
        fp = await _faculty(db_session, max_credits=99)
        db_session.add(TimetableTeacherEligibility(faculty_id=fp.id, course_id=course.id))
    db_session.add(TimetableCourseOffering(term_id=term.id, course_id=course.id, batch_id=batch.id))
    await db_session.commit()

    data = await load_solver_data(db_session, term.id)
    result = solve(data, time_limit_s=30, online_penalty_weight=200)
    assert result["status"] in ("optimal", "feasible"), result.get("infeasible_core")
    assert len(result["entries"]) == 3
    rtype = _room_type_map(data)
    online = [e for e in result["entries"] if rtype.get(e["room_id"]) == "ONLINE"]
    assert len(online) == 2, [rtype.get(e["room_id"]) for e in result["entries"]]


@pytest.mark.asyncio
async def test_validator_flags_online_fallback(db_session):
    """A persisted entry sitting in an ONLINE room is surfaced as an advisory."""
    term = await _term(db_session, ["Sat"], ["8:30-10:00"])
    batch = TimetableBatch(name="B", program="SWE")
    db_session.add(batch)
    await db_session.flush()
    sec = await _section(db_session, batch.id, "A")
    course = TimetableCourse(code="C1", name="C1", credits=3, is_lab=False, weekly_classes=1)
    online = TimetableRoom(name="O1", room_type="ONLINE", capacity=999)
    db_session.add_all([course, online])
    fp = await _faculty(db_session)
    await db_session.flush()
    db_session.add(TimetableEntry(
        term_id=term.id, result_version=1, course_id=course.id, section_id=sec.id,
        faculty_id=fp.id, room_id=online.id, day=0, slot=0, is_lab=False,
        locked=False, source="solver",
    ))
    await db_session.commit()

    conflicts = await timetable_svc.validate_entries(db_session, term.id, 1)
    assert any(c.conflict_type == "online_fallback" for c in conflicts)


# ── 2. Weekly active-day caps ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_section_active_days_capped(db_session):
    """6 single-session courses over 6 available days: with a 3-active-day cap and
    no per-day limit, the section must pack its classes into ≤3 days."""
    term = await _term(db_session, ["Sat", "Sun", "Mon", "Tue", "Wed", "Thu"],
                       [f"s{i}" for i in range(3)])
    batch = TimetableBatch(name="B", program="SWE")
    db_session.add(batch)
    await db_session.flush()
    await _section(db_session, batch.id, "A")
    for i in range(6):
        db_session.add(TimetableRoom(name=f"T{i}", room_type="THEORY", capacity=40))
    for i in range(6):
        c = TimetableCourse(code=f"C{i}", name=f"C{i}", credits=3, is_lab=False, weekly_classes=1)
        db_session.add(c)
        await db_session.flush()
        fp = await _faculty(db_session, max_credits=99)
        db_session.add(TimetableTeacherEligibility(faculty_id=fp.id, course_id=c.id))
        db_session.add(TimetableCourseOffering(term_id=term.id, course_id=c.id, batch_id=batch.id))
    await db_session.commit()

    data = await load_solver_data(db_session, term.id)
    result = solve(data, time_limit_s=30, section_max_per_day=0,
                   max_active_days=3, section_rule_weight=1000)
    assert result["status"] in ("optimal", "feasible"), result.get("infeasible_core")
    assert len({e["day"] for e in result["entries"]}) <= 3


@pytest.mark.asyncio
async def test_teacher_active_days_capped(db_session):
    """One teacher teaches 6 courses; a 3-active-day cap forces those classes into
    ≤3 distinct days (they fit — max_per_day is high)."""
    term = await _term(db_session, ["Sat", "Sun", "Mon", "Tue", "Wed", "Thu"],
                       [f"s{i}" for i in range(3)])
    batch = TimetableBatch(name="B", program="SWE")
    db_session.add(batch)
    await db_session.flush()
    await _section(db_session, batch.id, "A")
    for i in range(6):
        db_session.add(TimetableRoom(name=f"T{i}", room_type="THEORY", capacity=40))
    fp = await _faculty(db_session, max_per_day=6, max_credits=99)
    for i in range(6):
        c = TimetableCourse(code=f"C{i}", name=f"C{i}", credits=3, is_lab=False, weekly_classes=1)
        db_session.add(c)
        await db_session.flush()
        db_session.add(TimetableTeacherEligibility(faculty_id=fp.id, course_id=c.id))
        db_session.add(TimetableCourseOffering(term_id=term.id, course_id=c.id, batch_id=batch.id))
    await db_session.commit()

    data = await load_solver_data(db_session, term.id)
    result = solve(data, time_limit_s=30, section_max_per_day=0,
                   max_active_days=3, section_rule_weight=1000)
    assert result["status"] in ("optimal", "feasible"), result.get("infeasible_core")
    assert len({e["day"] for e in result["entries"]}) <= 3


# ── 3. Teacher credit load ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_credit_max_binds_when_enforced(db_session):
    """A sole teacher capped at 3 credits cannot cover two 3-credit sections of a
    course (needs 6). With credit enforcement the model is infeasible; without it
    (credits ignored) a timetable is produced."""
    term = await _term(db_session, ["Sat"], ["s0", "s1"])
    batch = TimetableBatch(name="B", program="SWE")
    db_session.add(batch)
    await db_session.flush()
    await _section(db_session, batch.id, "A")
    await _section(db_session, batch.id, "B")
    db_session.add(TimetableRoom(name="T0", room_type="THEORY", capacity=40))
    course = TimetableCourse(code="C1", name="C1", credits=3, is_lab=False, weekly_classes=1)
    db_session.add(course)
    await db_session.flush()
    fp = await _faculty(db_session, max_credits=3)
    db_session.add(TimetableTeacherEligibility(faculty_id=fp.id, course_id=course.id))
    db_session.add(TimetableCourseOffering(term_id=term.id, course_id=course.id, batch_id=batch.id))
    await db_session.commit()

    data = await load_solver_data(db_session, term.id)
    hard = solve(data, time_limit_s=30, credit_enforce=True)
    assert hard["status"] == "infeasible"
    soft = solve(data, time_limit_s=30, credit_enforce=False)
    assert soft["status"] in ("optimal", "feasible"), soft.get("infeasible_core")
    assert len(soft["entries"]) == 2


@pytest.mark.asyncio
async def test_insufficient_credit_capacity_diagnostic(db_session):
    """A course whose credit demand (3 cr × 4 sections = 12) exceeds its lone
    eligible teacher's 6-credit cap is flagged at load time."""
    term = await _term(db_session, ["Sat", "Sun", "Mon"], ["s0", "s1", "s2"])
    batch = TimetableBatch(name="B", program="SWE")
    db_session.add(batch)
    await db_session.flush()
    for n in ("A", "B", "C", "D"):
        await _section(db_session, batch.id, n)
    db_session.add(TimetableRoom(name="T0", room_type="THEORY", capacity=40))
    course = TimetableCourse(code="C1", name="C1", credits=3, is_lab=False, weekly_classes=1)
    db_session.add(course)
    await db_session.flush()
    fp = await _faculty(db_session, max_per_day=4, max_credits=6)
    db_session.add(TimetableTeacherEligibility(faculty_id=fp.id, course_id=course.id))
    db_session.add(TimetableCourseOffering(term_id=term.id, course_id=course.id, batch_id=batch.id))
    await db_session.commit()

    data = await load_solver_data(db_session, term.id)
    assert any(d.startswith("insufficient_credit_capacity:") for d in data.diagnostics), data.diagnostics


@pytest.mark.asyncio
async def test_teacher_underloaded_advisory(db_session):
    """A LECTURER (12-credit floor) carrying a single 3-credit class is surfaced
    as an advisory by the validator."""
    term = await _term(db_session, ["Sat"], ["s0"])
    batch = TimetableBatch(name="B", program="SWE")
    db_session.add(batch)
    await db_session.flush()
    sec = await _section(db_session, batch.id, "A")
    course = TimetableCourse(code="C1", name="C1", credits=3, is_lab=False, weekly_classes=1)
    room = TimetableRoom(name="T0", room_type="THEORY", capacity=40)
    db_session.add_all([course, room])
    fp = await _faculty(db_session, rank="LECTURER")
    await db_session.flush()
    db_session.add(TimetableEntry(
        term_id=term.id, result_version=1, course_id=course.id, section_id=sec.id,
        faculty_id=fp.id, room_id=room.id, day=0, slot=0, is_lab=False,
        locked=False, source="solver",
    ))
    await db_session.commit()

    conflicts = await timetable_svc.validate_entries(db_session, term.id, 1)
    assert any(c.conflict_type == "teacher_underloaded" for c in conflicts)


# ── 4. Professor preferred slot ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_professor_defaults_to_ten_slot(db_session):
    """A PROFESSOR with no explicit pref_slot defaults to the 10:00 block and the
    solver places their single class there."""
    term = await _term(db_session, ["Sat"], ["8:30-10:00", "10:00-11:30", "11:30-1:00"])
    batch = TimetableBatch(name="B", program="SWE")
    db_session.add(batch)
    await db_session.flush()
    await _section(db_session, batch.id, "A")
    db_session.add(TimetableRoom(name="T0", room_type="THEORY", capacity=40))
    course = TimetableCourse(code="C1", name="C1", credits=3, is_lab=False, weekly_classes=1)
    db_session.add(course)
    await db_session.flush()
    prof = await _faculty(db_session, rank="PROFESSOR")
    db_session.add(TimetableTeacherEligibility(faculty_id=prof.id, course_id=course.id))
    db_session.add(TimetableCourseOffering(term_id=term.id, course_id=course.id, batch_id=batch.id))
    await db_session.commit()

    data = await load_solver_data(db_session, term.id)
    assert data.faculty[0].pref_slot == 1               # 10:00–11:30 is index 1
    result = solve(data, time_limit_s=30)
    assert result["status"] in ("optimal", "feasible"), result.get("infeasible_core")
    assert result["entries"][0]["slot"] == 1


# ── 5. Pure-unit checks ───────────────────────────────────────────────────────

def test_rank_credit_bounds_defaults():
    assert default_credit_bounds("PROFESSOR") == (3, 6)
    assert default_credit_bounds("HOD") == (3, 6)
    assert default_credit_bounds("LECTURER") == (12, 15)
    assert rank_credit_bounds("PROFESSOR", None, None) == (3, 6)
    assert rank_credit_bounds("LECTURER", None, None) == (12, 15)
    assert rank_credit_bounds("LECTURER", 10, 20) == (10, 20)      # explicit wins


@pytest.mark.asyncio
async def test_run_solve_job_online_overflow_end_to_end(db_session):
    """Full background-job path: config knobs → solve kwargs. A room-starved term
    solves, persists entries with no teacher/room clashes, and overflows exactly
    the excess classes into ONLINE rooms."""
    term = await _term(db_session, ["Sat"], ["8:30-10:00"])
    batch = TimetableBatch(name="B", program="SWE")
    db_session.add(batch)
    await db_session.flush()
    for n in ("A", "B", "C"):
        await _section(db_session, batch.id, n)
    course = TimetableCourse(code="C1", name="C1", credits=3, is_lab=False, weekly_classes=1)
    db_session.add_all([
        course,
        TimetableRoom(name="T1", room_type="THEORY", capacity=40),
        TimetableRoom(name="O1", room_type="ONLINE", capacity=999),
        TimetableRoom(name="O2", room_type="ONLINE", capacity=999),
    ])
    await db_session.flush()
    for _ in range(3):
        fp = await _faculty(db_session, max_credits=99)
        db_session.add(TimetableTeacherEligibility(faculty_id=fp.id, course_id=course.id))
    db_session.add(TimetableCourseOffering(term_id=term.id, course_id=course.id, batch_id=batch.id))
    await db_session.commit()

    job = await timetable_svc.create_solve_job(db_session, term_id=term.id)
    await run_solve_job(job.id, _session_factory(db_session),
                        SolveRequest(term_id=term.id, time_limit_s=30))
    job = await timetable_svc.get_solve_job(db_session, job.id)
    assert job.status in ("optimal", "feasible"), (job.solver_status, job.infeasible_core)

    entries = await timetable_svc.list_entries(db_session, term.id, job.result_version)
    assert len(entries) == 3
    # no teacher or room double-booking in the single slot
    assert len({e.faculty_id for e in entries}) == 3
    assert len({e.room_id for e in entries}) == 3
    rooms = {r.id: r.room_type for r in (
        await timetable_svc.list_rooms(db_session))}
    assert sum(rooms[e.room_id] == "ONLINE" for e in entries) == 2


def test_new_constraint_types_are_registered():
    """Previously-advertised-but-ignored types now resolve to a builder so the
    registry never silently drops them."""
    for t in ("weekly_active_days", "teacher_credit_band", "online_penalty",
              "no_overlap_teacher", "friday_excluded"):
        assert t in CONSTRAINT_BUILDERS, t
    for t in ("gap_minimize", "adjacent_lab", "weekly_active_days",
              "teacher_credit_band", "pref_slot_reward", "online_penalty"):
        assert t in SOFT_BUILDERS, t
