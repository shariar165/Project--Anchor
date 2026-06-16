"""Realistic DIU Software-Engineering scenario for exercising the timetable solver.

Shared by `tests/test_timetable_generator_scale.py` (SQLite) and the standalone
`seed_timetable_demo.py` (live Postgres). Builds: ~115 faculty, 9 batches (40–48) ×
8 sections (A–H) with lab-group splits, the real per-batch course lists (one lab
course per batch), the real theory/lab room inventory, a round-robin eligibility map
(≥N teachers per course), a schedule config, and one offering per (course, batch).

Capacity (full scale, 6 days):
  theory ≈ 44 courses × 8 sections × 2/wk ≈ 700 sessions  vs 21 theory rooms
  lab    ≈ 9 courses × 8 sections × 2 groups × 1/wk ≈ 144 sessions vs 13 lab rooms
6×6 slots is borderline for theory (756 capacity); default 8 slots gives headroom.
"""
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, Role, AccountStatus
from app.models.timetable import (
    TimetableTerm, TimetableBatch, TimetableSection,
    TimetableRoom, TimetableCourse, TimetableFacultyProfile,
    TimetableCourseOffering, TimetableTeacherEligibility,
    TimetableScheduleConfig,
)
from app.services import timetable_svc

# Faculty short-codes supplied by the user (deduplicated, order-stable).
_RAW_FACULTY_CODES = [
    "AJE","AAA","AAS","AE","AF","AHZ","AMR","AUA","AB","AS","AR","BNS","C1","CP",
    "DB","DEH","DMA","DMH","DMR","DMMA","DSM","DSI","DKS","DK","EMP1","FA","FAJ",
    "FBR","FH","FJT","FRN","FRR","FC","FF","FUA","HI","HM","HKN","HT","IAT","IM",
    "IS","JIC","JC","JJS","JR","KBB","KM","KRA","KRY","MAS","MA","MAK","MAJ","MAB",
    "MKS","MIR","MIS","MNA","MMSI","MME","MSH","MSIM","MSR","MSP","MS","MTE","MKH",
    "MJM","MMH","MMN","MTH","NA","NAJ","NJN","NIR","NML","NN","NSL","PSI","PC","PS",
    "RA","RH","RHH","RI","RMS","RJM","RKH","RUA","RRB","RT","SD","SI","SIK","SIM",
    "SKU","SK","SCS","SAM","SBA","SP","SR","SSR","SST","ST","SSI","TBH","TM","THZ",
    "TRT","TRK","TT","UKD","WNI","ZNM","ZH",
]
# Deduplicate while preserving order.
FACULTY_CODES = list(dict.fromkeys(_RAW_FACULTY_CODES))

# Batch → ordered course codes. The LAST code in each list is treated as a lab.
BATCH_COURSES: dict[str, list[str]] = {
    "48": ["ENG101", "BNS101", "SE111", "SE112"],
    "47": ["MAT101", "MAT102", "PHY101", "SE121", "SE122", "SE123"],
    "46": ["SE131", "SE132", "SE133", "SE213"],
    "45": ["AOL101", "GE235", "SE222", "SE223", "SE224"],
    "44": ["SE214", "SE215", "SE216", "SE217", "SE411", "SE447"],
    "43": ["SE231", "SE232", "SE233", "SE234", "SE235", "SE236"],
    "42": ["SE312", "SE313", "SE321", "SE322", "SE323", "SE334", "SE341", "SE532"],
    "41": ["DS332", "DS411", "DS412", "ST413", "ST414", "SE333"],
    "40": ["EMP101", "CS211", "CS418", "CS422", "DS421", "DS422", "DS423", "DS424"],
}
# Batches ordered newest-first (48 has the fewest courses → cheapest subset).
BATCH_ORDER = ["48", "47", "46", "45", "44", "43", "42", "41", "40"]

THEORY_ROOMS = [
    "AB4-101A", "AB4-611", "AB4-612", "AB4-604", "AB4-701A", "AB4-701B",
    "AB4-712A", "AB4-712B", "AB4-713", "AB4-811", "AB4-812", "AB4-813A",
    "AB4-913", "AB4-914", "AB4-802", "AB4-1415A", "AB4-1415B", "AB4-1504",
    "YKSG3-106", "YKSG3-107", "YKSG3-108",
]
LAB_ROOMS = [
    "AB4-814B", "AB4-610", "AB4-616", "AB4-710", "AB4-711A", "AB4-711B",
    "AB4-814A", "AB4-903", "AB3-104", "AB3-106", "AB3-107", "AB4-601", "AB4-613",
]

DAYS = ["Sat", "Sun", "Mon", "Tue", "Wed", "Thu"]
_SEED_PW_HASH = "seed-no-login-placeholder"  # faculty users never authenticate


def _slots(n: int) -> list[str]:
    base = [
        "8:30-10:00", "10:00-11:30", "11:30-13:00", "13:30-15:00",
        "15:00-16:30", "16:30-18:00", "18:00-19:30", "19:30-21:00",
    ]
    return base[:n]


async def seed_scenario(
    db: AsyncSession,
    *,
    n_batches: int = 9,
    n_slots: int = 8,
    eligible_per_course: int = 4,
    tenant_id: uuid.UUID | None = None,
    email_domain: str = "seed.diu.edu.bd",
    term_name: str = "Demo Term",
) -> dict:
    """Create the full scenario. Returns ids/counts for the caller.

    Idempotency is NOT attempted — intended for a fresh test DB or a wiped term.
    """
    # ── Term + schedule config ────────────────────────────────────────────────
    term = TimetableTerm(name=term_name, tenant_id=tenant_id, is_active=True)
    db.add(term)
    await db.flush()

    db.add(TimetableScheduleConfig(
        tenant_id=tenant_id, term_id=term.id,
        days=list(DAYS), slots=_slots(n_slots), off_days=["Fri"],
    ))

    # ── Faculty (User + profile) ──────────────────────────────────────────────
    faculty_profiles: list[TimetableFacultyProfile] = []
    for code in FACULTY_CODES:
        user = User(
            full_name=f"Faculty {code}",
            email=f"{code.lower()}@{email_domain}",
            password_hash=_SEED_PW_HASH,
            role=Role.moderator,
            status=AccountStatus.active,
            tenant_id=tenant_id,
            email_verified=True,
        )
        db.add(user)
        await db.flush()
        fp = TimetableFacultyProfile(
            user_id=user.id, tenant_id=tenant_id, rank="LECTURER",
            max_per_day=4, off_days=[], active=True,
        )
        db.add(fp)
        faculty_profiles.append(fp)
    await db.flush()

    # ── Rooms ─────────────────────────────────────────────────────────────────
    for name in THEORY_ROOMS:
        db.add(TimetableRoom(name=name, room_type="THEORY", capacity=40, tenant_id=tenant_id))
    for name in LAB_ROOMS:
        db.add(TimetableRoom(name=name, room_type="LAB", capacity=30, tenant_id=tenant_id))
    await db.flush()

    # ── Courses (unique by code; last code per batch is a lab) ────────────────
    batches_to_seed = BATCH_ORDER[:n_batches]
    courses_by_code: dict[str, TimetableCourse] = {}
    for batch_name in batches_to_seed:
        codes = BATCH_COURSES[batch_name]
        for i, code in enumerate(codes):
            if code in courses_by_code:
                continue
            is_lab = (i == len(codes) - 1)
            course = TimetableCourse(
                code=code, name=f"{code} course", credits=3,
                is_lab=is_lab, weekly_classes=1 if is_lab else 2,
                tenant_id=tenant_id,
            )
            db.add(course)
            courses_by_code[code] = course
    await db.flush()

    # ── Eligibility — round-robin so every course has >= eligible_per_course ──
    fp_count = len(faculty_profiles)
    ptr = 0
    for course in courses_by_code.values():
        for _ in range(eligible_per_course):
            fp = faculty_profiles[ptr % fp_count]
            ptr += 1
            db.add(TimetableTeacherEligibility(faculty_id=fp.id, course_id=course.id))
    await db.flush()

    # ── Batches + sections (A–H) + lab groups, and offerings ──────────────────
    section_count = 0
    offering_count = 0
    for batch_name in batches_to_seed:
        batch = TimetableBatch(name=f"Batch {batch_name}", program="SWE", tenant_id=tenant_id)
        db.add(batch)
        await db.flush()
        secs = await timetable_svc.generate_sections(db, batch.id, count=8, lab_split=True)
        section_count += len(secs)
        for code in BATCH_COURSES[batch_name]:
            db.add(TimetableCourseOffering(
                term_id=term.id, course_id=courses_by_code[code].id, batch_id=batch.id,
            ))
            offering_count += 1
    await db.commit()

    return {
        "term_id": term.id,
        "n_batches": len(batches_to_seed),
        "n_faculty": fp_count,
        "n_courses": len(courses_by_code),
        "n_sections": section_count,
        "n_offerings": offering_count,
        "n_theory_rooms": len(THEORY_ROOMS),
        "n_lab_rooms": len(LAB_ROOMS),
        "n_slots": n_slots,
        "n_days": len(DAYS),
    }
