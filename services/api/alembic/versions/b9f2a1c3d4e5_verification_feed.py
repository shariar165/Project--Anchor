"""verification_feed

Revision ID: b9f2a1c3d4e5
Revises: a3f7c8d2e1b5
Create Date: 2026-06-02 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'b9f2a1c3d4e5'
down_revision: Union[str, None] = 'a3f7c8d2e1b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. verification_feed_posts
    op.create_table(
        'verification_feed_posts',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('post_number', sa.String(30), nullable=False),
        sa.Column('publisher_user_id', sa.Uuid(), nullable=False),
        sa.Column('scope', sa.Enum('campus', 'national', name='postscope'), nullable=False),
        sa.Column('tenant_id', sa.Uuid(), nullable=True),
        sa.Column('category', sa.Enum(
            'incident', 'missing_person', 'road', 'safety', 'civic_event',
            name='postcategory',
        ), nullable=False),
        sa.Column('title', sa.String(100), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('geo_lat', sa.Double(), nullable=True),
        sa.Column('geo_lng', sa.Double(), nullable=True),
        sa.Column('geo_address', sa.Text(), nullable=True),
        sa.Column('state', sa.Enum(
            'pending_ai', 'live', 'under_review', 'taken_down', 'marked_fake', 'deleted_by_author',
            name='poststate',
        ), nullable=False, server_default='pending_ai'),
        sa.Column('ai_prescreen_verdict', sa.Enum(
            'pass', 'block', 'manual_review',
            name='aiprescreenverdict',
        ), nullable=True),
        sa.Column('ai_prescreen_data', sa.JSON(), nullable=True),
        sa.Column('admin_confirmed', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('admin_confirmed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('admin_confirmed_by', sa.Uuid(), nullable=True),
        sa.Column('zone_id', sa.Uuid(), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['publisher_user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['admin_confirmed_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['zone_id'], ['zones.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('post_number'),
    )
    op.create_index('ix_vfp_post_number', 'verification_feed_posts', ['post_number'], unique=True)
    op.create_index('ix_vfp_publisher', 'verification_feed_posts', ['publisher_user_id'])
    op.create_index('ix_vfp_scope', 'verification_feed_posts', ['scope'])
    op.create_index('ix_vfp_state', 'verification_feed_posts', ['state'])
    op.create_index('ix_vfp_tenant_id', 'verification_feed_posts', ['tenant_id'])
    op.create_index('ix_vfp_category', 'verification_feed_posts', ['category'])

    # 2. verification_feed_post_versions
    op.create_table(
        'verification_feed_post_versions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('post_id', sa.Uuid(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(100), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('geo_lat', sa.Double(), nullable=True),
        sa.Column('geo_lng', sa.Double(), nullable=True),
        sa.Column('edited_by', sa.Uuid(), nullable=True),
        sa.Column('edited_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['post_id'], ['verification_feed_posts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['edited_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_vfpv_post_id', 'verification_feed_post_versions', ['post_id'])

    # 3. verification_feed_attachments
    op.create_table(
        'verification_feed_attachments',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('post_id', sa.Uuid(), nullable=False),
        sa.Column('file_ref', sa.Text(), nullable=False),
        sa.Column('file_hash_sha256', sa.String(64), nullable=False),
        sa.Column('content_type', sa.String(100), nullable=False),
        sa.Column('file_size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('explain_cache', sa.Text(), nullable=True),
        sa.Column('uploaded_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['post_id'], ['verification_feed_posts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_vfa_post_id', 'verification_feed_attachments', ['post_id'])

    # 4. verification_feed_signals
    op.create_table(
        'verification_feed_signals',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('post_id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=True),
        sa.Column('signal_type', sa.Enum('corroborate', 'challenge', name='signaltype'), nullable=False),
        sa.Column('reason', sa.String(200), nullable=True),
        sa.Column('weight', sa.Numeric(4, 2), nullable=False, server_default='1.00'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['post_id'], ['verification_feed_posts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('post_id', 'user_id', name='uq_feed_signal_per_user'),
    )
    op.create_index('ix_vfs_post_id', 'verification_feed_signals', ['post_id'])
    op.create_index('ix_vfs_user_id', 'verification_feed_signals', ['user_id'])

    # 5. verification_feed_flags
    op.create_table(
        'verification_feed_flags',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('post_id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=True),
        sa.Column('flag_reason', sa.Enum(
            'harassment', 'off_topic', 'wrong_category', 'illegal_content', 'spam', 'other',
            name='flagreason',
        ), nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['post_id'], ['verification_feed_posts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('post_id', 'user_id', name='uq_feed_flag_per_user'),
    )
    op.create_index('ix_vff_post_id', 'verification_feed_flags', ['post_id'])

    # 6. verification_feed_moderation
    op.create_table(
        'verification_feed_moderation',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('post_id', sa.Uuid(), nullable=False),
        sa.Column('moderator_user_id', sa.Uuid(), nullable=True),
        sa.Column('action', sa.Enum(
            'confirm', 'mark_fake', 'take_down', 'no_action', 'defer', 'restore', 'promote_to_zone',
            name='moderationaction',
        ), nullable=False),
        sa.Column('internal_note', sa.Text(), nullable=True),
        sa.Column('public_note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['post_id'], ['verification_feed_posts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['moderator_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_vfm_post_id', 'verification_feed_moderation', ['post_id'])

    # 7. user_feed_trust
    op.create_table(
        'user_feed_trust',
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('confirmed_accurate_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('confirmed_fake_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('trust_tier', sa.Enum('none', 'bronze', 'silver', 'gold', name='trusttier'),
                  nullable=False, server_default='none'),
        sa.Column('last_recalculated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id'),
    )


def downgrade() -> None:
    op.drop_table('user_feed_trust')
    op.drop_table('verification_feed_moderation')
    op.drop_table('verification_feed_flags')
    op.drop_table('verification_feed_signals')
    op.drop_table('verification_feed_attachments')
    op.drop_table('verification_feed_post_versions')
    op.drop_table('verification_feed_posts')

    # Drop named enum types
    for name in [
        'trusttier', 'moderationaction', 'flagreason', 'signaltype',
        'aiprescreenverdict', 'poststate', 'postcategory', 'postscope',
    ]:
        sa.Enum(name=name).drop(op.get_bind(), checkfirst=True)
