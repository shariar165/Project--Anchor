import uuid
from datetime import datetime
from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Integer, String, Text, Uuid, JSON, func,
)
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin


class TimetableTerm(Base, TimestampMixin):
    __tablename__ = "tt_terms"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("tenants.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class TimetableBatch(Base, TimestampMixin):
    __tablename__ = "tt_batches"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("tenants.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    program: Mapped[str] = mapped_column(String(20), nullable=False, default="SWE")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class TimetableSection(Base):
    __tablename__ = "tt_sections"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    batch_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tt_batches.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(10), nullable=False)


class TimetableLabGroup(Base):
    __tablename__ = "tt_lab_groups"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    section_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tt_sections.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(10), nullable=False)


class TimetableRoom(Base, TimestampMixin):
    __tablename__ = "tt_rooms"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("tenants.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    room_type: Mapped[str] = mapped_column(String(20), nullable=False)  # THEORY | LAB | ONLINE
    capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=30)


class TimetableCourse(Base, TimestampMixin):
    __tablename__ = "tt_courses"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("tenants.id"), nullable=True, index=True)
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    credits: Mapped[int] = mapped_column(Integer, nullable=False)
    is_lab: Mapped[bool] = mapped_column(Boolean, nullable=False)
    weekly_classes: Mapped[int] = mapped_column(Integer, nullable=False)


class TimetableFacultyProfile(Base, TimestampMixin):
    __tablename__ = "tt_faculty_profiles"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("tenants.id"), nullable=True, index=True)
    rank: Mapped[str] = mapped_column(String(30), nullable=False)
    min_credits: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_credits: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pref_slot: Mapped[int | None] = mapped_column(Integer, nullable=True)
    off_days: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    max_per_day: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class TimetableStudentEnrollment(Base):
    __tablename__ = "tt_student_enrollment"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    section_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tt_sections.id"), nullable=False, index=True)
    term_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tt_terms.id"), nullable=False, index=True)
    lab_group_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("tt_lab_groups.id"), nullable=True)


class TimetableCourseOffering(Base):
    __tablename__ = "tt_course_offerings"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    term_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tt_terms.id"), nullable=False, index=True)
    course_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tt_courses.id"), nullable=False, index=True)
    batch_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tt_batches.id"), nullable=False, index=True)


class TimetableTeacherEligibility(Base):
    __tablename__ = "tt_teacher_eligibility"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    faculty_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tt_faculty_profiles.id"), nullable=False, index=True)
    course_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tt_courses.id"), nullable=False, index=True)


class TimetableScheduleConfig(Base, TimestampMixin):
    __tablename__ = "tt_schedule_config"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("tenants.id"), nullable=True, index=True)
    term_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("tt_terms.id"), nullable=True, index=True)
    days: Mapped[list] = mapped_column(JSON, nullable=False)   # ["Sat","Sun","Mon","Tue","Wed","Thu"]
    slots: Mapped[list] = mapped_column(JSON, nullable=False)  # ["8:30-10:00", "10:00-11:30", ...]
    off_days: Mapped[list] = mapped_column(JSON, nullable=False, default=list)


class TimetableConstraint(Base, TimestampMixin):
    __tablename__ = "tt_constraints"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("tenants.id"), nullable=True, index=True)
    term_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("tt_terms.id"), nullable=True, index=True)
    constraint_type: Mapped[str] = mapped_column(String(50), nullable=False)
    scope: Mapped[dict] = mapped_column(JSON, nullable=False)
    params: Mapped[dict] = mapped_column(JSON, nullable=False)
    enforcement: Mapped[str] = mapped_column(String(10), nullable=False)  # hard | soft
    weight: Mapped[int | None] = mapped_column(Integer, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)


class TimetableSolveJob(Base, TimestampMixin):
    __tablename__ = "tt_solve_jobs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("tenants.id"), nullable=True, index=True)
    term_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tt_terms.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    solver_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    objective_value: Mapped[int | None] = mapped_column(Integer, nullable=True)
    infeasible_core: Mapped[list | None] = mapped_column(JSON, nullable=True)
    params: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    requested_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)
    result_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TimetableEntry(Base, TimestampMixin):
    __tablename__ = "tt_entries"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("tenants.id"), nullable=True, index=True)
    term_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tt_terms.id"), nullable=False, index=True)
    result_version: Mapped[int] = mapped_column(Integer, nullable=False)
    course_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tt_courses.id"), nullable=False)
    section_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tt_sections.id"), nullable=False, index=True)
    lab_group_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("tt_lab_groups.id"), nullable=True)
    faculty_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tt_faculty_profiles.id"), nullable=False)
    room_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tt_rooms.id"), nullable=False)
    day: Mapped[int] = mapped_column(Integer, nullable=False)    # 0=Sat .. 5=Thu
    slot: Mapped[int] = mapped_column(Integer, nullable=False)
    is_lab: Mapped[bool] = mapped_column(Boolean, nullable=False)
    locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source: Mapped[str] = mapped_column(String(10), nullable=False, default="solver")  # solver | manual
    published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
