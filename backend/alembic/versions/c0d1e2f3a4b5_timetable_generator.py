"""timetable generator — add tt_* tables

Revision ID: c0d1e2f3a4b5
Revises: b1c2d3e4f5a6
Create Date: 2026-06-13 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'c0d1e2f3a4b5'
down_revision: Union[str, None] = 'b1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'tt_terms',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('tenant_id', sa.Uuid(), sa.ForeignKey('tenants.id'), nullable=True, index=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        'tt_batches',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('tenant_id', sa.Uuid(), sa.ForeignKey('tenants.id'), nullable=True, index=True),
        sa.Column('name', sa.String(50), nullable=False),
        sa.Column('program', sa.String(20), nullable=False, server_default='SWE'),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        'tt_sections',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('batch_id', sa.Uuid(), sa.ForeignKey('tt_batches.id'), nullable=False, index=True),
        sa.Column('name', sa.String(10), nullable=False),
    )

    op.create_table(
        'tt_lab_groups',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('section_id', sa.Uuid(), sa.ForeignKey('tt_sections.id'), nullable=False, index=True),
        sa.Column('name', sa.String(10), nullable=False),
    )

    op.create_table(
        'tt_rooms',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('tenant_id', sa.Uuid(), sa.ForeignKey('tenants.id'), nullable=True, index=True),
        sa.Column('name', sa.String(50), nullable=False),
        sa.Column('room_type', sa.String(20), nullable=False),
        sa.Column('capacity', sa.Integer(), nullable=False, server_default='30'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        'tt_courses',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('tenant_id', sa.Uuid(), sa.ForeignKey('tenants.id'), nullable=True, index=True),
        sa.Column('code', sa.String(20), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('credits', sa.Integer(), nullable=False),
        sa.Column('is_lab', sa.Boolean(), nullable=False),
        sa.Column('weekly_classes', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        'tt_faculty_profiles',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('tenant_id', sa.Uuid(), sa.ForeignKey('tenants.id'), nullable=True, index=True),
        sa.Column('rank', sa.String(30), nullable=False),
        sa.Column('min_credits', sa.Integer(), nullable=True),
        sa.Column('max_credits', sa.Integer(), nullable=True),
        sa.Column('pref_slot', sa.Integer(), nullable=True),
        sa.Column('off_days', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('max_per_day', sa.Integer(), nullable=False, server_default='4'),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        'tt_student_enrollment',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('section_id', sa.Uuid(), sa.ForeignKey('tt_sections.id'), nullable=False, index=True),
        sa.Column('term_id', sa.Uuid(), sa.ForeignKey('tt_terms.id'), nullable=False, index=True),
        sa.Column('lab_group_id', sa.Uuid(), sa.ForeignKey('tt_lab_groups.id'), nullable=True),
    )

    op.create_table(
        'tt_course_offerings',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('term_id', sa.Uuid(), sa.ForeignKey('tt_terms.id'), nullable=False, index=True),
        sa.Column('course_id', sa.Uuid(), sa.ForeignKey('tt_courses.id'), nullable=False, index=True),
        sa.Column('batch_id', sa.Uuid(), sa.ForeignKey('tt_batches.id'), nullable=False, index=True),
    )

    op.create_table(
        'tt_teacher_eligibility',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('faculty_id', sa.Uuid(), sa.ForeignKey('tt_faculty_profiles.id'), nullable=False, index=True),
        sa.Column('course_id', sa.Uuid(), sa.ForeignKey('tt_courses.id'), nullable=False, index=True),
    )

    op.create_table(
        'tt_schedule_config',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('tenant_id', sa.Uuid(), sa.ForeignKey('tenants.id'), nullable=True, index=True),
        sa.Column('term_id', sa.Uuid(), sa.ForeignKey('tt_terms.id'), nullable=True, index=True),
        sa.Column('days', sa.JSON(), nullable=False),
        sa.Column('slots', sa.JSON(), nullable=False),
        sa.Column('off_days', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        'tt_constraints',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('tenant_id', sa.Uuid(), sa.ForeignKey('tenants.id'), nullable=True, index=True),
        sa.Column('term_id', sa.Uuid(), sa.ForeignKey('tt_terms.id'), nullable=True, index=True),
        sa.Column('constraint_type', sa.String(50), nullable=False),
        sa.Column('scope', sa.JSON(), nullable=False),
        sa.Column('params', sa.JSON(), nullable=False),
        sa.Column('enforcement', sa.String(10), nullable=False),
        sa.Column('weight', sa.Integer(), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_by', sa.Uuid(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        'tt_solve_jobs',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('tenant_id', sa.Uuid(), sa.ForeignKey('tenants.id'), nullable=True, index=True),
        sa.Column('term_id', sa.Uuid(), sa.ForeignKey('tt_terms.id'), nullable=False, index=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='queued'),
        sa.Column('progress', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('solver_status', sa.String(30), nullable=True),
        sa.Column('objective_value', sa.Integer(), nullable=True),
        sa.Column('infeasible_core', sa.JSON(), nullable=True),
        sa.Column('params', sa.JSON(), nullable=True),
        sa.Column('requested_by', sa.Uuid(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('result_version', sa.Integer(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        'tt_entries',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('tenant_id', sa.Uuid(), sa.ForeignKey('tenants.id'), nullable=True, index=True),
        sa.Column('term_id', sa.Uuid(), sa.ForeignKey('tt_terms.id'), nullable=False, index=True),
        sa.Column('result_version', sa.Integer(), nullable=False),
        sa.Column('course_id', sa.Uuid(), sa.ForeignKey('tt_courses.id'), nullable=False),
        sa.Column('section_id', sa.Uuid(), sa.ForeignKey('tt_sections.id'), nullable=False, index=True),
        sa.Column('lab_group_id', sa.Uuid(), sa.ForeignKey('tt_lab_groups.id'), nullable=True),
        sa.Column('faculty_id', sa.Uuid(), sa.ForeignKey('tt_faculty_profiles.id'), nullable=False),
        sa.Column('room_id', sa.Uuid(), sa.ForeignKey('tt_rooms.id'), nullable=False),
        sa.Column('day', sa.Integer(), nullable=False),
        sa.Column('slot', sa.Integer(), nullable=False),
        sa.Column('is_lab', sa.Boolean(), nullable=False),
        sa.Column('locked', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('source', sa.String(10), nullable=False, server_default='solver'),
        sa.Column('published', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('tt_entries')
    op.drop_table('tt_solve_jobs')
    op.drop_table('tt_constraints')
    op.drop_table('tt_schedule_config')
    op.drop_table('tt_teacher_eligibility')
    op.drop_table('tt_course_offerings')
    op.drop_table('tt_student_enrollment')
    op.drop_table('tt_faculty_profiles')
    op.drop_table('tt_courses')
    op.drop_table('tt_rooms')
    op.drop_table('tt_lab_groups')
    op.drop_table('tt_sections')
    op.drop_table('tt_batches')
    op.drop_table('tt_terms')
