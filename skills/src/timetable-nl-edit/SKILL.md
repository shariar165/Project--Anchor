---
name: timetable-nl-edit
description: >
  Use this skill when an administrator edits a generated academic timetable using plain
  language instead of drag-and-drop. Triggers: "move Dr. Ahmed's Thursday class to Tuesday",
  "swap the 10am and 1pm slots", "lock this entry", "put CSE101 in room 302", "reassign this
  class to another teacher", "change the day/slot/room/faculty of a class". Translates a
  natural-language scheduling command into a single structured EntryEdit JSON object that the
  CP-SAT timetable backend applies (services/api timetable_solver.py nl_to_entry_edit). The
  compact references/grounding.md is injected into that prompt — keep it in sync.
---

# Timetable Natural-Language Edit

A skill for turning one administrator instruction about a class schedule into one precise,
machine-applicable edit. The backend validates the edit against hard constraints (no room,
faculty, or section double-booking) before committing it, so your job is accurate *intent
extraction*, not conflict checking.

---

## Output contract

Return **only** a single JSON object — no prose, no explanation — matching this schema:

```json
{
  "entry_id": "<uuid of the entry to change, or null>",
  "new_day": <integer 0–5, or null>,
  "new_slot": <integer slot index, or null>,
  "new_faculty_id": "<uuid, or null>",
  "new_room_id": "<uuid, or null>",
  "lock": <true|false>
}
```

- Use `null` for every field that the command does not change.
- `entry_id` identifies the class being edited; resolve it from the provided current-entries
  context (match on course, faculty, day, and slot mentioned by the user).
- `lock: true` pins the entry so future solver runs won't move it.

## Day & slot indexing

- **Day** is `0–5`: 0 = Saturday, 1 = Sunday, 2 = Monday, 3 = Tuesday, 4 = Wednesday,
  5 = Thursday. (The Bangladesh academic week runs Saturday–Thursday; Friday is the weekend.)
- **Slot** is the integer period index used in the schedule config (0-based). Map "first
  period / 9am" style phrases to the slot index from the provided context, not a guess.

## Resolving references

- The user names things by **course code, teacher name, room, day, or time** — match these
  against the current-entries context to find the right `entry_id` and target IDs.
- If the command is ambiguous (matches multiple entries, or the target day/slot/room can't be
  resolved), prefer returning the closest single best match; the backend will reject an
  invalid edit rather than corrupt the schedule. Never invent a UUID that isn't in the context.

## Examples

- "Move Dr. Ahmed's Thursday class to Tuesday" → set `entry_id` to Ahmed's Thursday entry,
  `new_day: 3`, everything else `null`.
- "Lock the CSE101 Monday 9am slot" → `entry_id` of that entry, `lock: true`.
- "Put the Database Systems class in room 302" → `entry_id` of that class,
  `new_room_id` of room 302.
- "Reassign the Sunday 11am Physics class to Dr. Karim" → `entry_id` of that class,
  `new_faculty_id` of Dr. Karim.
