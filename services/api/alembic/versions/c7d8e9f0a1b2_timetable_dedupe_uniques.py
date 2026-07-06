"""Timetable: dedupe polluted data + unique constraints.

The CSV importer used to append instead of upserting (audit finding H-1),
which roughly doubled tt_courses and inflated tt_faculty_profiles in
production. This migration:

1. (PostgreSQL only) merges duplicate courses / faculty / rooms / batches /
   sections / lab groups onto the oldest row per normalized identity,
   remapping every FK reference, then deletes the duplicates, then removes
   exact-duplicate offerings and eligibility rows.
2. Adds the unique constraints that make re-pollution impossible:
   - portable (also present in the SQLAlchemy models, so SQLite tests match):
     offerings(term, course, batch) · eligibility(faculty, course) ·
     sections(batch, name) · lab_groups(section, name)
   - PostgreSQL-only normalized unique indexes (NULLS NOT DISTINCT, PG 15+):
     courses / rooms / batches / faculty-email per tenant.

Terms are intentionally NOT deduped here (merging terms would mix result
versions); duplicate term names are blocked at the service layer instead.

Downgrade drops the constraints only — the dedupe is one-way.

Revision ID: c7d8e9f0a1b2
Revises: b3c4d5e6f7a8
Create Date: 2026-07-06
"""
from alembic import op
import sqlalchemy as sa

revision = "c7d8e9f0a1b2"
down_revision = "b3c4d5e6f7a8"
branch_labels = None
depends_on = None


# Normalization mirrors app.services.timetable_svc._norm_code / _norm_batch.
_NORM_CODE = r"lower(regexp_replace(code, '[\s_-]+', '', 'g'))"
_NORM_BATCH = r"regexp_replace(lower(regexp_replace(name, '[\s_-]+', '', 'g')), '^batch', '')"


def _dedupe(table: str, partition: str, order: str, remaps: list[tuple[str, str]]):
    """Merge duplicate `table` rows onto the oldest per `partition`.

    remaps: [(referencing_table, fk_column)] — repointed to the canonical row
    before the duplicates are deleted.
    """
    ranked = (
        f"SELECT id, first_value(id) OVER ("
        f"  PARTITION BY {partition} ORDER BY {order}) AS canon "
        f"FROM {table}"
    )
    for ref_table, fk_col in remaps:
        op.execute(sa.text(
            f"UPDATE {ref_table} t SET {fk_col} = r.canon "
            f"FROM ({ranked}) r WHERE t.{fk_col} = r.id AND r.id <> r.canon"
        ))
    op.execute(sa.text(
        f"DELETE FROM {table} x USING ({ranked}) r "
        f"WHERE x.id = r.id AND r.id <> r.canon"
    ))


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        # Tests build their schema from SQLAlchemy metadata (which already
        # carries the portable constraints); the dedupe DML is PG-specific.
        return

    # 1) Courses — duplicates by normalized code within a tenant
    _dedupe(
        "tt_courses",
        f"tenant_id, {_NORM_CODE}",
        "created_at, id",
        [
            ("tt_course_offerings", "course_id"),
            ("tt_teacher_eligibility", "course_id"),
            ("tt_entries", "course_id"),
        ],
    )

    # 2) Faculty — duplicates by email within a tenant (email-less rows kept)
    ranked_fac = (
        "SELECT id, first_value(id) OVER ("
        "  PARTITION BY tenant_id, lower(email) ORDER BY created_at, id) AS canon "
        "FROM tt_faculty_profiles WHERE email IS NOT NULL"
    )
    for ref_table, fk_col in [
        ("tt_teacher_eligibility", "faculty_id"),
        ("tt_entries", "faculty_id"),
    ]:
        op.execute(sa.text(
            f"UPDATE {ref_table} t SET {fk_col} = r.canon "
            f"FROM ({ranked_fac}) r WHERE t.{fk_col} = r.id AND r.id <> r.canon"
        ))
    op.execute(sa.text(
        f"DELETE FROM tt_faculty_profiles x USING ({ranked_fac}) r "
        f"WHERE x.id = r.id AND r.id <> r.canon"
    ))

    # 3) Rooms — duplicates by lower(name) within a tenant
    _dedupe(
        "tt_rooms",
        "tenant_id, lower(name)",
        "created_at, id",
        [("tt_entries", "room_id")],
    )

    # 4) Batches — duplicates by normalized name within a tenant
    _dedupe(
        "tt_batches",
        f"tenant_id, {_NORM_BATCH}",
        "created_at, id",
        [
            ("tt_sections", "batch_id"),
            ("tt_course_offerings", "batch_id"),
        ],
    )

    # 5) Sections (may newly collide after batch merge), then lab groups
    _dedupe(
        "tt_sections",
        "batch_id, name",
        "id",
        [
            ("tt_lab_groups", "section_id"),
            ("tt_entries", "section_id"),
            ("tt_student_enrollment", "section_id"),
        ],
    )
    _dedupe(
        "tt_lab_groups",
        "section_id, name",
        "id",
        [
            ("tt_entries", "lab_group_id"),
            ("tt_student_enrollment", "lab_group_id"),
        ],
    )

    # 6) Exact-duplicate offerings / eligibility rows (nothing references them)
    op.execute(sa.text(
        "DELETE FROM tt_course_offerings x USING ("
        "  SELECT id, first_value(id) OVER ("
        "    PARTITION BY term_id, course_id, batch_id ORDER BY id) AS canon"
        "  FROM tt_course_offerings) r "
        "WHERE x.id = r.id AND r.id <> r.canon"
    ))
    op.execute(sa.text(
        "DELETE FROM tt_teacher_eligibility x USING ("
        "  SELECT id, first_value(id) OVER ("
        "    PARTITION BY faculty_id, course_id ORDER BY id) AS canon"
        "  FROM tt_teacher_eligibility) r "
        "WHERE x.id = r.id AND r.id <> r.canon"
    ))

    # 7) Portable unique constraints (mirror the models' __table_args__)
    op.create_unique_constraint(
        "uq_tt_offerings_term_course_batch", "tt_course_offerings",
        ["term_id", "course_id", "batch_id"],
    )
    op.create_unique_constraint(
        "uq_tt_eligibility_faculty_course", "tt_teacher_eligibility",
        ["faculty_id", "course_id"],
    )
    op.create_unique_constraint(
        "uq_tt_sections_batch_name", "tt_sections", ["batch_id", "name"],
    )
    op.create_unique_constraint(
        "uq_tt_lab_groups_section_name", "tt_lab_groups", ["section_id", "name"],
    )

    # 8) PG-only normalized unique indexes. NULLS NOT DISTINCT matters: most
    # production rows have tenant_id NULL, and a plain unique would treat every
    # NULL as distinct — enforcing nothing.
    op.execute(sa.text(
        "CREATE UNIQUE INDEX uq_tt_courses_tenant_norm_code ON tt_courses "
        f"(tenant_id, ({_NORM_CODE})) NULLS NOT DISTINCT"
    ))
    op.execute(sa.text(
        "CREATE UNIQUE INDEX uq_tt_rooms_tenant_lower_name ON tt_rooms "
        "(tenant_id, lower(name)) NULLS NOT DISTINCT"
    ))
    op.execute(sa.text(
        "CREATE UNIQUE INDEX uq_tt_batches_tenant_norm_name ON tt_batches "
        f"(tenant_id, ({_NORM_BATCH})) NULLS NOT DISTINCT"
    ))
    op.execute(sa.text(
        "CREATE UNIQUE INDEX uq_tt_faculty_tenant_email ON tt_faculty_profiles "
        "(tenant_id, lower(email)) NULLS NOT DISTINCT WHERE email IS NOT NULL"
    ))


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute(sa.text("DROP INDEX IF EXISTS uq_tt_faculty_tenant_email"))
    op.execute(sa.text("DROP INDEX IF EXISTS uq_tt_batches_tenant_norm_name"))
    op.execute(sa.text("DROP INDEX IF EXISTS uq_tt_rooms_tenant_lower_name"))
    op.execute(sa.text("DROP INDEX IF EXISTS uq_tt_courses_tenant_norm_code"))
    op.drop_constraint("uq_tt_lab_groups_section_name", "tt_lab_groups")
    op.drop_constraint("uq_tt_sections_batch_name", "tt_sections")
    op.drop_constraint("uq_tt_eligibility_faculty_course", "tt_teacher_eligibility")
    op.drop_constraint("uq_tt_offerings_term_course_batch", "tt_course_offerings")
    # Dedupe DML is intentionally not reversible.
