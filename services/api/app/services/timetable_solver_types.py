"""Plain-data containers for the timetable solver.

The solver runs in a separate process at real scale (see SOLVER_ISOLATION), so
everything that crosses the executor boundary must be picklable without a DB
session attached. ORM rows are converted to these frozen dataclasses once, in
``load_solver_data`` / the router boundary, and never travel further.
"""
import uuid
from dataclasses import dataclass, field


@dataclass(frozen=True)
class CourseD:
    id: uuid.UUID
    code: str
    is_lab: bool
    weekly_classes: int
    credits: int = 0


@dataclass(frozen=True)
class SectionD:
    id: uuid.UUID
    batch_id: uuid.UUID
    name: str


@dataclass(frozen=True)
class LabGroupD:
    id: uuid.UUID
    name: str


@dataclass(frozen=True)
class FacultyD:
    id: uuid.UUID
    name: str | None
    off_days: tuple[int, ...]
    max_per_day: int
    pref_slot: int | None
    rank: str = "LECTURER"
    min_credits: int | None = None
    max_credits: int | None = None


@dataclass(frozen=True)
class RoomD:
    id: uuid.UUID
    name: str
    room_type: str  # THEORY | LAB | ONLINE


@dataclass(frozen=True)
class ConstraintD:
    id: str
    constraint_type: str
    scope: dict
    params: dict
    enforcement: str  # hard | soft
    weight: int | None
    enabled: bool


@dataclass(frozen=True)
class EntryD:
    """A persisted timetable entry, detached from the ORM."""
    id: uuid.UUID | None
    course_id: uuid.UUID
    section_id: uuid.UUID
    lab_group_id: uuid.UUID | None
    faculty_id: uuid.UUID
    room_id: uuid.UUID
    day: int
    slot: int
    is_lab: bool
    locked: bool
    source: str


def to_entry_d(e) -> EntryD:
    """Convert an ORM TimetableEntry (or anything with the same attrs) to EntryD."""
    if isinstance(e, EntryD):
        return e
    return EntryD(
        id=e.id, course_id=e.course_id, section_id=e.section_id,
        lab_group_id=e.lab_group_id, faculty_id=e.faculty_id, room_id=e.room_id,
        day=e.day, slot=e.slot, is_lab=e.is_lab, locked=e.locked, source=e.source,
    )


@dataclass
class Reservations:
    """Resources already consumed by classes outside the current sub-model.

    Built from previously-committed groups (per-batch decomposition) and from
    entries carried verbatim during a pinned re-solve. The solver treats these
    as constants: no variable is created on a busy faculty slot, per-slot room
    capacity is reduced, count-constraints (max_per_day / consecutive_limit)
    include the reserved counts, and the room post-pass never hands out a
    reserved room.
    """
    faculty_busy: set = field(default_factory=set)     # {(faculty_id, day, slot)}
    theory_used: dict = field(default_factory=dict)    # {(day, slot): count}
    lab_used: dict = field(default_factory=dict)       # {(day, slot): count}
    online_used: dict = field(default_factory=dict)    # {(day, slot): count} in ONLINE rooms
    rooms_used: dict = field(default_factory=dict)     # {(day, slot): set[room_id]}
    # Weekly credit load already committed per teacher, deduped per taught
    # (course, section, lab_group) so weekly copies don't multiply the credits.
    faculty_credits: dict = field(default_factory=dict)   # {faculty_id: credits}
    _credit_seen: set = field(default_factory=set)        # {(fac, course, section, lg)}

    def add_entry(self, e, *, credits_by_course: dict | None = None,
                  online_room_ids: set | None = None) -> None:
        """Reserve the resources of one placed class (EntryD or result dict)."""
        if isinstance(e, dict):
            fac, room, day, slot, is_lab = (
                e["faculty_id"], e["room_id"], e["day"], e["slot"], e["is_lab"]
            )
            course_id = e.get("course_id")
            section_id = e.get("section_id")
            lg_id = e.get("lab_group_id")
        else:
            fac, room, day, slot, is_lab = e.faculty_id, e.room_id, e.day, e.slot, e.is_lab
            course_id = e.course_id
            section_id = e.section_id
            lg_id = e.lab_group_id
        key = (day, slot)
        self.faculty_busy.add((fac, day, slot))
        bucket = self.lab_used if is_lab else self.theory_used
        bucket[key] = bucket.get(key, 0) + 1
        self.rooms_used.setdefault(key, set()).add(room)
        if online_room_ids and room in online_room_ids:
            self.online_used[key] = self.online_used.get(key, 0) + 1
        # Credit load: count a course's credits once per (teacher, course,
        # section, lab_group) regardless of how many weekly copies were placed.
        if credits_by_course and course_id in credits_by_course:
            ck = (fac, course_id, section_id, lg_id)
            if ck not in self._credit_seen:
                self._credit_seen.add(ck)
                self.faculty_credits[fac] = (
                    self.faculty_credits.get(fac, 0) + credits_by_course[course_id]
                )


def build_reservations(entries, *, credits_by_course: dict | None = None,
                       online_room_ids: set | None = None) -> Reservations:
    """Aggregate reservations from a list of EntryD / result dicts."""
    res = Reservations()
    for e in entries:
        res.add_entry(e, credits_by_course=credits_by_course,
                      online_room_ids=online_room_ids)
    return res
