"""CP-SAT timetable solver with registry-driven constraints.

Scale architecture: the term is solved **per batch** (batches are course-
disjoint; they couple only through faculty time, room capacity, and faculty
count-limits). Each batch group is a small CP-SAT model solved sequentially;
resources consumed by earlier groups are passed forward as `Reservations`
constants. This keeps peak model size ~1/n_batches of the old monolith, which
is what let a 9-batch term OOM a small container. The monolith path is kept
for small inputs (`solver_decompose_threshold`) and as an escalation fallback.

Solves run in a spawned subprocess by default (`SOLVER_ISOLATION=process`) so
an OOM kill takes down the child, not the API — the job then fails with
`solver_oom` instead of orphaning at 10%.
"""
import asyncio
import json
import logging
import math
import multiprocessing
import time
import uuid
from collections import deque
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.timetable import (
    TimetableTerm, TimetableBatch, TimetableSection, TimetableLabGroup,
    TimetableRoom, TimetableCourse, TimetableFacultyProfile,
    TimetableCourseOffering, TimetableTeacherEligibility,
    TimetableConstraint, TimetableEntry,
)
from app.schemas.timetable import SolveRequest, EntryEdit
from app.services import timetable_svc
from app.services.timetable_solver_types import (
    CourseD, SectionD, LabGroupD, FacultyD, RoomD, ConstraintD, EntryD,
    Reservations, build_reservations, to_entry_d,
)

logger = logging.getLogger(__name__)

# Diagnostics that mean class sessions would be silently dropped from the
# model (the old behavior behind the misleading "no_offerings" core), or that
# the instance is provably infeasible before building a model (capacity
# pre-checks — the solver would only burn its budget/memory proving it). A
# solve must fail fast on these with actionable cores.
_BLOCKING_DIAGNOSTIC_PREFIXES = (
    "no_sections_for_batch:",
    "no_lab_groups_for_section:",
    "insufficient_teacher_capacity:",
    "sole_teacher_overload:",
    "insufficient_group_capacity:",
)

# ── Data containers ───────────────────────────────────────────────────────────

@dataclass(frozen=True)
class OfferingSlot:
    """One class occurrence that needs to be placed (copy_idx handles weekly_classes > 1)."""
    offering_id: uuid.UUID
    course: CourseD
    section: SectionD
    lab_group: LabGroupD | None
    copy_idx: int

@dataclass
class SolverData:
    """Everything the solver needs, as plain picklable data (no ORM, no session)."""
    term_id: uuid.UUID
    term_name: str
    tenant_id: uuid.UUID | None
    n_days: int
    n_slots: int
    offerings: list[OfferingSlot] = field(default_factory=list)
    faculty: list[FacultyD] = field(default_factory=list)
    rooms: list[RoomD] = field(default_factory=list)
    constraints: list[ConstraintD] = field(default_factory=list)
    # Maps eligible faculty for each course_id
    eligible: dict[uuid.UUID, list[uuid.UUID]] = field(default_factory=dict)
    # Existing entries for warm-start / perturbation
    prev_entries: list[EntryD] = field(default_factory=list)
    batch_names: dict[uuid.UUID, str] = field(default_factory=dict)
    batch_id_by_section: dict[uuid.UUID, uuid.UUID] = field(default_factory=dict)
    # Machine-readable data problems detected at load time (see diagnose notes)
    diagnostics: list[str] = field(default_factory=list)


def _teacher_capacity(f: FacultyD, n_days: int) -> int:
    """Weekly sessions a teacher can physically hold: available days × max/day."""
    avail = n_days - sum(1 for d in f.off_days if 0 <= d < n_days)
    return max(avail, 0) * max(f.max_per_day, 0)


def _find_capacity_gap(
    demand: dict[uuid.UUID, int],
    pools: dict[uuid.UUID, list[uuid.UUID]],
    caps: dict[uuid.UUID, int],
) -> tuple[list[uuid.UUID], list[uuid.UUID], int, int] | None:
    """Decide the counting relaxation of teacher capacity exactly, by max-flow.

    Network: source → course (cap = weekly sessions) → eligible teacher →
    sink (cap = available days × max/day). If max-flow < total demand then no
    assignment of sessions to teachers exists even before considering the
    time grid, and the min-cut names the tight group: returns
    (courses, teachers, required, capacity) for a Hall-violating set — a
    group of courses whose combined demand exceeds what the union of their
    eligible teachers can teach. Returns None when the relaxation is
    satisfiable. Sizes here are tiny (tens of nodes), Dinic is instant.
    """
    course_ids = sorted(demand, key=str)
    teacher_ids = sorted({t for c in course_ids for t in pools.get(c, [])}, key=str)
    n = 2 + len(course_ids) + len(teacher_ids)
    src, snk = 0, n - 1
    c_node = {c: 1 + i for i, c in enumerate(course_ids)}
    t_node = {t: 1 + len(course_ids) + i for i, t in enumerate(teacher_ids)}

    adj: list[list[int]] = [[] for _ in range(n)]
    edges: list[list[int]] = []  # [to, residual_cap]; edge i^1 is the reverse

    def _add(u: int, v: int, cap: int) -> None:
        adj[u].append(len(edges)); edges.append([v, cap])
        adj[v].append(len(edges)); edges.append([u, 0])

    total = 0
    for c in course_ids:
        _add(src, c_node[c], demand[c])
        total += demand[c]
        for t in pools.get(c, []):
            _add(c_node[c], t_node[t], demand[c])
    for t in teacher_ids:
        _add(t_node[t], snk, caps.get(t, 0))

    flow = 0
    while True:  # Dinic: BFS levels, then blocking DFS augmentation
        level = [-1] * n
        level[src] = 0
        dq = deque([src])
        while dq:
            u = dq.popleft()
            for eid in adj[u]:
                v, cap = edges[eid]
                if cap > 0 and level[v] < 0:
                    level[v] = level[u] + 1
                    dq.append(v)
        if level[snk] < 0:
            break
        it = [0] * n

        def _dfs(u: int, pushed: int) -> int:
            if u == snk:
                return pushed
            while it[u] < len(adj[u]):
                eid = adj[u][it[u]]
                v, cap = edges[eid]
                if cap > 0 and level[v] == level[u] + 1:
                    got = _dfs(v, min(pushed, cap))
                    if got:
                        edges[eid][1] -= got
                        edges[eid ^ 1][1] += got
                        return got
                it[u] += 1
            return 0

        while (pushed := _dfs(src, 1 << 60)):
            flow += pushed

    if flow >= total:
        return None

    # Min-cut certificate: courses reachable from the source in the residual
    # graph form the violating set W, the reachable teachers are N(W).
    seen = [False] * n
    seen[src] = True
    dq = deque([src])
    while dq:
        u = dq.popleft()
        for eid in adj[u]:
            v, cap = edges[eid]
            if cap > 0 and not seen[v]:
                seen[v] = True
                dq.append(v)
    w_courses = [c for c in course_ids if seen[c_node[c]]]
    w_teachers = [t for t in teacher_ids if seen[t_node[t]]]
    required = sum(demand[c] for c in w_courses)
    capacity = sum(caps.get(t, 0) for t in w_teachers)
    return w_courses, w_teachers, required, capacity


async def load_solver_data(db: AsyncSession, term_id: uuid.UUID, seed_version: int | None = None) -> SolverData:
    """Load all scheduling data for a term, scoped to what the term references.

    Courses, sections, lab groups, and eligibility are derived from the term's
    offerings; rooms and faculty are filtered to the term's tenant (rows with a
    NULL tenant count as global). This keeps other tenants/terms out of the
    model entirely.
    """
    term_r = await db.execute(select(TimetableTerm).where(TimetableTerm.id == term_id))
    term = term_r.scalars().first()
    if not term:
        raise ValueError(f"Term {term_id} not found")

    config = await timetable_svc.get_schedule_config(db, term_id=term_id)
    if not config:
        raise ValueError("Schedule config not found — set days and slots first")

    n_days = len(config.days)
    n_slots = len(config.slots)

    def _tenant_scoped(q, col):
        if term.tenant_id is not None:
            return q.where(or_(col == term.tenant_id, col.is_(None)))
        return q

    # Load rooms + faculty (tenant-scoped)
    rooms_r = await db.execute(_tenant_scoped(select(TimetableRoom), TimetableRoom.tenant_id))
    rooms = [RoomD(id=r.id, name=r.name, room_type=r.room_type) for r in rooms_r.scalars().all()]

    faculty_r = await db.execute(_tenant_scoped(
        select(TimetableFacultyProfile).where(TimetableFacultyProfile.active == True),
        TimetableFacultyProfile.tenant_id,
    ))
    faculty = [
        FacultyD(
            id=fp.id, name=fp.name or fp.email,
            off_days=tuple(fp.off_days or []),
            max_per_day=fp.max_per_day or 4, pref_slot=fp.pref_slot,
        )
        for fp in faculty_r.scalars().all()
    ]
    faculty_ids = {fp.id for fp in faculty}

    # Load offerings for this term, then everything they reference
    off_r = await db.execute(
        select(TimetableCourseOffering).where(TimetableCourseOffering.term_id == term_id)
    )
    raw_offerings = list(off_r.scalars().all())
    offered_course_ids = {o.course_id for o in raw_offerings}
    offered_batch_ids = {o.batch_id for o in raw_offerings}

    courses_by_id: dict[uuid.UUID, CourseD] = {}
    if offered_course_ids:
        courses_r = await db.execute(
            select(TimetableCourse).where(TimetableCourse.id.in_(offered_course_ids))
        )
        courses_by_id = {
            c.id: CourseD(id=c.id, code=c.code, is_lab=c.is_lab, weekly_classes=c.weekly_classes)
            for c in courses_r.scalars().all()
        }

    batch_names: dict[uuid.UUID, str] = {}
    if offered_batch_ids:
        batches_r = await db.execute(
            select(TimetableBatch).where(TimetableBatch.id.in_(offered_batch_ids))
        )
        batch_names = {b.id: b.name for b in batches_r.scalars().all()}

    sections_by_batch: dict[uuid.UUID, list[SectionD]] = {}
    batch_id_by_section: dict[uuid.UUID, uuid.UUID] = {}
    if offered_batch_ids:
        secs_r = await db.execute(
            select(TimetableSection).where(TimetableSection.batch_id.in_(offered_batch_ids))
        )
        for s in secs_r.scalars().all():
            sec = SectionD(id=s.id, batch_id=s.batch_id, name=s.name)
            sections_by_batch.setdefault(s.batch_id, []).append(sec)
            batch_id_by_section[s.id] = s.batch_id

    lab_groups_by_section: dict[uuid.UUID, list[LabGroupD]] = {}
    if batch_id_by_section:
        lgs_r = await db.execute(
            select(TimetableLabGroup).where(TimetableLabGroup.section_id.in_(batch_id_by_section.keys()))
        )
        for lg in lgs_r.scalars().all():
            lab_groups_by_section.setdefault(lg.section_id, []).append(
                LabGroupD(id=lg.id, name=lg.name)
            )

    # Eligibility, restricted to offered courses and loaded (active, in-tenant) faculty
    eligible: dict[uuid.UUID, list[uuid.UUID]] = {}
    if offered_course_ids:
        elig_r = await db.execute(
            select(TimetableTeacherEligibility).where(
                TimetableTeacherEligibility.course_id.in_(offered_course_ids)
            )
        )
        for elig in elig_r.scalars().all():
            if elig.faculty_id in faculty_ids:
                eligible.setdefault(elig.course_id, []).append(elig.faculty_id)

    # Build OfferingSlot list + structural diagnostics
    diagnostics: list[str] = []
    if not raw_offerings:
        diagnostics.append("no_offerings_for_term")
    if not faculty:
        diagnostics.append("no_faculty")

    offering_slots: list[OfferingSlot] = []
    batches_missing_sections: set[uuid.UUID] = set()
    sections_missing_lab_groups: list[str] = []
    any_theory = any_lab = False
    for off in raw_offerings:
        course = courses_by_id.get(off.course_id)
        if not course:
            continue
        sections = sections_by_batch.get(off.batch_id, [])
        if not sections:
            batches_missing_sections.add(off.batch_id)
            continue
        if course.is_lab:
            any_lab = True
        else:
            any_theory = True
        for section in sections:
            if course.is_lab:
                lgs = lab_groups_by_section.get(section.id, [])
                if not lgs:
                    label = f"{batch_names.get(off.batch_id, '?')}/{section.name}"
                    if label not in sections_missing_lab_groups:
                        sections_missing_lab_groups.append(label)
                    continue
                for lg in lgs:
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

    for b_id in sorted(batches_missing_sections, key=lambda b: batch_names.get(b, "")):
        diagnostics.append(f"no_sections_for_batch:{batch_names.get(b_id, str(b_id))}")
    for label in sections_missing_lab_groups:
        diagnostics.append(f"no_lab_groups_for_section:{label}")
    if any_theory and not any(r.room_type in ("THEORY", "ONLINE") for r in rooms):
        diagnostics.append("no_theory_rooms")
    if any_lab and not any(r.room_type == "LAB" for r in rooms):
        diagnostics.append("no_lab_rooms")
    for c_id in offered_course_ids:
        course = courses_by_id.get(c_id)
        if course and not eligible.get(c_id):
            diagnostics.append(f"no_eligibility_for_course:{course.code}")

    # Capacity pre-check (a necessary condition): a course's weekly sessions
    # can never exceed what its eligible teachers can physically teach
    # (available days × max_per_day). Real data hit this — one teacher solely
    # eligible for a course offered to two batches (40 sessions vs 24 teachable)
    # — and the solver burned its whole budget (or the container's memory)
    # proving the inevitable. Catch it here with an actionable core instead.
    fac_by_id = {f.id: f for f in faculty}

    def _teach_cap(f) -> int:
        return _teacher_capacity(f, n_days)

    sessions_by_course: dict[uuid.UUID, int] = {}
    for slot in offering_slots:
        sessions_by_course[slot.course.id] = sessions_by_course.get(slot.course.id, 0) + 1

    for c_id in sorted(sessions_by_course, key=lambda c: courses_by_id[c].code):
        pool = [fac_by_id[fid] for fid in eligible.get(c_id, []) if fid in fac_by_id]
        if not pool:
            continue  # already reported as no_eligibility_for_course
        required, capacity = sessions_by_course[c_id], sum(_teach_cap(f) for f in pool)
        if required > capacity:
            diagnostics.append(
                f"insufficient_teacher_capacity:{courses_by_id[c_id].code}"
                f":{required}:{capacity}:{len(pool)}"
            )

    # Same bound per teacher, across every course they are the SOLE teacher of.
    sole_courses: dict[uuid.UUID, list[uuid.UUID]] = {}
    for c_id, pool_ids in eligible.items():
        if len(pool_ids) == 1 and c_id in sessions_by_course:
            sole_courses.setdefault(pool_ids[0], []).append(c_id)
    for fid, c_ids in sole_courses.items():
        f = fac_by_id.get(fid)
        if f is None or len(c_ids) < 2:
            continue  # the single-course case is the per-course check above
        required, cap = sum(sessions_by_course[c] for c in c_ids), _teach_cap(f)
        if required > cap:
            codes = "+".join(sorted(courses_by_id[c].code for c in c_ids))
            diagnostics.append(
                f"sole_teacher_overload:{f.name or fid}:{codes}:{required}:{cap}"
            )

    # Exact group check (counting relaxation, decided by max-flow): the two
    # bounds above only see one course or one sole teacher at a time and miss
    # shortages spread across courses that share a pool — real data passed
    # both while the term as a whole demanded 780 sessions from teachers who
    # can physically hold 768, so CP-SAT burned the whole budget failing to
    # prove the inevitable and the UI said "increase the time limit". The
    # min-cut names exactly the tight course group and its teacher pool.
    if not any(d.startswith(("insufficient_teacher_capacity:", "sole_teacher_overload:"))
               for d in diagnostics):
        flow_demand = {c: s for c, s in sessions_by_course.items() if eligible.get(c)}
        caps = {fid: _teach_cap(f) for fid, f in fac_by_id.items()}
        gap = _find_capacity_gap(flow_demand, eligible, caps)
        if gap is not None:
            w_courses, w_teachers, required, capacity = gap
            codes = "+".join(sorted(courses_by_id[c].code for c in w_courses))
            diagnostics.append(
                f"insufficient_group_capacity:{required}:{capacity}"
                f":{len(w_teachers)}:{codes}"
            )

    # Load constraints
    con_r = await db.execute(
        select(TimetableConstraint).where(
            TimetableConstraint.term_id == term_id,
            TimetableConstraint.enabled == True,
        )
    )
    constraints = [
        ConstraintD(
            id=str(c.id), constraint_type=c.constraint_type,
            scope=c.scope or {}, params=c.params or {},
            enforcement=c.enforcement, weight=c.weight, enabled=c.enabled,
        )
        for c in con_r.scalars().all()
    ]

    # Load previous entries for warm-start
    prev_entries: list[EntryD] = []
    if seed_version is not None:
        prev_entries = [
            to_entry_d(e) for e in await timetable_svc.list_entries(db, term_id, seed_version)
        ]

    return SolverData(
        term_id=term.id, term_name=term.name, tenant_id=term.tenant_id,
        n_days=n_days, n_slots=n_slots,
        offerings=offering_slots, faculty=faculty, rooms=rooms,
        constraints=constraints, eligible=eligible, prev_entries=prev_entries,
        batch_names=batch_names, batch_id_by_section=batch_id_by_section,
        diagnostics=diagnostics,
    )


# ── Solver ────────────────────────────────────────────────────────────────────

def solve(
    data: SolverData,
    time_limit_s: int = 60,
    pinned_change: EntryEdit | None = None,
    locked_entry_ids: set[uuid.UUID] | None = None,
    base_entries: list | None = None,
    reservations: Reservations | None = None,
    num_workers: int = 1,
    section_max_per_day: int = 0,
    section_consecutive_limit: int = 0,
    section_course_spread: bool = False,
    section_rule_weight: int = 1000,
) -> dict:
    """
    Run CP-SAT over ``data.offerings``. Returns:
      {status, objective, entries: list[dict], infeasible_core: list[str]}

    ``reservations`` holds resources already consumed by classes outside this
    model (other batch groups / carried entries) — treated as constants.
    """
    try:
        from ortools.sat.python import cp_model
    except ImportError:
        return {"status": "failed", "error": "ortools not installed", "entries": [], "infeasible_core": []}

    model = cp_model.CpModel()
    res = reservations or Reservations()

    offering_count = len(data.offerings)
    faculty_list = data.faculty
    room_list = data.rooms

    if not offering_count or not faculty_list or not room_list:
        core = list(data.diagnostics)
        if not core:
            if not offering_count:
                core.append("no_offerings_for_term")
            if not faculty_list:
                core.append("no_faculty")
            if not room_list:
                core.append("no_theory_rooms")
        return {"status": "infeasible", "objective": None, "entries": [], "infeasible_core": core}

    n_d = data.n_days
    n_s = data.n_slots

    # faculty index maps
    faculty_idx = {fp.id: i for i, fp in enumerate(faculty_list)}
    room_idx = {r.id: i for i, r in enumerate(room_list)}

    # Reservation constants keyed by faculty index (busy slots from other groups)
    busy_fds: set[tuple] = set()          # (f_idx, d, s)
    busy_fd_count: dict[tuple, int] = {}  # (f_idx, d) -> count
    for (fac_id, d, s) in res.faculty_busy:
        f_idx = faculty_idx.get(fac_id)
        if f_idx is None:
            continue
        busy_fds.add((f_idx, d, s))
        busy_fd_count[(f_idx, d)] = busy_fd_count.get((f_idx, d), 0) + 1
    res_ctx = {"busy_fds": busy_fds, "busy_fd_count": busy_fd_count}

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
    # the course, on days that are not one of that faculty's off-days and slots
    # not already reserved by another batch group.

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
        if is_lab and n_lab_cap == 0:
            unplaceable.append("no_lab_rooms")
            continue
        if not is_lab and n_theory_cap == 0:
            unplaceable.append("no_theory_rooms")
            continue
        if not allowed_f:
            unplaceable.append(f"no_eligibility_for_course:{offering.course.code}")
            continue
        lg_id = offering.lab_group.id if offering.lab_group else None
        slot_bucket = lab_by_slot if is_lab else theory_by_slot
        for f_idx in allowed_f:
            off = set(faculty_list[f_idx].off_days or [])
            for d in range(n_d):
                if d in off:
                    continue
                for s in range(n_s):
                    if (f_idx, d, s) in busy_fds:
                        continue
                    var = model.new_bool_var(f"x_{o_idx}_{f_idx}_{d}_{s}")
                    cell[(f_idx, d, s)] = var
                    by_faculty_slot.setdefault((f_idx, d, s), []).append(var)
                    by_section_slot.setdefault((offering.section.id, d, s, lg_id), []).append(var)
                    slot_bucket.setdefault((d, s), []).append(var)
        vars_by_offering[o_idx] = list(cell.values())
        if not cell:
            unplaceable.append(f"no_assignment:{offering.course.code}")

    # Guard: an offering with no legal placement makes the whole model infeasible
    # via add_exactly_one([]). Fail loudly instead, naming the cause.
    if unplaceable:
        return {
            "status": "infeasible",
            "objective": None,
            "entries": [],
            "infeasible_core": sorted(set(unplaceable)),
        }

    # ── Hard constraints ──────────────────────────────────────────────────────
    assumption_map: dict[str, any] = {}  # constraint_id → assumption BoolVar

    # Each offering must be assigned exactly once
    for o_idx in range(offering_count):
        model.add_exactly_one(vars_by_offering[o_idx])

    # Per-slot room capacity: concurrent classes of a type ≤ rooms of that type
    # still free after other groups' reservations.
    for key, vars_list in theory_by_slot.items():
        cap = max(n_theory_cap - res.theory_used.get(key, 0), 0)
        if len(vars_list) > cap:
            model.add(sum(vars_list) <= cap)
    for key, vars_list in lab_by_slot.items():
        cap = max(n_lab_cap - res.lab_used.get(key, 0), 0)
        if len(vars_list) > cap:
            model.add(sum(vars_list) <= cap)

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

    # Faculty workload cap — at most fp.max_per_day classes per teacher per day,
    # counting classes this teacher already has in other batch groups.
    by_faculty_day: dict[tuple, list] = {}
    for (f_idx, d, _s), vars_list in by_faculty_slot.items():
        by_faculty_day.setdefault((f_idx, d), []).extend(vars_list)
    for (f_idx, d), vars_list in by_faculty_day.items():
        cap = max((faculty_list[f_idx].max_per_day or 4) - busy_fd_count.get((f_idx, d), 0), 0)
        if len(vars_list) > cap:
            model.add(sum(vars_list) <= cap)

    # Registry-driven constraints — hard only; soft ones become penalties below
    for con in data.constraints:
        if not con.enabled or con.enforcement != "hard":
            continue
        builder = CONSTRAINT_BUILDERS.get(con.constraint_type)
        if builder is None:
            continue
        try:
            assumption = model.new_bool_var(f"assume_{con.id}")
            builder(model, x, data, faculty_list, room_list, faculty_idx, room_idx,
                    con.scope, con.params, assumption, res_ctx)
            assumption_map[str(con.id)] = assumption
        except Exception as exc:
            logger.warning(f"Constraint {con.constraint_type} build failed: {exc}")

    # ── Perturbation hints (minimal-perturbation re-solve) ────────────────────
    penalty_terms = []

    locked_offerings: set[int] = set()
    pinned_offering: int | None = None
    pin_lock = pinned_change.lock if pinned_change else True
    if base_entries:
        pert = _add_perturbation(
            model, x, data, faculty_list, room_list, faculty_idx, room_idx,
            base_entries, locked_entry_ids or set(), pinned_change, penalty_terms,
        )
        if pert["pin_error"]:
            # The requested move points at a combo with no decision variable
            # (teacher off-day / ineligible / out-of-range slot / reserved by
            # another batch). Fail loudly instead of returning an unchanged
            # timetable as "success".
            return {
                "status": "infeasible",
                "objective": None,
                "entries": [],
                "infeasible_core": [f"pin_impossible: {pert['pin_error']}"],
            }
        locked_offerings = pert["locked_offerings"]
        pinned_offering = pert["pinned_offering"]
    else:
        # Fresh solve → break the two big search symmetries. Not applied in
        # perturbation mode: an existing (possibly hand-edited) solution may
        # violate them, and pinning + these constraints could contradict.
        _add_symmetry_breaking(model, x, data, n_s)

    # ── Soft constraints (penalties) ──────────────────────────────────────────
    for con in data.constraints:
        if not con.enabled or con.enforcement != "soft":
            continue
        soft_builder = SOFT_BUILDERS.get(con.constraint_type)
        if soft_builder:
            try:
                soft_builder(model, x, data, faculty_list, room_list, faculty_idx, room_idx,
                             con.scope, con.params, con.weight or 1, penalty_terms, res_ctx)
            except Exception as exc:
                logger.warning(f"Soft constraint {con.constraint_type} build failed: {exc}")

    # Built-in section-centric spacing rules (student view). High-weight soft so
    # a timetable is always produced; relaxed (and flagged by validate) only when
    # a grid is too tight to space perfectly.
    _add_section_rules(
        model, x, data, by_section_slot, penalty_terms,
        section_max_per_day, section_consecutive_limit,
        section_course_spread, section_rule_weight,
    )

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
    # Per-batch models are small; extra portfolio workers mostly multiply CPU
    # and peak memory. Configurable via SOLVER_NUM_WORKERS (default 1).
    solver.parameters.num_search_workers = max(int(num_workers), 1)
    status = solver.solve(model)

    status_name = solver.status_name(status)

    infeasible_core: list[str] = []
    if status == cp_model.INFEASIBLE and assumption_map:
        try:
            # Returns literal indices (ints); a positive literal's index equals
            # its BoolVar's index. Map those back to constraint IDs.
            core = solver.sufficient_assumptions_for_infeasibility()
            reverse_map = {v.index: k for k, v in assumption_map.items()}
            infeasible_core = [
                reverse_map[idx]
                for idx in (lit if isinstance(lit, int) else lit.index for lit in core)
                if idx in reverse_map
            ]
        except Exception:
            logger.warning("Could not extract infeasible core", exc_info=True)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return {
            "status": status_name.lower(),
            "objective": None,
            "entries": [],
            "infeasible_core": infeasible_core,
        }

    # Extract solution — collect placed classes per (day, slot), grouped by type,
    # then hand out concrete rooms. Distinct index per slot ⇒ no room double-booking;
    # the per-slot capacity constraint guarantees index < free-pool size. Rooms
    # already taken by other groups' entries in the same slot are excluded.
    placed_theory: dict[tuple, list] = {}
    placed_lab: dict[tuple, list] = {}
    for o_idx, offering in enumerate(data.offerings):
        for (f_idx, d, s), var in x[o_idx].items():
            if solver.boolean_value(var):
                rec = (o_idx, offering, faculty_list[f_idx].id, d, s)
                bucket = placed_lab if offering.course.is_lab else placed_theory
                bucket.setdefault((d, s), []).append(rec)

    result_entries = []

    def _emit(buckets: dict, pool: list):
        for key, recs in buckets.items():
            used = res.rooms_used.get(key, set())
            avail = [rid for rid in pool if rid not in used] or list(pool)
            for i, (o_idx, offering, faculty_id, d, s) in enumerate(recs):
                room_id = avail[i] if i < len(avail) else avail[i % len(avail)]
                # Locks must survive into the new version, or the next re-solve
                # silently moves cells the admin pinned down.
                locked = o_idx in locked_offerings or (o_idx == pinned_offering and pin_lock)
                result_entries.append({
                    "course_id": offering.course.id,
                    "section_id": offering.section.id,
                    "lab_group_id": offering.lab_group.id if offering.lab_group else None,
                    "faculty_id": faculty_id,
                    "room_id": room_id,
                    "day": d,
                    "slot": s,
                    "is_lab": offering.course.is_lab,
                    "locked": locked,
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


def _add_symmetry_breaking(model, x, data: SolverData, n_s: int) -> None:
    """Break the two dominant symmetries on fresh solves (S-5).

    1. Same teacher for every weekly copy of a course-section(-lab-group): what
       universities want anyway, and it collapses the teacher-permutation space.
    2. Weekly copies are time-ordered (copy 0 earlier in the week than copy 1),
       killing the copy-permutation symmetry.
    """
    copies: dict[tuple, list[tuple[int, int]]] = {}
    for o_idx, offering in enumerate(data.offerings):
        lg_id = offering.lab_group.id if offering.lab_group else None
        key = (offering.offering_id, offering.section.id, lg_id)
        copies.setdefault(key, []).append((offering.copy_idx, o_idx))

    for group in copies.values():
        if len(group) < 2:
            continue
        group.sort()
        o_idxs = [o for _, o in group]

        # (1) same teacher across copies
        f_present: set[int] = set()
        for o in o_idxs:
            f_present.update(f for (f, _d, _s) in x[o].keys())
        first = o_idxs[0]
        for other in o_idxs[1:]:
            for f in f_present:
                lhs = [v for (ff, _d, _s), v in x[first].items() if ff == f]
                rhs = [v for (ff, _d, _s), v in x[other].items() if ff == f]
                model.add(sum(lhs) == sum(rhs))

        # (2) copies in strict week order (also ⇒ distinct times)
        prev_t = None
        for o in o_idxs:
            t = model.new_int_var(0, data.n_days * n_s - 1, f"t_{o}")
            model.add(t == sum(v * (d * n_s + s) for (_f, d, s), v in x[o].items()))
            if prev_t is not None:
                model.add(prev_t < t)
            prev_t = t


def _add_section_rules(
    model, x, data: SolverData, by_section_slot: dict, penalty_terms: list,
    max_per_day: int, consecutive_limit: int, course_spread: bool, weight: int,
) -> None:
    """Section-centric spacing penalties — what a *student* experiences.

    A student's day = the section's theory classes + their own lab group's labs
    (two lab groups of one section may run concurrently). So we build one
    "attendance stream" per (section, lab_group): the section's theory vars plus
    that group's lab vars; a section with no labs gets a single theory-only
    stream. Every class a section attends lives in one batch group, so these are
    self-contained — no cross-group reservations needed.

    All three are high-weight soft penalties (``weight`` dominates the small
    preference penalties): the solver honours them whenever a spacing exists and
    relaxes them minimally otherwise, so a timetable is always produced. Each
    rule is skipped when its knob is 0 / False, or when ``weight`` <= 0.
    """
    if weight <= 0:
        return

    # (section_id) -> {lg_id -> {(day, slot) -> [vars]}}
    by_section: dict[uuid.UUID, dict] = {}
    for (sec_id, d, s, lg_id), vars_list in by_section_slot.items():
        by_section.setdefault(sec_id, {}).setdefault(lg_id, {}) \
            .setdefault((d, s), []).extend(vars_list)

    for sec_id, by_lg in by_section.items():
        theory = by_lg.get(None, {})           # {(d,s): [vars]}
        lab_lgs = [lg for lg in by_lg if lg is not None]
        streams = lab_lgs if lab_lgs else [None]
        for lg in streams:
            # Merge theory + this stream's lab cells into one day -> {slot:[vars]}
            by_day: dict[int, dict] = {}
            for (d, s), v in theory.items():
                by_day.setdefault(d, {}).setdefault(s, []).extend(v)
            if lg is not None:
                for (d, s), v in by_lg[lg].items():
                    by_day.setdefault(d, {}).setdefault(s, []).extend(v)

            for d, slot_map in by_day.items():
                # (a) max classes per day for this student stream
                if max_per_day:
                    day_vars = [v for vs in slot_map.values() for v in vs]
                    if len(day_vars) > max_per_day:
                        excess = model.new_int_var(0, len(day_vars), f"sec_mpd_{sec_id}_{lg}_{d}")
                        model.add(sum(day_vars) - max_per_day <= excess)
                        penalty_terms.append(weight * excess)
                # (b) no more than `limit` back-to-back before a gap
                if consecutive_limit:
                    for s_start in range(data.n_slots - consecutive_limit):
                        window = range(s_start, s_start + consecutive_limit + 1)
                        window_vars = [v for s in window for v in slot_map.get(s, [])]
                        if len(window_vars) > consecutive_limit:
                            over = model.new_int_var(
                                0, len(window_vars), f"sec_cons_{sec_id}_{lg}_{d}_{s_start}")
                            model.add(sum(window_vars) - consecutive_limit <= over)
                            penalty_terms.append(weight * over)

    # (c) same course must not repeat within a day for a section. Uses offering
    # identity (lost by by_section_slot), grouped by (section, course, lg, day).
    if course_spread:
        by_scld: dict[tuple, list] = {}
        weekly: dict[uuid.UUID, int] = {}
        for o_idx, offering in enumerate(data.offerings):
            lg_id = offering.lab_group.id if offering.lab_group else None
            weekly[offering.course.id] = offering.course.weekly_classes
            for (_f, d, _s), var in x[o_idx].items():
                by_scld.setdefault((offering.section.id, offering.course.id, lg_id, d), []).append(var)
        n_days = max(data.n_days, 1)
        for (sec_id, course_id, lg_id, d), vars_list in by_scld.items():
            # ceil(weekly / days): normally 1; only >1 when a course meets more
            # times than there are days, so it isn't penalised for the unavoidable.
            cap = max(1, math.ceil(weekly.get(course_id, 1) / n_days))
            if len(vars_list) > cap:
                over = model.new_int_var(0, len(vars_list), f"sec_rep_{sec_id}_{course_id}_{lg_id}_{d}")
                model.add(sum(vars_list) - cap <= over)
                penalty_terms.append(weight * over)


def _add_perturbation(
    model, x, data, faculty_list, room_list, faculty_idx, room_idx,
    base_entries, locked_ids, pinned_change, penalty_terms,
) -> dict:
    """Add lock constraints + perturbation penalty + the pinned change.

    Returns {"locked_offerings": set[int], "pinned_offering": int | None,
    "pin_error": str | None}. A non-None pin_error means the requested change
    cannot be expressed in the model and the caller must abort the solve.

    Base entries that do not match any offering in this (possibly per-batch)
    model are skipped — they belong to other groups and are handled there.
    """
    result = {"locked_offerings": set(), "pinned_offering": None, "pin_error": None}

    # Build lookup: (section_id, lab_group_id, course_id, copy_idx) → offering_idx
    offering_key_map: dict[tuple, int] = {}
    for o_idx, offering in enumerate(data.offerings):
        lg_id = offering.lab_group.id if offering.lab_group else None
        key = (offering.section.id, lg_id, offering.course.id, offering.copy_idx)
        offering_key_map[key] = o_idx

    pinned_entry = None
    if pinned_change and pinned_change.entry_id:
        pinned_entry = next((e for e in base_entries if e.id == pinned_change.entry_id), None)
        if pinned_entry is None:
            result["pin_error"] = "entry not found in the base version"
            return result

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

        # The entry being moved is pinned at its NEW position below — pinning
        # or rewarding its old position here would fight (or contradict) that.
        if pinned_entry is not None and entry.id == pinned_entry.id:
            result["pinned_offering"] = o_idx
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
            result["locked_offerings"].add(o_idx)
        else:
            # Movement penalty (weight 5 = strongly prefer not to move):
            # move ⇔ ¬var, so any relocation of this class costs 5.
            move = model.new_bool_var(f"move_{o_idx}")
            model.add(var == 0).only_enforce_if(move)
            model.add(var == 1).only_enforce_if(move.negated())
            penalty_terms.append(5 * move)

    # Apply pinned change at its new coordinates
    if pinned_entry is not None:
        o_idx = result["pinned_offering"]
        if o_idx is None:
            result["pin_error"] = "no schedulable offering matches the entry (course/section changed?)"
            return result
        new_day = pinned_change.new_day if pinned_change.new_day is not None else pinned_entry.day
        new_slot = pinned_change.new_slot if pinned_change.new_slot is not None else pinned_entry.slot
        new_f_id = pinned_change.new_faculty_id or pinned_entry.faculty_id
        nf_idx = faculty_idx.get(new_f_id)
        if nf_idx is None:
            result["pin_error"] = "target teacher is not schedulable (inactive or unknown)"
            return result
        var = x[o_idx].get((nf_idx, new_day, new_slot))
        if var is None:
            result["pin_error"] = "target teacher/day/slot is unavailable (off-day, ineligible, busy, or out of range)"
            return result
        model.add(var == 1)

    return result


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
# Builders receive res_ctx = {"busy_fds": set[(f_idx,d,s)], "busy_fd_count":
# dict[(f_idx,d)→n]} so count-limits keep holding across batch groups: a
# teacher already given 3 classes on Monday by an earlier group has only
# (limit-3) left here. Pruning the busy vars alone would NOT enforce this.

def _build_max_per_day(model, x, data, faculty_list, room_list, faculty_idx, room_idx,
                       scope, params, assumption, res_ctx):
    limit = int(params.get("limit", 4))
    busy_fd = res_ctx["busy_fd_count"]
    # Group created vars by (faculty, day)
    by_fd: dict[tuple, list] = {}
    for cell in x.values():
        for (f_idx, d, _s), var in cell.items():
            by_fd.setdefault((f_idx, d), []).append(var)
    for (f_idx, d), day_vars in by_fd.items():
        cap = max(limit - busy_fd.get((f_idx, d), 0), 0)
        if len(day_vars) > cap:
            model.add(sum(day_vars) <= cap).only_enforce_if(assumption)


def _build_consecutive_limit(model, x, data, faculty_list, room_list, faculty_idx, room_idx,
                              scope, params, assumption, res_ctx):
    limit = int(params.get("limit", 2))
    busy_fds = res_ctx["busy_fds"]
    # Group created vars by (faculty, day) → {slot: [vars]}
    by_fd_s: dict[tuple, dict] = {}
    for cell in x.values():
        for (f_idx, d, s), var in cell.items():
            by_fd_s.setdefault((f_idx, d), {}).setdefault(s, []).append(var)
    for (f_idx, d), slot_map in by_fd_s.items():
        for s_start in range(data.n_slots - limit):
            window = range(s_start, s_start + limit + 1)
            reserved = sum(1 for s in window if (f_idx, d, s) in busy_fds)
            window_vars = [v for s in window for v in slot_map.get(s, [])]
            cap = max(limit - reserved, 0)
            if len(window_vars) > cap:
                model.add(sum(window_vars) <= cap).only_enforce_if(assumption)


CONSTRAINT_BUILDERS = {
    "max_classes_per_day": _build_max_per_day,
    "consecutive_limit": _build_consecutive_limit,
}


def _soft_pref_slot(model, x, data, faculty_list, room_list, faculty_idx, room_idx,
                    scope, params, weight, penalty_terms, res_ctx):
    # Penalise any class a teacher with a preferred slot is given outside it.
    for cell in x.values():
        for (f_idx, _d, s), var in cell.items():
            pref_s = faculty_list[f_idx].pref_slot
            if pref_s is not None and s != pref_s:
                penalty_terms.append(weight * var)


def _soft_online_penalty(model, x, data, faculty_list, room_list, faculty_idx, room_idx,
                         scope, params, weight, penalty_terms, res_ctx):
    # Rooms are assigned in a post-pass (THEORY preferred over ONLINE), so online
    # usage is already minimised structurally; there are no room decision vars to
    # penalise here. Kept as a registered no-op so the constraint type stays valid.
    return


def _soft_max_per_day(model, x, data, faculty_list, room_list, faculty_idx, room_idx,
                      scope, params, weight, penalty_terms, res_ctx):
    # Penalise each class beyond `limit` a teacher gets on one day (counting
    # classes already committed in other batch groups).
    limit = int(params.get("limit", 4))
    busy_fd = res_ctx["busy_fd_count"]
    by_fd: dict[tuple, list] = {}
    for cell in x.values():
        for (f_idx, d, _s), var in cell.items():
            by_fd.setdefault((f_idx, d), []).append(var)
    for (f_idx, d), day_vars in by_fd.items():
        reserved = busy_fd.get((f_idx, d), 0)
        if len(day_vars) + reserved <= limit:
            continue
        excess = model.new_int_var(0, len(day_vars) + reserved, f"soft_mpd_{f_idx}_{d}")
        model.add(sum(day_vars) + reserved - limit <= excess)
        penalty_terms.append(weight * excess)


def _soft_consecutive(model, x, data, faculty_list, room_list, faculty_idx, room_idx,
                      scope, params, weight, penalty_terms, res_ctx):
    # Penalise each class beyond `limit` inside any window of limit+1 slots.
    limit = int(params.get("limit", 2))
    busy_fds = res_ctx["busy_fds"]
    by_fd_s: dict[tuple, dict] = {}
    for cell in x.values():
        for (f_idx, d, s), var in cell.items():
            by_fd_s.setdefault((f_idx, d), {}).setdefault(s, []).append(var)
    for (f_idx, d), slot_map in by_fd_s.items():
        for s_start in range(data.n_slots - limit):
            window = range(s_start, s_start + limit + 1)
            reserved = sum(1 for s in window if (f_idx, d, s) in busy_fds)
            window_vars = [v for s in window for v in slot_map.get(s, [])]
            if len(window_vars) + reserved <= limit:
                continue
            over = model.new_int_var(0, len(window_vars) + reserved, f"soft_cons_{f_idx}_{d}_{s_start}")
            model.add(sum(window_vars) + reserved - limit <= over)
            penalty_terms.append(weight * over)


SOFT_BUILDERS = {
    "pref_slot_reward": _soft_pref_slot,
    "online_penalty": _soft_online_penalty,
    "max_classes_per_day": _soft_max_per_day,
    "consecutive_limit": _soft_consecutive,
}


# ── Decomposition planning ────────────────────────────────────────────────────

def plan_groups(data: SolverData, strategy: str, threshold: int) -> list[list[OfferingSlot]]:
    """Split offerings into per-batch solve groups, tightest first.

    Tightness is teacher scarcity, not raw size: a batch whose course has one
    eligible teacher must solve while that teacher's week is still empty —
    solved last, earlier (wide) groups may already have reserved his slots and
    only an expensive merge can undo that. Size breaks ties.

    Returns a single group (monolith) when strategy says so or the term has few
    enough batches that decomposition buys nothing.
    """
    by_batch: dict[uuid.UUID, list[OfferingSlot]] = {}
    for slot in data.offerings:
        by_batch.setdefault(slot.section.batch_id, []).append(slot)

    if strategy == "monolith" or (strategy != "per_batch" and len(by_batch) <= threshold):
        return [list(data.offerings)]

    def _scarcity(g: list[OfferingSlot]) -> float:
        return sum(
            1.0 / max(len(data.eligible.get(o.course.id, ())), 1) for o in g
        )

    groups = sorted(
        by_batch.values(),
        key=lambda g: (-_scarcity(g), -len(g),
                       data.batch_names.get(g[0].section.batch_id, "")),
    )
    return groups


def split_budget(group_sizes: list[int], total_s: int, min_s: int = 5) -> list[int]:
    """Per-group time budgets proportional to group size, floored at min_s."""
    total_sessions = sum(group_sizes) or 1
    return [max(min_s, int(total_s * size / total_sessions)) for size in group_sizes]


def trim_eligible(
    data: SolverData,
    grp: list[OfferingSlot],
    reservations: Reservations | None,
    k: int,
    base_entries: list[EntryD] | None = None,
    pinned_change: EntryEdit | None = None,
) -> dict[uuid.UUID, list[uuid.UUID]] | None:
    """Cap the candidate-teacher pool per course for one group solve.

    Real rosters mark 100+ teachers eligible per course; every extra candidate
    multiplies BoolVars (course sessions × days × slots), peak memory, and the
    symmetric search plateau CP-SAT has to wade through. Keep the k candidates
    with the fewest reserved slots (stable roster order as tiebreak) so later
    groups naturally drift toward less-loaded teachers. Teachers already placed
    in base entries for a course — and a pin's target teacher — are always
    kept, so re-solves and pin edits stay expressible.

    Returns None when no course in the group exceeds k (solve with the full
    pool; the caller uses this to know a full-pool retry would change nothing).
    """
    if k <= 0:
        return None

    busy_count: dict[uuid.UUID, int] = {}
    if reservations is not None:
        for fid, _d, _s in reservations.faculty_busy:
            busy_count[fid] = busy_count.get(fid, 0) + 1

    # Term-wide demand pressure per teacher: a session of a 1-teacher course
    # weighs 1.0, a session of a 100-teacher course ~0.01. Used as a ranking
    # tiebreak so wide courses don't grab teachers that scarce courses (in
    # this or a later group) cannot do without.
    demand: dict[uuid.UUID, float] = {}
    for o in data.offerings:
        pool = data.eligible.get(o.course.id, ())
        if pool:
            w = 1.0 / len(pool)
            for fid in pool:
                demand[fid] = demand.get(fid, 0.0) + w

    must_keep: dict[uuid.UUID, set[uuid.UUID]] = {}
    for e in base_entries or []:
        if e.faculty_id is not None:
            must_keep.setdefault(e.course_id, set()).add(e.faculty_id)
    if pinned_change is not None and pinned_change.new_faculty_id:
        for cid in {o.course.id for o in grp}:
            must_keep.setdefault(cid, set()).add(pinned_change.new_faculty_id)

    out: dict[uuid.UUID, list[uuid.UUID]] = dict(data.eligible)
    trimmed_any = False
    for cid in {o.course.id for o in grp}:
        pool = data.eligible.get(cid, [])
        keep = must_keep.get(cid, set()) & set(pool)
        if len(pool) <= max(k, len(keep)):
            continue
        order = {fid: idx for idx, fid in enumerate(pool)}
        ranked = sorted(
            (fid for fid in pool if fid not in keep),
            key=lambda fid: (busy_count.get(fid, 0), demand.get(fid, 0.0), order[fid]),
        )
        kept = keep | set(ranked[: max(k - len(keep), 0)])
        out[cid] = [fid for fid in pool if fid in kept]
        trimmed_any = True
    return out if trimmed_any else None


def _batches_of(group: list[OfferingSlot]) -> set[uuid.UUID]:
    return {slot.section.batch_id for slot in group}


def _group_label(data: SolverData, group: list[OfferingSlot]) -> str:
    names = sorted(data.batch_names.get(b, str(b)) for b in _batches_of(group))
    return "+".join(names) if names else "?"


def _entry_to_row(e: EntryD) -> dict:
    """A carried-verbatim entry as insert kwargs (keeps locked/source/room)."""
    return {
        "course_id": e.course_id, "section_id": e.section_id,
        "lab_group_id": e.lab_group_id, "faculty_id": e.faculty_id,
        "room_id": e.room_id, "day": e.day, "slot": e.slot,
        "is_lab": e.is_lab, "locked": e.locked, "source": e.source,
    }


def _plan_pin_groups(
    data: SolverData, base: list[EntryD], pinned_entry: EntryD, pinned_change: EntryEdit,
) -> tuple[list[list[OfferingSlot]], list[EntryD]]:
    """Pin fast path: solve only the pinned entry's batch; carry the rest.

    If the pin's target (teacher, day, slot) is currently held by an entry in
    another batch, that batch joins the solve group (the monolith could resolve
    such ripples; a pure single-batch solve would report pin_impossible).
    """
    pin_batch = data.batch_id_by_section.get(pinned_entry.section_id)
    group_batches = {pin_batch}

    tgt_day = pinned_change.new_day if pinned_change.new_day is not None else pinned_entry.day
    tgt_slot = pinned_change.new_slot if pinned_change.new_slot is not None else pinned_entry.slot
    tgt_fac = pinned_change.new_faculty_id or pinned_entry.faculty_id
    for e in base:
        if e.faculty_id == tgt_fac and e.day == tgt_day and e.slot == tgt_slot:
            b = data.batch_id_by_section.get(e.section_id)
            if b is not None:
                group_batches.add(b)

    carried = [
        e for e in base
        if data.batch_id_by_section.get(e.section_id) not in group_batches
    ]
    group = [o for o in data.offerings if o.section.batch_id in group_batches]
    return [group], carried


# ── Executor isolation ────────────────────────────────────────────────────────

def _solve_worker(data: SolverData, kwargs: dict) -> dict:
    """Top-level entry point for the solver subprocess (spawn-picklable)."""
    return solve(data, **kwargs)


async def _solve_async(pool: ProcessPoolExecutor | None, data: SolverData, kwargs: dict) -> dict:
    loop = asyncio.get_event_loop()
    if pool is None:
        # Thread mode — call through the module global so tests can monkeypatch.
        return await loop.run_in_executor(None, lambda: solve(data, **kwargs))
    return await loop.run_in_executor(pool, _solve_worker, data, kwargs)


# ── Background job runner ─────────────────────────────────────────────────────

async def run_solve_job(
    job_id: uuid.UUID,
    db_factory,
    request: SolveRequest,
    pinned_change: EntryEdit | None = None,
    locked_entry_ids: set[uuid.UUID] | None = None,
    base_entries: list | None = None,
) -> None:
    """Background task — opens its own DB session. Never raises.

    Drives the per-batch decomposition: plan groups → solve sequentially with
    reservations → write real progress per group → escalate on infeasibility
    (pair-merge, then one monolith over the remainder) → insert all entries as
    one new result version.
    """
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

    settings = get_settings()
    pool: ProcessPoolExecutor | None = None
    try:
        async with db_factory() as db:
            data = await load_solver_data(
                db, request.term_id,
                seed_version=request.seed_from_version,
            )

        base: list[EntryD] = [to_entry_d(e) for e in (base_entries or [])]
        if pinned_change is not None and not pinned_change.entry_id:
            pinned_change = None  # empty change ⇒ plain perturbation re-solve

        # Structural data problems mean sessions would silently vanish from the
        # timetable — fail fast with actionable cores instead.
        blocking = [d for d in data.diagnostics if d.startswith(_BLOCKING_DIAGNOSTIC_PREFIXES)]
        if blocking:
            await _finish_job(db_factory, job_id, status="infeasible", progress=100,
                              solver_status="infeasible", infeasible_core=blocking)
            return

        pinned_entry: EntryD | None = None
        if pinned_change is not None:
            pinned_entry = next((e for e in base if e.id == pinned_change.entry_id), None)
            if pinned_entry is None:
                await _finish_job(
                    db_factory, job_id, status="infeasible", progress=100,
                    solver_status="infeasible",
                    infeasible_core=["pin_impossible: entry not found in the base version"],
                )
                return

        strategy = getattr(request, "strategy", None) or "auto"
        if pinned_entry is not None:
            groups, carried = _plan_pin_groups(data, base, pinned_entry, pinned_change)
        else:
            groups = plan_groups(data, strategy, settings.solver_decompose_threshold)
            carried = []

        base_by_batch: dict[uuid.UUID | None, list[EntryD]] = {}
        for e in base:
            base_by_batch.setdefault(data.batch_id_by_section.get(e.section_id), []).append(e)

        if settings.solver_isolation == "process":
            pool = ProcessPoolExecutor(
                max_workers=1, mp_context=multiprocessing.get_context("spawn")
            )

        total_sessions = sum(len(g) for g in groups) or 1
        committed: list[list[dict]] = []      # per solved group, parallel to groups[:i]
        statuses: list[str] = []
        tried_pair: set[frozenset] = set()
        widened: set[frozenset] = set()       # groups re-solving with a wider candidate pool
        extended: set[frozenset] = set()      # groups re-solving with the remaining budget
        final_merged = False
        failure: tuple[str, list[str]] | None = None
        deadline = time.monotonic() + request.time_limit_s * 1.5
        i = 0

        while i < len(groups):
            grp = groups[i]
            multi = len(groups) > 1
            if multi:
                # Heartbeat + real progress before each group solve — the row's
                # updated_at doubles as the orphan-reaper's liveness signal.
                await _write_job(
                    db_factory, job_id,
                    progress=10 + int(85 * i / len(groups)),
                    solver_status=f"batch {i + 1}/{len(groups)}"[:30],
                )
            key = frozenset(_batches_of(grp))

            # Reservations = carried entries + already-solved groups + (in a
            # no-pin perturbation) the still-standing base of unsolved groups.
            res_entries: list = list(carried)
            for c in committed:
                res_entries.extend(c)
            if base and pinned_entry is None:
                for g in groups[i + 1:]:
                    for b in _batches_of(g):
                        res_entries.extend(base_by_batch.get(b, []))
            reservations = build_reservations(res_entries) if res_entries else None

            # Wide real-world eligibility (100+ teachers/course) is what blew
            # up model size and memory at scale — cap candidates per course.
            # A retry widens the cap instead of dropping it entirely: a truly
            # uncapped merged-group model measured 1.5 GB on real data, which
            # is a guaranteed OOM on small containers.
            k = settings.solver_max_candidates
            if key in widened and k > 0:
                k = max(4 * k, 40)
            trimmed = trim_eligible(
                data, grp, reservations, k,
                base_entries=base or None,
                pinned_change=pinned_change if pinned_entry is not None else None,
            )
            slice_data = replace(data, offerings=grp,
                                 eligible=trimmed if trimmed is not None else data.eligible)

            budget = max(5, int(request.time_limit_s * len(grp) / total_sessions)) if multi \
                else request.time_limit_s
            if key in extended:
                # Retry after an UNKNOWN: proportional slice wasn't enough —
                # hand the group the rest of the wall-clock deadline (capped at
                # time_limit_s so the reaper's heartbeat-staleness window,
                # time_limit_s + 120s, can never fire on a live solve).
                budget = max(budget, min(int(deadline - time.monotonic()),
                                         request.time_limit_s))
            budget = max(5, min(budget, int(deadline - time.monotonic())))

            kwargs = dict(
                time_limit_s=budget,
                pinned_change=pinned_change if pinned_entry is not None else None,
                locked_entry_ids=locked_entry_ids,
                base_entries=base or None,
                reservations=reservations,
                num_workers=settings.solver_num_workers,
                section_max_per_day=settings.solver_section_max_per_day,
                section_consecutive_limit=settings.solver_section_consecutive_limit,
                section_course_spread=settings.solver_section_course_spread,
                section_rule_weight=settings.solver_section_rule_weight,
            )
            result = await _solve_async(pool, slice_data, kwargs)
            st = result["status"]

            if st in ("optimal", "feasible"):
                committed.append(result["entries"])
                statuses.append(st)
                i += 1
                continue

            if trimmed is not None and key not in widened and st in ("infeasible", "unknown"):
                # The cap may have hidden the teachers a solution needs —
                # retry this group with a wider pool before escalating.
                widened.add(key)
                continue

            cores = result.get("infeasible_core") or []
            if st == "unknown":
                if key not in extended and deadline - time.monotonic() > 5:
                    # No solution within the proportional slice; give the
                    # group the remaining budget before declaring defeat.
                    extended.add(key)
                    continue
                timeout_cores = [
                    "solver_timeout: no timetable found within the time limit"
                    " — increase the time limit and solve again",
                ]
                # A course group keeping its teacher pool >90% booked is the
                # usual reason a not-provably-infeasible instance still times
                # out — rerun the load-time flow check with capacities scaled
                # to 90% so the min-cut names the squeezed courses, instead of
                # only telling the admin to add time.
                demand: dict[uuid.UUID, int] = {}
                code_of: dict[uuid.UUID, str] = {}
                for off in data.offerings:
                    demand[off.course.id] = demand.get(off.course.id, 0) + 1
                    code_of[off.course.id] = off.course.code
                caps = {f.id: _teacher_capacity(f, data.n_days) for f in data.faculty}
                gap = _find_capacity_gap(
                    {c: s for c, s in demand.items() if data.eligible.get(c)},
                    data.eligible,
                    {fid: int(c * 0.9) for fid, c in caps.items()},
                )
                if gap is not None:
                    w_courses, w_teachers, required, _ = gap
                    capacity = sum(caps.get(t, 0) for t in w_teachers)
                    codes = "+".join(sorted(code_of[c] for c in w_courses))
                    timeout_cores.append(
                        f"high_utilization:{required}:{capacity}"
                        f":{len(w_teachers)}:{codes}"
                    )
                failure = ("unknown", timeout_cores)
                break

            if st == "infeasible" and multi:
                if i > 0 and key not in tried_pair and not final_merged:
                    # The previous group may have greedily taken this group's
                    # resources — merge the pair and re-solve them together.
                    tried_pair.add(key)
                    groups[i - 1:i + 1] = [groups[i - 1] + grp]
                    committed.pop()
                    statuses.pop()
                    i -= 1
                    continue
                if not final_merged and len(groups) - i > 1:
                    # Last resort inside the budget: one model over everything
                    # not yet committed.
                    groups[i:] = [[o for g in groups[i:] for o in g]]
                    final_merged = True
                    continue
                failure = (st, [f"batch {_group_label(data, grp)}: {c}" for c in cores])
                break

            failure = (st, cores)
            break

        if failure is not None:
            st, cores = failure
            job_status = st if st == "infeasible" else "failed"
            await _finish_job(
                db_factory, job_id, status=job_status, progress=100,
                solver_status=st[:30], infeasible_core=cores,
            )
            return

        # Persist: carried-verbatim entries (pin fast path) + all solved groups.
        entry_rows = [_entry_to_row(e) for e in carried]
        for c in committed:
            entry_rows.extend(c)
        objective = 0  # objectives are per-group; report their sum

        async with db_factory() as db:
            job = await timetable_svc.get_solve_job(db, job_id)
            if not job:
                return
            next_version = await timetable_svc.get_next_version(db, request.term_id)
            entries = [
                TimetableEntry(
                    tenant_id=job.tenant_id,
                    term_id=request.term_id,
                    result_version=next_version,
                    **e,
                )
                for e in entry_rows
            ]
            await timetable_svc.bulk_insert_entries(db, entries)
            final_status = "optimal" if all(s == "optimal" for s in statuses) else "feasible"
            await timetable_svc.update_solve_job(
                db, job,
                status=final_status,
                progress=100,
                solver_status=final_status,
                objective_value=objective,
                result_version=next_version,
                finished_at=datetime.now(timezone.utc),
                infeasible_core=[],
            )
    except BrokenProcessPool:
        # The solver child was killed (almost always the OOM killer). Without
        # process isolation this took down the API and orphaned the job at 10%.
        logger.error(f"Solve job {job_id}: solver subprocess died (OOM-killed?)")
        await _finish_job(
            db_factory, job_id, status="failed", progress=100,
            solver_status="solver_oom",
            infeasible_core=["solver process was killed — likely out of memory"],
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
    finally:
        if pool is not None:
            pool.shutdown(wait=False, cancel_futures=True)


async def _write_job(db_factory, job_id: uuid.UUID, **kwargs) -> None:
    """Best-effort intermediate job update (progress heartbeat)."""
    try:
        async with db_factory() as db:
            job = await timetable_svc.get_solve_job(db, job_id)
            if job:
                await timetable_svc.update_solve_job(db, job, **kwargs)
    except Exception:
        logger.warning(f"Solve job {job_id}: progress write failed", exc_info=True)


async def _finish_job(db_factory, job_id: uuid.UUID, **kwargs) -> None:
    """Terminal job update; adds finished_at."""
    kwargs.setdefault("finished_at", datetime.now(timezone.utc))
    await _write_job(db_factory, job_id, **kwargs)


# ── NL → EntryEdit ────────────────────────────────────────────────────────────

async def nl_to_entry_edit(text: str, entries_context: list[dict]) -> EntryEdit | None:
    """Parse a natural-language timetable command into an EntryEdit using Ollama."""
    try:
        from app.services import skill_loader

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

        context_summary = json.dumps(entries_context[:60], default=str)
        prompt = (
            f"{rules}\n\n"
            f"Current entries (first 60): {context_summary}\n\n"
            f"User command: {text}\n\n"
            "Return ONLY the JSON object, no explanation."
        )

        # Ollama (local) → Gemini → Groq; None when all providers are offline.
        from app.services import llm_client
        raw = await llm_client.generate(prompt, temperature=0.1, timeout=15.0)
        if raw is None:
            return None

        # Extract JSON from response (strips <think> blocks, brace-balanced)
        from app.services.llm_json import extract_json_object
        data = extract_json_object(raw)
        if data is None:
            return None
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
