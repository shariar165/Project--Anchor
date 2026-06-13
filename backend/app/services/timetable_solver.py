"""CP-SAT timetable solver with registry-driven constraints."""
import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.timetable import (
    TimetableTerm, TimetableBatch, TimetableSection, TimetableLabGroup,
    TimetableRoom, TimetableCourse, TimetableFacultyProfile,
    TimetableCourseOffering, TimetableTeacherEligibility,
    TimetableScheduleConfig, TimetableConstraint,
    TimetableSolveJob, TimetableEntry,
)
from app.schemas.timetable import SolveRequest, EntryEdit
from app.services import timetable_svc

logger = logging.getLogger(__name__)

# ── Data containers ───────────────────────────────────────────────────────────

@dataclass
class OfferingSlot:
    """One class occurrence that needs to be placed (copy_idx handles weekly_classes > 1)."""
    offering_id: uuid.UUID
    course: TimetableCourse
    section: TimetableSection
    lab_group: TimetableLabGroup | None
    copy_idx: int

@dataclass
class SolverData:
    term: TimetableTerm
    config: TimetableScheduleConfig
    n_days: int
    n_slots: int
    offerings: list[OfferingSlot] = field(default_factory=list)
    faculty: list[TimetableFacultyProfile] = field(default_factory=list)
    rooms: list[TimetableRoom] = field(default_factory=list)
    constraints: list[TimetableConstraint] = field(default_factory=list)
    # Maps eligible faculty for each course_id
    eligible: dict[uuid.UUID, list[uuid.UUID]] = field(default_factory=dict)  # course_id → [faculty_id]
    # Existing entries for warm-start / perturbation
    prev_entries: list[TimetableEntry] = field(default_factory=list)


async def load_solver_data(db: AsyncSession, term_id: uuid.UUID, seed_version: int | None = None) -> SolverData:
    """Load all scheduling data for a term."""
    term_r = await db.execute(select(TimetableTerm).where(TimetableTerm.id == term_id))
    term = term_r.scalars().first()
    if not term:
        raise ValueError(f"Term {term_id} not found")

    config = await timetable_svc.get_schedule_config(db, term_id=term_id)
    if not config:
        raise ValueError("Schedule config not found — set days and slots first")

    n_days = len(config.days)
    n_slots = len(config.slots)

    # Load rooms
    rooms_r = await db.execute(select(TimetableRoom))
    rooms = list(rooms_r.scalars().all())

    # Load faculty
    faculty_r = await db.execute(
        select(TimetableFacultyProfile).where(TimetableFacultyProfile.active == True)
    )
    faculty = list(faculty_r.scalars().all())
    faculty_by_id = {fp.id: fp for fp in faculty}

    # Build eligibility map
    elig_r = await db.execute(select(TimetableTeacherEligibility))
    eligible: dict[uuid.UUID, list[uuid.UUID]] = {}
    for elig in elig_r.scalars().all():
        eligible.setdefault(elig.course_id, []).append(elig.faculty_id)

    # Load offerings for this term
    off_r = await db.execute(
        select(TimetableCourseOffering).where(TimetableCourseOffering.term_id == term_id)
    )
    raw_offerings = list(off_r.scalars().all())

    # Load courses + sections + lab groups
    courses_r = await db.execute(select(TimetableCourse))
    courses_by_id = {c.id: c for c in courses_r.scalars().all()}

    secs_r = await db.execute(select(TimetableSection))
    sections_by_batch: dict[uuid.UUID, list[TimetableSection]] = {}
    for s in secs_r.scalars().all():
        sections_by_batch.setdefault(s.batch_id, []).append(s)

    lgs_r = await db.execute(select(TimetableLabGroup))
    lab_groups_by_section: dict[uuid.UUID, list[TimetableLabGroup]] = {}
    for lg in lgs_r.scalars().all():
        lab_groups_by_section.setdefault(lg.section_id, []).append(lg)

    # Build OfferingSlot list
    offering_slots: list[OfferingSlot] = []
    for off in raw_offerings:
        course = courses_by_id.get(off.course_id)
        if not course:
            continue
        sections = sections_by_batch.get(off.batch_id, [])
        for section in sections:
            if course.is_lab:
                # One slot per lab group
                for lg in lab_groups_by_section.get(section.id, []):
                    for copy_idx in range(course.weekly_classes):
                        offering_slots.append(OfferingSlot(
                            offering_id=off.id, course=course,
                            section=section, lab_group=lg, copy_idx=copy_idx,
                        ))
            else:
                for copy_idx in range(course.weekly_classes):
                    offering_slots.append(OfferingSlot(
                        offering_id=off.id, course=course,
                        section=section, lab_group=None, copy_idx=copy_idx,
                    ))

    # Load constraints
    con_r = await db.execute(
        select(TimetableConstraint).where(
            TimetableConstraint.term_id == term_id,
            TimetableConstraint.enabled == True,
        )
    )
    constraints = list(con_r.scalars().all())

    # Load previous entries for warm-start
    prev_entries: list[TimetableEntry] = []
    if seed_version is not None:
        prev_entries = await timetable_svc.list_entries(db, term_id, seed_version)

    return SolverData(
        term=term, config=config, n_days=n_days, n_slots=n_slots,
        offerings=offering_slots, faculty=faculty, rooms=rooms,
        constraints=constraints, eligible=eligible, prev_entries=prev_entries,
    )


# ── Solver ────────────────────────────────────────────────────────────────────

def solve(
    data: SolverData,
    time_limit_s: int = 60,
    pinned_change: EntryEdit | None = None,
    locked_entry_ids: set[uuid.UUID] | None = None,
    base_entries: list[TimetableEntry] | None = None,
) -> dict:
    """
    Run CP-SAT. Returns:
      {status, objective, entries: list[dict], infeasible_core: list[uuid]}
    """
    try:
        from ortools.sat.python import cp_model
    except ImportError:
        return {"status": "failed", "error": "ortools not installed", "entries": [], "infeasible_core": []}

    model = cp_model.CpModel()

    faculty_by_id = {fp.id: fp for fp in data.faculty}
    room_by_id = {r.id: r for r in data.rooms}
    offering_count = len(data.offerings)
    faculty_list = data.faculty
    room_list = data.rooms

    if not offering_count or not faculty_list or not room_list:
        return {"status": "feasible", "objective": 0, "entries": [], "infeasible_core": []}

    n_f = len(faculty_list)
    n_r = len(room_list)
    n_d = data.n_days
    n_s = data.n_slots

    # faculty/room index maps
    faculty_idx = {fp.id: i for i, fp in enumerate(faculty_list)}
    room_idx = {r.id: i for i, r in enumerate(room_list)}

    # ── Variables ─────────────────────────────────────────────────────────────
    # x[o][f][r][d][s] = 1 iff offering o is taught by faculty f in room r on day d slot s
    x = {}
    for o_idx in range(offering_count):
        x[o_idx] = {}
        for f_idx in range(n_f):
            x[o_idx][f_idx] = {}
            for r_idx in range(n_r):
                x[o_idx][f_idx][r_idx] = {}
                for d in range(n_d):
                    x[o_idx][f_idx][r_idx][d] = {}
                    for s in range(n_s):
                        x[o_idx][f_idx][r_idx][d][s] = model.new_bool_var(
                            f"x_{o_idx}_{f_idx}_{r_idx}_{d}_{s}"
                        )

    # Indexed lookups — O(1) access instead of scanning all vars
    by_faculty_slot: dict[tuple, list] = {}
    by_room_slot: dict[tuple, list] = {}
    by_section_slot: dict[tuple, list] = {}

    for o_idx, offering in enumerate(data.offerings):
        for f_idx, fp in enumerate(faculty_list):
            for r_idx, room in enumerate(room_list):
                for d in range(n_d):
                    for s in range(n_s):
                        var = x[o_idx][f_idx][r_idx][d][s]
                        by_faculty_slot.setdefault((f_idx, d, s), []).append(var)
                        by_room_slot.setdefault((r_idx, d, s), []).append(var)
                        by_section_slot.setdefault((offering.section.id, d, s, offering.lab_group.id if offering.lab_group else None), []).append(var)

    # ── Hard constraints ──────────────────────────────────────────────────────
    assumption_map: dict[str, any] = {}  # constraint_id → assumption BoolVar

    # Each offering must be assigned exactly once
    for o_idx in range(offering_count):
        model.add_exactly_one(
            x[o_idx][f_idx][r_idx][d][s]
            for f_idx in range(n_f)
            for r_idx in range(n_r)
            for d in range(n_d)
            for s in range(n_s)
        )

    # No room double-booked
    for key, vars_list in by_room_slot.items():
        if len(vars_list) > 1:
            model.add(sum(vars_list) <= 1)

    # No teacher in two places at once
    for key, vars_list in by_faculty_slot.items():
        if len(vars_list) > 1:
            model.add(sum(vars_list) <= 1)

    # No section in two theory classes at once (lab groups are separate)
    for key, vars_list in by_section_slot.items():
        if len(vars_list) > 1:
            model.add(sum(vars_list) <= 1)

    # Only eligible faculty can teach each offering
    for o_idx, offering in enumerate(data.offerings):
        eligible_ids = data.eligible.get(offering.course.id, [])
        for f_idx, fp in enumerate(faculty_list):
            if fp.id not in eligible_ids:
                for r_idx in range(n_r):
                    for d in range(n_d):
                        for s in range(n_s):
                            model.add(x[o_idx][f_idx][r_idx][d][s] == 0)

    # Room type match: lab courses → LAB rooms, theory → THEORY or ONLINE
    for o_idx, offering in enumerate(data.offerings):
        for r_idx, room in enumerate(room_list):
            if offering.course.is_lab and room.room_type == "THEORY":
                for f_idx in range(n_f):
                    for d in range(n_d):
                        for s in range(n_s):
                            model.add(x[o_idx][f_idx][r_idx][d][s] == 0)
            elif not offering.course.is_lab and room.room_type == "LAB":
                for f_idx in range(n_f):
                    for d in range(n_d):
                        for s in range(n_s):
                            model.add(x[o_idx][f_idx][r_idx][d][s] == 0)

    # Off-days from faculty profile
    for o_idx in range(offering_count):
        for f_idx, fp in enumerate(faculty_list):
            for d in (fp.off_days or []):
                if 0 <= d < n_d:
                    for r_idx in range(n_r):
                        for s in range(n_s):
                            model.add(x[o_idx][f_idx][r_idx][d][s] == 0)

    # Registry-driven constraints
    for con in data.constraints:
        if not con.enabled:
            continue
        builder = CONSTRAINT_BUILDERS.get(con.constraint_type)
        if builder is None:
            continue
        try:
            assumption = model.new_bool_var(f"assume_{con.id}")
            builder(model, x, data, faculty_list, room_list, faculty_idx, room_idx,
                    con.scope, con.params, assumption)
            assumption_map[str(con.id)] = assumption
        except Exception as exc:
            logger.warning(f"Constraint {con.constraint_type} build failed: {exc}")

    # ── Perturbation hints (minimal-perturbation re-solve) ────────────────────
    penalty_terms = []

    if base_entries:
        _add_perturbation(
            model, x, data, faculty_list, room_list, faculty_idx, room_idx,
            base_entries, locked_entry_ids or set(), pinned_change, penalty_terms,
        )

    # ── Soft constraints (penalties) ──────────────────────────────────────────
    for con in data.constraints:
        if not con.enabled or con.enforcement != "soft":
            continue
        soft_builder = SOFT_BUILDERS.get(con.constraint_type)
        if soft_builder:
            try:
                soft_builder(model, x, data, faculty_list, room_list, faculty_idx, room_idx,
                             con.scope, con.params, con.weight or 1, penalty_terms)
            except Exception as exc:
                logger.warning(f"Soft constraint {con.constraint_type} build failed: {exc}")

    if penalty_terms:
        model.minimize(sum(penalty_terms))

    # ── Warm start hints ──────────────────────────────────────────────────────
    if data.prev_entries and not base_entries:
        _add_warm_hints(model, x, data, faculty_list, room_list, faculty_idx, room_idx)

    # ── Solve ─────────────────────────────────────────────────────────────────
    if assumption_map:
        model.add_assumptions(list(assumption_map.values()))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(time_limit_s)
    solver.parameters.num_search_workers = 4
    status = solver.solve(model)

    status_name = solver.status_name(status)

    infeasible_core: list[str] = []
    if status == cp_model.INFEASIBLE and assumption_map:
        try:
            core_vars = solver.sufficient_assumptions_for_infeasibility()
            # Map BoolVar index back to constraint ID
            reverse_map = {v.index: k for k, v in assumption_map.items()}
            infeasible_core = [reverse_map[v.index] for v in core_vars if v.index in reverse_map]
        except Exception:
            pass

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return {
            "status": status_name.lower(),
            "objective": None,
            "entries": [],
            "infeasible_core": infeasible_core,
        }

    # Extract solution
    result_entries = []
    for o_idx, offering in enumerate(data.offerings):
        for f_idx, fp in enumerate(faculty_list):
            for r_idx, room in enumerate(room_list):
                for d in range(n_d):
                    for s in range(n_s):
                        if solver.boolean_value(x[o_idx][f_idx][r_idx][d][s]):
                            result_entries.append({
                                "course_id": offering.course.id,
                                "section_id": offering.section.id,
                                "lab_group_id": offering.lab_group.id if offering.lab_group else None,
                                "faculty_id": fp.id,
                                "room_id": room.id,
                                "day": d,
                                "slot": s,
                                "is_lab": offering.course.is_lab,
                                "locked": False,
                                "source": "solver",
                            })

    return {
        "status": status_name.lower(),
        "objective": int(solver.objective_value) if penalty_terms else 0,
        "entries": result_entries,
        "infeasible_core": infeasible_core,
    }


def _add_perturbation(
    model, x, data, faculty_list, room_list, faculty_idx, room_idx,
    base_entries, locked_ids, pinned_change, penalty_terms,
):
    """Add warm hints + lock constraints + perturbation penalty."""
    from ortools.sat.python import cp_model

    # Build lookup: (section_id, lab_group_id, course_id, copy_idx) → offering_idx
    offering_key_map: dict[tuple, int] = {}
    for o_idx, offering in enumerate(data.offerings):
        lg_id = offering.lab_group.id if offering.lab_group else None
        key = (offering.section.id, lg_id, offering.course.id, offering.copy_idx)
        offering_key_map[key] = o_idx

    for entry in base_entries:
        lg_id = entry.lab_group_id
        # find matching offering_idx (try copy_idx 0, 1, ...)
        o_idx = None
        for copy_idx in range(10):
            key = (entry.section_id, lg_id, entry.course_id, copy_idx)
            if key in offering_key_map:
                o_idx = offering_key_map.pop(key)
                break
        if o_idx is None:
            continue

        f_idx = faculty_idx.get(entry.faculty_id)
        r_idx = room_idx.get(entry.room_id)
        if f_idx is None or r_idx is None:
            continue

        var = x[o_idx][f_idx][r_idx][entry.day][entry.slot]

        if entry.id in locked_ids:
            # Hard-pin locked entry
            model.add(var == 1)
        else:
            # Soft: reward staying in same position
            stay = model.new_bool_var(f"stay_{o_idx}")
            model.add(var == 1).only_enforce_if(stay)
            model.add(var == 0).only_enforce_if(stay.negated())
            # Add movement penalty (weight 5 = strongly prefer not to move)
            move = model.new_bool_var(f"move_{o_idx}")
            model.add_bool_or([stay, move])
            model.add_bool_and([stay.negated()]).only_enforce_if(move)
            penalty_terms.append(5 * move)

    # Apply pinned change
    if pinned_change and pinned_change.entry_id:
        # Find the entry in base_entries
        for entry in base_entries:
            if entry.id == pinned_change.entry_id:
                lg_id = entry.lab_group_id
                for copy_idx in range(10):
                    key = (entry.section_id, lg_id, entry.course_id, copy_idx)
                    if key in offering_key_map:
                        continue
                # Use new values for pinning
                new_day = pinned_change.new_day if pinned_change.new_day is not None else entry.day
                new_slot = pinned_change.new_slot if pinned_change.new_slot is not None else entry.slot
                new_f_id = pinned_change.new_faculty_id or entry.faculty_id
                new_r_id = pinned_change.new_room_id or entry.room_id
                nf_idx = faculty_idx.get(new_f_id)
                nr_idx = room_idx.get(new_r_id)
                # Find o_idx for this entry
                for o_idx, offering in enumerate(data.offerings):
                    if (offering.section.id == entry.section_id and
                            offering.course.id == entry.course_id):
                        if nf_idx is not None and nr_idx is not None:
                            model.add(x[o_idx][nf_idx][nr_idx][new_day][new_slot] == 1)
                        break
                break


def _add_warm_hints(model, x, data, faculty_list, room_list, faculty_idx, room_idx):
    """Provide previous solution as hints to speed up re-solve."""
    for entry in data.prev_entries:
        f_idx = faculty_idx.get(entry.faculty_id)
        r_idx = room_idx.get(entry.room_id)
        if f_idx is None or r_idx is None:
            continue
        for o_idx, offering in enumerate(data.offerings):
            if (offering.section.id == entry.section_id and
                    offering.course.id == entry.course_id):
                model.add_hint(x[o_idx][f_idx][r_idx][entry.day][entry.slot], 1)
                break


# ── Constraint registry ───────────────────────────────────────────────────────

def _build_max_per_day(model, x, data, faculty_list, room_list, faculty_idx, room_idx,
                       scope, params, assumption):
    limit = int(params.get("limit", 4))
    for f_idx in range(len(faculty_list)):
        for d in range(data.n_days):
            day_vars = [
                x[o_idx][f_idx][r_idx][d][s]
                for o_idx in range(len(data.offerings))
                for r_idx in range(len(room_list))
                for s in range(data.n_slots)
            ]
            if day_vars:
                model.add(sum(day_vars) <= limit).only_enforce_if(assumption)


def _build_consecutive_limit(model, x, data, faculty_list, room_list, faculty_idx, room_idx,
                              scope, params, assumption):
    limit = int(params.get("limit", 2))
    for f_idx in range(len(faculty_list)):
        for d in range(data.n_days):
            for s_start in range(data.n_slots - limit):
                window_vars = [
                    x[o_idx][f_idx][r_idx][d][s]
                    for o_idx in range(len(data.offerings))
                    for r_idx in range(len(room_list))
                    for s in range(s_start, s_start + limit + 1)
                ]
                if window_vars:
                    model.add(sum(window_vars) <= limit).only_enforce_if(assumption)


CONSTRAINT_BUILDERS = {
    "max_classes_per_day": _build_max_per_day,
    "consecutive_limit": _build_consecutive_limit,
}


def _soft_pref_slot(model, x, data, faculty_list, room_list, faculty_idx, room_idx,
                    scope, params, weight, penalty_terms):
    for f_idx, fp in enumerate(faculty_list):
        if fp.pref_slot is None:
            continue
        pref_s = fp.pref_slot
        for o_idx in range(len(data.offerings)):
            for r_idx in range(len(room_list)):
                for d in range(data.n_days):
                    for s in range(data.n_slots):
                        if s != pref_s:
                            penalty_var = model.new_bool_var(f"pref_{f_idx}_{o_idx}_{d}_{s}")
                            model.add(x[o_idx][f_idx][r_idx][d][s] <= penalty_var)
                            penalty_terms.append(weight * penalty_var)


def _soft_online_penalty(model, x, data, faculty_list, room_list, faculty_idx, room_idx,
                         scope, params, weight, penalty_terms):
    for r_idx, room in enumerate(room_list):
        if room.room_type == "ONLINE":
            for o_idx in range(len(data.offerings)):
                for f_idx in range(len(faculty_list)):
                    for d in range(data.n_days):
                        for s in range(data.n_slots):
                            penalty_terms.append(weight * x[o_idx][f_idx][r_idx][d][s])


SOFT_BUILDERS = {
    "pref_slot_reward": _soft_pref_slot,
    "online_penalty": _soft_online_penalty,
}


# ── Background job runner ─────────────────────────────────────────────────────

async def run_solve_job(
    job_id: uuid.UUID,
    db_factory,
    request: SolveRequest,
    pinned_change: EntryEdit | None = None,
    locked_entry_ids: set[uuid.UUID] | None = None,
    base_entries: list[TimetableEntry] | None = None,
) -> None:
    """Background task — opens its own DB session. Never raises."""
    try:
        async with db_factory() as db:
            job = await timetable_svc.get_solve_job(db, job_id)
            if not job:
                return
            await timetable_svc.update_solve_job(
                db, job,
                status="running",
                started_at=datetime.now(timezone.utc),
                progress=10,
            )
    except Exception as exc:
        logger.warning(f"Solve job {job_id} could not start (DB unavailable?): {exc}")
        return

    try:
        async with db_factory() as db:
            data = await load_solver_data(
                db, request.term_id,
                seed_version=request.seed_from_version,
            )

        # Run solver in thread pool (CPU-bound)
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: solve(
                data,
                time_limit_s=request.time_limit_s,
                pinned_change=pinned_change,
                locked_entry_ids=locked_entry_ids,
                base_entries=base_entries,
            ),
        )

        async with db_factory() as db:
            job = await timetable_svc.get_solve_job(db, job_id)
            if not job:
                return

            if result["status"] in ("optimal", "feasible"):
                next_version = await timetable_svc.get_next_version(db, request.term_id)
                entries = [
                    TimetableEntry(
                        tenant_id=job.tenant_id,
                        term_id=request.term_id,
                        result_version=next_version,
                        **e,
                    )
                    for e in result["entries"]
                ]
                await timetable_svc.bulk_insert_entries(db, entries)
                await timetable_svc.update_solve_job(
                    db, job,
                    status=result["status"],
                    progress=100,
                    solver_status=result["status"],
                    objective_value=result.get("objective"),
                    result_version=next_version,
                    finished_at=datetime.now(timezone.utc),
                    infeasible_core=result.get("infeasible_core") or [],
                )
            else:
                await timetable_svc.update_solve_job(
                    db, job,
                    status=result["status"],
                    progress=100,
                    solver_status=result["status"],
                    finished_at=datetime.now(timezone.utc),
                    infeasible_core=result.get("infeasible_core") or [],
                )
    except Exception as exc:
        logger.exception(f"Solve job {job_id} failed")
        try:
            async with db_factory() as db:
                job = await timetable_svc.get_solve_job(db, job_id)
                if job:
                    await timetable_svc.update_solve_job(
                        db, job,
                        status="failed",
                        progress=0,
                        solver_status=str(exc)[:30],
                        finished_at=datetime.now(timezone.utc),
                    )
        except Exception:
            logger.warning(f"Solve job {job_id} could not update failure status (DB unavailable?)")


# ── NL → EntryEdit ────────────────────────────────────────────────────────────

async def nl_to_entry_edit(text: str, entries_context: list[dict]) -> EntryEdit | None:
    """Parse a natural-language timetable command into an EntryEdit using Ollama."""
    try:
        import httpx
        from app.config import get_settings
        settings = get_settings()
        ollama_url = getattr(settings, "ollama_base_url", "http://localhost:11434")

        context_summary = json.dumps(entries_context[:20], default=str)
        prompt = (
            f"You are a timetable assistant. Current entries (first 20): {context_summary}\n\n"
            f"User command: {text}\n\n"
            "Return ONLY valid JSON matching this schema: "
            '{"entry_id": "<uuid or null>", "new_day": <0-5 or null>, "new_slot": <int or null>, '
            '"new_faculty_id": "<uuid or null>", "new_room_id": "<uuid or null>", "lock": true}. '
            "Use null for fields that don't change. Do not explain."
        )

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{ollama_url}/api/generate",
                json={"model": "qwen3:1.7b", "prompt": prompt, "stream": False},
            )
            resp.raise_for_status()
            raw = resp.json().get("response", "")

        # Extract JSON from response
        import re
        match = re.search(r"\{.*?\}", raw, re.DOTALL)
        if not match:
            return None
        data = json.loads(match.group())
        return EntryEdit(
            entry_id=uuid.UUID(data["entry_id"]) if data.get("entry_id") else None,
            new_day=data.get("new_day"),
            new_slot=data.get("new_slot"),
            new_faculty_id=uuid.UUID(data["new_faculty_id"]) if data.get("new_faculty_id") else None,
            new_room_id=uuid.UUID(data["new_room_id"]) if data.get("new_room_id") else None,
            lock=data.get("lock", True),
        )
    except Exception as exc:
        logger.warning(f"NL parse failed: {exc}")
        return None
