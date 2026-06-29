import copy
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.routine import AcademicRoutine, RoutineStatus
from app.schemas.routines import RoutineCreate, RoutineUpdate
from app.services import export_svc

logger = logging.getLogger(__name__)

PAGE_SIZE = 20


async def list_routines(
    db: AsyncSession,
    department: str | None = None,
    batch: str | None = None,
    semester: str | None = None,
    status_filter: RoutineStatus | None = None,
    is_admin: bool = False,
    page: int = 1,
) -> list[AcademicRoutine]:
    q = select(AcademicRoutine)
    if not is_admin:
        q = q.where(AcademicRoutine.status == RoutineStatus.published)
    elif status_filter is not None:
        q = q.where(AcademicRoutine.status == status_filter)
    if department is not None:
        q = q.where(AcademicRoutine.department.ilike(f"%{department}%"))
    if batch is not None:
        q = q.where(AcademicRoutine.batch == batch)
    if semester is not None:
        q = q.where(AcademicRoutine.semester.ilike(f"%{semester}%"))
    q = q.order_by(AcademicRoutine.created_at.desc()).offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE)
    result = await db.execute(q)
    return list(result.scalars().all())


async def get_routine(
    db: AsyncSession,
    routine_id: uuid.UUID,
    is_admin: bool = False,
) -> AcademicRoutine | None:
    q = select(AcademicRoutine).where(AcademicRoutine.id == routine_id)
    if not is_admin:
        q = q.where(AcademicRoutine.status == RoutineStatus.published)
    result = await db.execute(q)
    return result.scalars().first()


async def create_routine(
    db: AsyncSession,
    data: RoutineCreate,
    created_by: uuid.UUID,
) -> AcademicRoutine:
    routine = AcademicRoutine(
        tenant_id=data.tenant_id,
        department=data.department,
        batch=data.batch,
        semester=data.semester,
        academic_year=data.academic_year,
        title=data.title,
        slots=[s.model_dump() for s in data.slots],
        created_by_user_id=created_by,
    )
    db.add(routine)
    await db.commit()
    await db.refresh(routine)
    return routine


async def update_routine(
    db: AsyncSession,
    routine: AcademicRoutine,
    data: RoutineUpdate,
) -> AcademicRoutine:
    if data.title is not None:
        routine.title = data.title
    if data.department is not None:
        routine.department = data.department
    if data.batch is not None:
        routine.batch = data.batch
    if data.semester is not None:
        routine.semester = data.semester
    if data.academic_year is not None:
        routine.academic_year = data.academic_year
    if data.slots is not None:
        routine.slots = [s.model_dump() for s in data.slots]
    await db.commit()
    await db.refresh(routine)
    return routine


async def publish_routine(
    db: AsyncSession,
    routine: AcademicRoutine,
    published_by: uuid.UUID,
) -> AcademicRoutine:
    if routine.status == RoutineStatus.published:
        raise ValueError("Routine is already published")
    routine.status = RoutineStatus.published
    routine.published_by_user_id = published_by
    routine.published_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(routine)
    return routine


# ── Slot helpers — shared by import / validate / ai-edit ──────────────────────

# Friendly canonical SlotItem keys (mirrors app/schemas/routines.py SlotItem)
_SLOT_KEYS = ("day", "start_time", "end_time", "course_code", "course_name", "teacher", "room")


def _slot_time(slot: dict) -> str:
    """Best-effort display time for a slot — `time` if present, else start-end."""
    t = (slot.get("time") or "").strip()
    if t:
        return t
    start = (slot.get("start_time") or "").strip()
    end = (slot.get("end_time") or "").strip()
    if start and end:
        return f"{start}-{end}"
    return start or end


def _split_time(value: str) -> tuple[str, str]:
    """Split "8:30-10:00" → ("8:30", "10:00"); single value → (value, "")."""
    value = (value or "").strip()
    if "-" in value:
        a, b = value.split("-", 1)
        return a.strip(), b.strip()
    return value, ""


def _row_to_slot(row: dict) -> dict | None:
    """Map a lowercased-header spreadsheet row → a SlotItem-shaped dict.

    Accepts the columns produced by the routine export (Day/Time/Course/Name/
    Room/Teacher) plus common aliases. Returns None for blank rows.
    """
    g = lambda *keys: next((row[k].strip() for k in keys if row.get(k) and str(row[k]).strip()), "")
    day = g("day")
    code = g("course_code", "course", "code")
    name = g("course_name", "name", "title")
    teacher = g("teacher", "instructor", "faculty")
    room = g("room", "venue")

    start = g("start_time", "start")
    end = g("end_time", "end")
    if not start:
        start, maybe_end = _split_time(g("time", "slot"))
        end = end or maybe_end

    # Skip rows that carry no real content
    if not any([day, code, name, teacher, room, start]):
        return None

    return {
        "day": day,
        "start_time": start,
        "end_time": end,
        "course_code": code,
        "course_name": name,
        "teacher": teacher,
        "room": room,
    }


async def import_slots(
    db: AsyncSession,
    routine: AcademicRoutine,
    file_bytes: bytes,
    content_type: str,
) -> dict:
    """Replace a routine's slots from an uploaded CSV/XLSX. Moves it back to
    draft so the admin can review before re-publishing. Returns a parse summary."""
    try:
        rows = export_svc.parse_table(
            file_bytes, content_type,
            header_hints=("day", "time", "course", "room", "teacher", "start_time", "name"),
        )
    except Exception as exc:  # malformed file
        raise ValueError(f"Could not read the file: {exc}")

    slots: list[dict] = []
    errors: list[str] = []
    for i, row in enumerate(rows, start=2):  # row 1 = header
        try:
            slot = _row_to_slot(row)
            if slot is not None:
                slots.append(slot)
        except Exception as exc:
            errors.append(f"Row {i}: {exc}")

    if not slots and not errors:
        raise ValueError("No rows found. Expected columns: Day, Time, Course, Name, Room, Teacher.")

    routine.slots = slots
    routine.status = RoutineStatus.draft
    await db.commit()
    await db.refresh(routine)
    return {"imported": len(slots), "errors": errors}


def validate_slots(slots: list[dict]) -> list[dict]:
    """Pure conflict detector over a routine's flat slot list. Mirrors the hard
    rules in timetable_svc.validate_entries, but on the projected slots so the
    friendly editor can highlight clashes without the full entity graph.

    Each conflict: {type, slot_indexes: [...], description}.
    """
    conflicts: list[dict] = []
    teacher_seen: dict = {}
    room_seen: dict = {}
    section_seen: dict = {}  # one routine == one section, so (day,time) must be unique

    for i, s in enumerate(slots or []):
        day = (s.get("day") or "").strip()
        time = _slot_time(s)
        if not day or not time:
            continue
        teacher = (s.get("teacher") or "").strip().lower()
        room = (s.get("room") or "").strip().lower()

        if teacher:
            key = (teacher, day, time)
            if key in teacher_seen:
                conflicts.append({
                    "type": "teacher_double_booked",
                    "slot_indexes": [teacher_seen[key], i],
                    "description": f"{s.get('teacher')} is assigned two classes on {day} {time}",
                })
            else:
                teacher_seen[key] = i

        if room:
            key = (room, day, time)
            if key in room_seen:
                conflicts.append({
                    "type": "room_double_booked",
                    "slot_indexes": [room_seen[key], i],
                    "description": f"Room {s.get('room')} is double-booked on {day} {time}",
                })
            else:
                room_seen[key] = i

        key = (day, time)
        if key in section_seen:
            conflicts.append({
                "type": "section_overlap",
                "slot_indexes": [section_seen[key], i],
                "description": f"Two classes are scheduled at the same time on {day} {time}",
            })
        else:
            section_seen[key] = i

    return conflicts


def _apply_ai_changes(slots: list[dict], target_idx: int, changes: dict) -> dict:
    """Apply non-empty `changes` to slots[target_idx], returning the new slot."""
    slot = dict(slots[target_idx])
    if changes.get("time"):
        start, end = _split_time(str(changes["time"]))
        slot["start_time"] = start
        if end:
            slot["end_time"] = end
    for k in ("day", "start_time", "end_time", "room", "teacher", "course_code", "course_name"):
        v = changes.get(k)
        if v is not None and str(v).strip() != "":
            slot[k] = str(v).strip()
    return slot


def _find_target(slots: list[dict], match: dict) -> int | None:
    """First slot index whose fields contain every provided `match` value
    (case-insensitive substring). Returns None when nothing matches."""
    crit = {k: str(v).strip().lower() for k, v in (match or {}).items() if v not in (None, "")}
    if not crit:
        return None
    for i, s in enumerate(slots):
        hay = {
            "course_code": str(s.get("course_code", "")).lower(),
            "course_name": str(s.get("course_name", "")).lower(),
            "teacher": str(s.get("teacher", "")).lower(),
            "room": str(s.get("room", "")).lower(),
            "day": str(s.get("day", "")).lower(),
            "time": _slot_time(s).lower(),
        }
        if all(val in hay.get(key, "") for key, val in crit.items() if key in hay):
            return i
    return None


async def ai_edit_slots(slots: list[dict], text: str) -> dict:
    """Translate a natural-language edit into a slot change via local Ollama.

    Returns {ok, new_slots, summary} on success, or {ok: False, reason} when the
    model is offline / can't parse / can't find the class. Never persists — the
    caller previews the diff and saves via PATCH.
    """
    slots = slots or []
    indexed = [
        {"index": i, "day": s.get("day", ""), "time": _slot_time(s),
         "course_code": s.get("course_code", ""), "course_name": s.get("course_name", ""),
         "teacher": s.get("teacher", ""), "room": s.get("room", "")}
        for i, s in enumerate(slots)
    ]

    schema = (
        "You edit a weekly class routine. Return ONLY one JSON object, no prose:\n"
        '{"target_index": <int or null>, '
        '"match": {"course_code": <str|null>, "teacher": <str|null>, "day": <str|null>, "time": <str|null>}, '
        '"changes": {"day": <str|null>, "time": <str|null>, "room": <str|null>, "teacher": <str|null>}}\n'
        "Pick the class by target_index if obvious, else fill `match`. Put the new "
        "values in `changes`. Use null for anything that does not change. Days look "
        'like "Saturday"; time looks like "8:30-10:00".'
    )
    prompt = (
        f"{schema}\n\nCurrent classes: {json.dumps(indexed, default=str)}\n\n"
        f"Instruction: {text}\n\nReturn ONLY the JSON object."
    )

    # Prefer Gemini when configured; fall back to local Ollama.
    from app.services import gemini_client
    raw = await gemini_client.generate(prompt, temperature=0.1, timeout=20.0)
    if raw is None:
        try:
            import httpx
            from app.config import get_settings
            ollama_url = getattr(get_settings(), "ollama_base_url", "http://localhost:11434")
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.post(
                    f"{ollama_url}/api/generate",
                    json={"model": "qwen3:1.7b", "prompt": prompt, "stream": False},
                )
                resp.raise_for_status()
                raw = resp.json().get("response", "")
        except Exception as exc:
            logger.warning(f"Routine AI edit — Gemini + Ollama unavailable: {exc}")
            return {"ok": False, "reason": "The AI assistant is offline. Edit the cell directly or try again later."}

    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return {"ok": False, "reason": "Couldn't understand that. Try naming the course and the new day/time."}
    try:
        data = json.loads(match.group())
    except Exception:
        return {"ok": False, "reason": "Couldn't understand that. Try naming the course and the new day/time."}

    idx = data.get("target_index")
    if not isinstance(idx, int) or not (0 <= idx < len(slots)):
        idx = _find_target(slots, data.get("match") or {})
    if idx is None:
        return {"ok": False, "reason": "Couldn't find a matching class to change. Be more specific."}

    changes = data.get("changes") or {}
    if not any(str(v).strip() for v in changes.values() if v is not None):
        return {"ok": False, "reason": "No change was requested. Say what to move and where."}

    new_slots = copy.deepcopy(slots)
    before = new_slots[idx]
    new_slot = _apply_ai_changes(new_slots, idx, changes)
    new_slots[idx] = new_slot

    label = before.get("course_code") or before.get("course_name") or "class"
    summary = (
        f"Move {label} from {before.get('day','?')} {_slot_time(before)} "
        f"to {new_slot.get('day', before.get('day','?'))} {_slot_time(new_slot)}"
    )
    return {"ok": True, "new_slots": new_slots, "summary": summary, "changed_index": idx}
