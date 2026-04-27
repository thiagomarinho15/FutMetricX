"""season 2025 db update — logo_url, canonical_team_id, worker_log

Revision ID: a1b2c3d4e5f6
Revises: 766b4f44ebb8
Create Date: 2026-04-27 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


revision = 'a1b2c3d4e5f6'
down_revision = '766b4f44ebb8'
branch_labels = None
depends_on = None


def _col_exists(table: str, col: str) -> bool:
    bind = op.get_bind()
    return col in [c['name'] for c in inspect(bind).get_columns(table)]


def _table_exists(table: str) -> bool:
    bind = op.get_bind()
    return inspect(bind).has_table(table)


def upgrade():
    # ── teams: visual assets + dedup ─────────────────────────────────────────
    if not _col_exists('teams', 'logo_url'):
        op.execute(text('ALTER TABLE teams ADD COLUMN logo_url VARCHAR(500)'))
    if not _col_exists('teams', 'banner_url'):
        op.execute(text('ALTER TABLE teams ADD COLUMN banner_url VARCHAR(500)'))
    if not _col_exists('teams', 'canonical_team_id'):
        op.execute(text(
            'ALTER TABLE teams ADD COLUMN canonical_team_id INTEGER '
            'REFERENCES teams(id)'
        ))

    # ── worker_log ────────────────────────────────────────────────────────────
    if not _table_exists('worker_log'):
        op.create_table(
            'worker_log',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('worker_name', sa.String(length=100), nullable=False),
            sa.Column('status', sa.String(length=20), nullable=True),
            sa.Column('started_at', sa.DateTime(), nullable=True),
            sa.Column('finished_at', sa.DateTime(), nullable=True),
            sa.Column('rows_affected', sa.Integer(), nullable=True),
            sa.Column('error_msg', sa.Text(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )


def downgrade():
    if _table_exists('worker_log'):
        op.drop_table('worker_log')

    if _col_exists('teams', 'canonical_team_id'):
        op.execute(text('ALTER TABLE teams DROP COLUMN canonical_team_id'))
    if _col_exists('teams', 'banner_url'):
        op.execute(text('ALTER TABLE teams DROP COLUMN banner_url'))
    if _col_exists('teams', 'logo_url'):
        op.execute(text('ALTER TABLE teams DROP COLUMN logo_url'))
