"""player data layer — extend players + 4 new tables

Revision ID: b4c7d1e2f3a8
Revises: 737bfccc61cc
Create Date: 2026-04-26

If Alembic reports the base revision is missing, run:
    flask db stamp 737bfccc61cc
    flask db upgrade
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'b4c7d1e2f3a8'
down_revision = '737bfccc61cc'
branch_labels = None
depends_on = None


def upgrade():
    # ── Extend players table ───────────────────────────────────────────────────
    with op.batch_alter_table('players') as batch_op:
        batch_op.add_column(sa.Column('name_full', sa.String(200), nullable=True))
        batch_op.add_column(sa.Column('name_short', sa.String(100), nullable=True))
        batch_op.add_column(sa.Column('nationality_iso2', sa.String(2), nullable=True))
        batch_op.add_column(sa.Column('date_of_birth', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('height_cm', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('weight_kg', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('foot_dominant', sa.String(10), nullable=True))
        batch_op.add_column(sa.Column('shirt_number', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('contract_until', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'))
        batch_op.add_column(sa.Column('external_id_understat', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('external_id_transfermarkt', sa.String(50), nullable=True))
        batch_op.add_column(sa.Column('external_id_fbref', sa.String(100), nullable=True))
        batch_op.add_column(sa.Column('external_id_sportsdb', sa.String(50), nullable=True))
        batch_op.add_column(sa.Column('photo_url_local', sa.String(500), nullable=True))
        batch_op.add_column(sa.Column('photo_url_apifootball', sa.String(500), nullable=True))
        batch_op.add_column(sa.Column('photo_url_sportsdb_thumb', sa.String(500), nullable=True))
        batch_op.add_column(sa.Column('photo_url_sportsdb_cutout', sa.String(500), nullable=True))
        batch_op.add_column(sa.Column('bio_text', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('bio_llm', sa.Text(), nullable=True))

    # ── player_season_stats ────────────────────────────────────────────────────
    op.create_table(
        'player_season_stats',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('player_id', sa.Integer(), sa.ForeignKey('players.id', ondelete='CASCADE'), nullable=False),
        sa.Column('team_id', sa.Integer(), sa.ForeignKey('teams.id'), nullable=True),
        sa.Column('competition_id', sa.Integer(), sa.ForeignKey('competitions.id'), nullable=True),
        sa.Column('season', sa.String(10), nullable=False),
        sa.Column('appearances', sa.Integer(), server_default='0'),
        sa.Column('starts', sa.Integer(), server_default='0'),
        sa.Column('minutes_played', sa.Integer(), server_default='0'),
        sa.Column('goals', sa.Integer(), server_default='0'),
        sa.Column('assists', sa.Integer(), server_default='0'),
        sa.Column('shots_total', sa.Integer(), server_default='0'),
        sa.Column('shots_on_target', sa.Integer(), server_default='0'),
        sa.Column('shot_accuracy_pct', sa.Numeric(5, 2), nullable=True),
        sa.Column('passes_total', sa.Integer(), server_default='0'),
        sa.Column('pass_accuracy_pct', sa.Numeric(5, 2), nullable=True),
        sa.Column('key_passes', sa.Integer(), server_default='0'),
        sa.Column('dribbles_attempted', sa.Integer(), server_default='0'),
        sa.Column('dribbles_success', sa.Integer(), server_default='0'),
        sa.Column('duels_total', sa.Integer(), server_default='0'),
        sa.Column('duels_won', sa.Integer(), server_default='0'),
        sa.Column('aerial_duels_won', sa.Integer(), server_default='0'),
        sa.Column('yellow_cards', sa.Integer(), server_default='0'),
        sa.Column('red_cards', sa.Integer(), server_default='0'),
        sa.Column('fouls_committed', sa.Integer(), server_default='0'),
        sa.Column('fouls_drawn', sa.Integer(), server_default='0'),
        sa.Column('xg', sa.Numeric(6, 3), nullable=True),
        sa.Column('xa', sa.Numeric(6, 3), nullable=True),
        sa.Column('npxg', sa.Numeric(6, 3), nullable=True),
        sa.Column('xg_chain', sa.Numeric(6, 3), nullable=True),
        sa.Column('xg_buildup', sa.Numeric(6, 3), nullable=True),
        sa.Column('xg_per90', sa.Numeric(5, 3), nullable=True),
        sa.Column('xa_per90', sa.Numeric(5, 3), nullable=True),
        sa.Column('goals_per90', sa.Numeric(5, 3), nullable=True),
        sa.Column('assists_per90', sa.Numeric(5, 3), nullable=True),
        sa.Column('progressive_carries', sa.Integer(), nullable=True),
        sa.Column('progressive_passes_fbref', sa.Integer(), nullable=True),
        sa.Column('pressures', sa.Integer(), nullable=True),
        sa.Column('defensive_actions', sa.Integer(), nullable=True),
        sa.Column('rating_avg', sa.Numeric(4, 2), nullable=True),
        sa.Column('source_base', sa.String(50), server_default='api-football'),
        sa.Column('source_advanced', sa.String(50), server_default='understat'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('player_id', 'competition_id', 'season', name='uq_player_season_comp'),
    )
    op.create_index('idx_pss_player', 'player_season_stats', ['player_id'])
    op.create_index('idx_pss_season', 'player_season_stats', ['season'])

    # ── player_market_value ────────────────────────────────────────────────────
    op.create_table(
        'player_market_value',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('player_id', sa.Integer(), sa.ForeignKey('players.id', ondelete='CASCADE'), nullable=False),
        sa.Column('value_eur', sa.BigInteger(), nullable=True),
        sa.Column('value_date', sa.Date(), nullable=False),
        sa.Column('team_id', sa.Integer(), sa.ForeignKey('teams.id'), nullable=True),
        sa.Column('source', sa.String(50), server_default='transfermarkt'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('player_id', 'value_date', name='uq_player_market_date'),
    )
    op.create_index('idx_pmv_player', 'player_market_value', ['player_id'])

    # ── player_percentiles ─────────────────────────────────────────────────────
    op.create_table(
        'player_percentiles',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('player_id', sa.Integer(), sa.ForeignKey('players.id', ondelete='CASCADE'), nullable=False),
        sa.Column('competition_id', sa.Integer(), sa.ForeignKey('competitions.id'), nullable=True),
        sa.Column('season', sa.String(10), nullable=True),
        sa.Column('position_group', sa.String(20), nullable=True),
        sa.Column('pct_goals', sa.SmallInteger(), nullable=True),
        sa.Column('pct_assists', sa.SmallInteger(), nullable=True),
        sa.Column('pct_xg', sa.SmallInteger(), nullable=True),
        sa.Column('pct_xa', sa.SmallInteger(), nullable=True),
        sa.Column('pct_xg_per90', sa.SmallInteger(), nullable=True),
        sa.Column('pct_progressive_passes', sa.SmallInteger(), nullable=True),
        sa.Column('pct_progressive_carries', sa.SmallInteger(), nullable=True),
        sa.Column('pct_pressures', sa.SmallInteger(), nullable=True),
        sa.Column('pct_pass_accuracy', sa.SmallInteger(), nullable=True),
        sa.Column('pct_aerial_duels_won', sa.SmallInteger(), nullable=True),
        sa.Column('pct_dribbles_success', sa.SmallInteger(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('player_id', 'competition_id', 'season', name='uq_player_percentiles'),
    )
    op.create_index('idx_pp_player', 'player_percentiles', ['player_id'])

    # ── player_id_mapping ──────────────────────────────────────────────────────
    op.create_table(
        'player_id_mapping',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('player_id', sa.Integer(), sa.ForeignKey('players.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source', sa.String(50), nullable=False),
        sa.Column('external_id', sa.String(100), nullable=False),
        sa.Column('confidence', sa.String(20), server_default='auto'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('source', 'external_id', name='uq_player_id_mapping'),
    )
    op.create_index('idx_pim_player', 'player_id_mapping', ['player_id'])


def downgrade():
    op.drop_table('player_id_mapping')
    op.drop_table('player_percentiles')
    op.drop_table('player_market_value')
    op.drop_table('player_season_stats')
    with op.batch_alter_table('players') as batch_op:
        for col in [
            'name_full', 'name_short', 'nationality_iso2', 'date_of_birth',
            'height_cm', 'weight_kg', 'foot_dominant', 'shirt_number',
            'contract_until', 'is_active', 'external_id_understat',
            'external_id_transfermarkt', 'external_id_fbref', 'external_id_sportsdb',
            'photo_url_local', 'photo_url_apifootball',
            'photo_url_sportsdb_thumb', 'photo_url_sportsdb_cutout',
            'bio_text', 'bio_llm',
        ]:
            batch_op.drop_column(col)
