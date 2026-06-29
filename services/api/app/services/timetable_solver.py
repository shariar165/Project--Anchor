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

    # ── Decision variables: (offering, faculty, day, slot) ────────────────────
    # Rooms are deliberately NOT part of the decision variable. Every room of a
    # given type is interchangeable (there are no room-specific constraints), so
    # pinning a concrete room inside CP-SAT only injects massive symmetry that
    # defeats the solver even at small scale. Instead we cap the number of
    # concurrent classes per (day, slot) to the rooms available for that type, and
    # assign concrete rooms in a trivial post-pass (Hall's theorem guarantees a
    # clash-free assignment exists once the per-slot capacity holds).
    #
    # x[o] = { (f_idx, d, s): BoolVar }, created only for faculty eligible to teach
    # the course, on days that are not one of that faculty's off-days. This keeps
    # the model from ~1e9 booleans (dense offering×faculty×room×day×slot) down to a
    # few hundred-thousand at full scale.

    eligible_f_idx_by_course: dict[uuid.UUID, list[int]] = {}
    for course_id, fac_ids in data.eligible.items():
        eligible_f_idx_by_course[course_id] = [
            faculty_idx[fid] for fid in fac_ids if fid in faculty_idx
        ]

    # Room pools by type. Theory draws from THEORY (preferred) then ONLINE.
    theory_room_ids = [r.id for r in room_list if r.room_type == "THEORY"]
    online_room_ids = [r.id for r in room_list if r.room_type == "ONLINE"]
    lab_room_ids = [r.id for r in room_list if r.room_type == "LAB"]
    theory_pool = theory_room_ids + online_room_ids
    n_theory_cap = len(theory_pool)
    n_lab_cap = len(lab_room_ids)

    x: dict[int, dict[tuple, any]] = {}
    vars_by_offering: dict[int, list] = {}
    by_faculty_slot: dict[tuple, list] = {}
    by_section_slot: dict[tuple, list] = {}
    theory_by_slot: dict[tuple, list] = {}   # (d, s) -> vars of theory offerings
    lab_by_slot: dict[tuple, list] = {}      # (d, s) -> vars of lab offerings
    unplaceable: list[str] = []

    for o_idx, offering in enumerate(data.offerings):
        is_lab = offering.course.is_lab
        cell: dict[tuple, any] = {}
        x[o_idx] = cell
        vars_by_offering[o_idx] = []
        # No room of the required type, or no eligible faculty → unplaceable.
        allowed_f = eligible_f_idx_by_course.get(offering.course.id, [])
        if (is_lab and n_lab_cap == 0) or (not is_lab and n_theory_cap == 0) or not allowed_f:
            unplaceable.append(offering.course.code)
            continue
        lg_id = offering.lab_group.id if offering.lab_group else None
        slot_bucket = lab_by_slot if is_lab else theory_by_slot
        for f_idx in allowed_f:
            off = set(faculty_list[f_idx].off_days or [])
            for d in range(n_d):
                if d in off:
                    continue
                for s in range(n_s):
                    var = model.new_bool_var(f"x_{o_idx}_{f_idx}_{d}_{s}")
                    cell[(f_idx, d, s)] = var
                    by_faculty_slot.setdefault((f_idx, d, s), []).append(var)
                    by_section_slot.setdefault((offering.section.id, d, s, lg_id), []).append(var)
                    slot_bucket.setdefault((d, s), []).append(var)
        vars_by_offering[o_idx] = list(cell.values())
        if not cell:
            unplaceable.append(offering.course.code)

    # Guard: an offering with no legal placement makes the whole model infeasible
    # via add_exactly_one([]). Fail loudly instead, naming the offending course(s).
    if unplaceable:
        return {
            "status": "infeasible",
            "objective": None,
            "entries": [],
            "infeasible_core": [f"no_assignment:{c}" for c in sorted(set(unplaceable))],
        }

    # ── Hard constraints ──────────────────────────────────────────────────────
    assumption_map: dict[str, any] = {}  # constraint_id → assumption BoolVar

    # Each offering must be assigned exactly once
    for o_idx in range(offering_count):
        model.add_exactly_one(vars_by_offering[o_idx])

    # Per-slot room capacity: concurrent classes of a type ≤ rooms of that type
    for vars_list in theory_by_slot.values():
        if len(vars_list) > n_theory_cap:
            model.add(sum(vars_list) <= n_theory_cap)
    for vars_list in lab_by_slot.values():
        if len(vars_list) > n_lab_cap:
            model.add(sum(vars_list) <= n_lab_cap)

    # No teacher in two places at once
    for vars_list in by_faculty_slot.values():
        if len(vars_list) > 1:
            model.add(sum(vars_list) <= 1)

    # No section/lab-group double-booked in the same slot
    for vars_list in by_section_slot.values():
        if len(vars_list) > 1:
            model.add(sum(vars_list) <= 1)

    # A section's theory class and one of that section's OWN lab groups must not
    # collide — the lab-group students also attend the section theory. (Two
    # different lab groups of the same section may still run concurrently.)
    section_slot_groups: dict[tuple, dict] = {}
    for (sec_id, d, s, lg_id), vars_list in by_section_slot.items():
        section_slot_groups.setdefault((sec_id, d, s), {})[lg_id] = vars_list
    for bylg in section_slot_groups.values():
        theory_vars = bylg.get(None)
        if not theory_vars:
            continue
        for lg_id, lab_vars in bylg.items():
            if lg_id is None:
                continue
            model.add(sum(theory_vars) + sum(lab_vars) <= 1)

    # Faculty workload cap — at most fp.max_per_day classes per teacher per day
    by_faculty_day: dict[tuple, list] = {}
    for (f_idx, d, _s), vars_list in by_faculty_slot.items():
        by_faculty_day.setdefault((f_idx, d), []).extend(vars_list)
    for (f_idx, _d), vars_list in by_faculty_day.items():
        cap = faculty_list[f_idx].max_per_day or 4
        if len(vars_list) > cap:
            model.add(sum(vars_list) <= cap)

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

    # Extract solution — collect placed classes per (day, slot), grouped by type,
    # then hand out concrete rooms. Distinct index per slot ⇒ no room double-booking;
    # the per-slot capacity constraint guarantees index < pool size.
    placed_theory: dict[tuple, list] = {}
    placed_lab: dict[tuple, list] = {}
    for o_idx, offering in enumerate(data.offerings):
        for (f_idx, d, s), var in x[o_idx].items():
            if solver.boolean_value(var):
                rec = (offering, faculty_list[f_idx].id, d, s)
                bucket = placed_lab if offering.course.is_lab else placed_theory
                bucket.setdefault((d, s), []).append(rec)

    result_entries = []

    def _emit(buckets: dict, pool: list):
        for recs in buckets.values():
            for i, (offering, faculty_id, d, s) in enumerate(recs):
                room_id = pool[i] if i < len(pool) else pool[i % len(pool)]
                result_entries.append({
                    "course_id": offering.course.id,
                    "section_id": offering.section.id,
                    "lab_group_id": offering.lab_group.id if offering.lab_group else None,
                    "faculty_id": faculty_id,
                    "room_id": room_id,
                    "day": d,
                    "slot": s,
                    "is_lab": offering.course.is_lab,
                    "locked": False,
                    "source": "solver",
                })

    _emit(placed_theory, theory_pool)
    _emit(placed_lab, lab_room_ids)

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
        if f_idx is None:
            continue

        # The (f, d, s) combo may have been pruned away (e.g. ineligible now).
        # Rooms are not solver variables, so room is not pinned here.
        var = x[o_idx].get((f_idx, entry.day, entry.slot))
        if var is None:
            continue

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
                # Use new values for pinning
                new_day = pinned_change.new_day if pinned_change.new_day is not None else entry.day
                new_slot = pinned_change.new_slot if pinned_change.new_slot is not None else entry.slot
                new_f_id = pinned_change.new_faculty_id or entry.faculty_id
                nf_idx = faculty_idx.get(new_f_id)
                # Find o_idx for this entry
                for o_idx, offering in enumerate(data.offerings):
                    if (offering.section.id == entry.section_id and
                            offering.course.id == entry.course_id):
                        if nf_idx is not None:
                            var = x[o_idx].get((nf_idx, new_day, new_slot))
                            if var is not None:
                                model.add(var == 1)
                        break
                break


def _add_warm_hints(model, x, data, faculty_list, room_list, faculty_idx, room_idx):
    """Provide previous solution as hints to speed up re-solve."""
    for entry in data.prev_entries:
        f_idx = faculty_idx.get(entry.faculty_id)
        if f_idx is None:
            continue
        for o_idx, offering in enumerate(data.offerings):
            if (offering.section.id == entry.section_id and
                    offering.course.id == entry.course_id):
                var = x[o_idx].get((f_idx, entry.day, entry.slot))
                if var is not None:
                    model.add_hint(var, 1)
                break


# ── Constraint registry ───────────────────────────────────────────────────────

def _build_max_per_day(model, x, data, faculty_list, room_list, faculty_idx, room_idx,
                       scope, params, assumption):
    limit = int(params.get("limit", 4))
    # Group created vars by (faculty, day)
    by_fd: dict[tuple, list] = {}
    for cell in x.values():
        for (f_idx, d, _s), var in cell.items():
            by_fd.setdefault((f_idx, d), []).append(var)
    for day_vars in by_fd.values():
        if day_vars:
            model.add(sum(day_vars) <= limit).only_enforce_if(assumption)


def _build_consecutive_limit(model, x, data, faculty_list, room_list, faculty_idx, room_idx,
                              scope, params, assumption):
    limit = int(params.get("limit", 2))
    # Group created vars by (faculty, day) → {slot: [vars]}
    by_fd_s: dict[tuple, dict] = {}
    for cell in x.values():
        for (f_idx, d, s), var in cell.items():
            by_fd_s.setdefault((f_idx, d), {}).setdefault(s, []).append(var)
    for slot_map in by_fd_s.values():
        for s_start in range(data.n_slots - limit):
            window_vars = [
                v
                for s in range(s_start, s_start + limit + 1)
                for v in slot_map.get(s, [])
            ]
            if window_vars:
                model.add(sum(window_vars) <= limit).only_enforce_if(assumption)


CONSTRAINT_BUILDERS = {
    "max_classes_per_day": _build_max_per_day,
    "consecutive_limit": _build_consecutive_limit,
}


def _soft_pref_slot(model, x, data, faculty_list, room_list, faculty_idx, room_idx,
                    scope, params, weight, penalty_terms):
    # Penalise any class a teacher with a preferred slot is given outside it.
    for cell in x.values():
        for (f_idx, _d, s), var in cell.items():
            pref_s = faculty_list[f_idx].pref_slot
            if pref_s is not None and s != pref_s:
                penalty_terms.append(weight * var)


def _soft_online_penalty(model, x, data, faculty_list, room_list, faculty_idx, room_idx,
                         scope, params, weight, penalty_terms):
    # Rooms are assigned in a post-pass (THEORY preferred over ONLINE), so online
    # usage is already minimised structurally; there are no room decision vars to
    # penalise here. Kept as a registered no-op so the constraint type stays valid.
    return


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
        from app.services import skill_loader
        settings = get_settings()
        ollama_url = getattr(settings, "ollama_base_url", "http://localhost:11434")

        # Skill grounding (day/slot indexing, reference resolution, examples); falls back to
        # the inline schema instructions below when the skill tree isn't shipped.
        _fallback_rules = (
            "You are a timetable assistant. "
            "Return ONLY valid JSON matching this schema: "
            '{"entry_id": "<uuid or null>", "new_day": <0-5 or null>, "new_slot": <int or null>, '
            '"new_faculty_id": "<uuid or null>", "new_room_id": "<uuid or null>", "lock": true}. '
            "Use null for fields that don't change. Do not explain."
        )
        rules = skill_loader.grounding("timetable-nl-edit", fallback=_fallback_rules)

        context_summary = json.dumps(entries_context[:20], default=str)
        prompt = (
            f"{rules}\n\n"
            f"Current entries (first 20): {context_summary}\n\n"
            f"User command: {text}\n\n"
            "Return ONLY the JSON object, no explanation."
        )

        # Prefer Gemini when configured; fall back to local Ollama.
        from app.services import gemini_client
        raw = await gemini_client.generate(prompt, temperature=0.1, timeout=15.0)
        if raw is None:
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
