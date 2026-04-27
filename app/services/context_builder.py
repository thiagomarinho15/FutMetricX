"""Builds enriched LLM context from current-season database records.

Replaces the old StatsBomb-based montar_contexto. Always filters by the
active season (2025-26 for Europe, 2025 for Brasileirão).
"""
from __future__ import annotations

from ..models import Fixture, Player, PlayerSeasonStats, TeamForm, Team
from ..season_config import season_label


def build_fixture_context(fixture: Fixture) -> dict:
    """Assemble full match context from current-season data for LLM consumption."""
    comp = fixture.competition
    home = fixture.home_team
    away = fixture.away_team
    s_label = season_label(comp.name) if comp else '2025-26'

    ctx: dict = {
        'time_casa': home.name if home else '?',
        'time_visitante': away.name if away else '?',
        'competicao': comp.name if comp else '?',
        'temporada': s_label,
        'rodada': None,
        'data': fixture.scheduled_at.strftime('%d/%m/%Y') if fixture.scheduled_at else None,
        'placar_casa': fixture.home_score,
        'placar_visitante': fixture.away_score,
    }

    if home:
        ctx['form_casa'] = _team_form(home.id, fixture.competition_id)
        ctx['destaques_casa'] = _top_players(home.id, fixture.competition_id, s_label)

    if away:
        ctx['form_visitante'] = _team_form(away.id, fixture.competition_id)
        ctx['destaques_visitante'] = _top_players(away.id, fixture.competition_id, s_label)

    return ctx


def _team_form(team_id: int, competition_id: int | None) -> dict:
    form = TeamForm.query.filter_by(
        team_id=team_id,
        competition_id=competition_id,
    ).first()
    if not form:
        return {}
    return {
        'ultimos_5': form.last_5,
        'vitorias': form.wins,
        'empates': form.draws,
        'derrotas': form.losses,
        'gols_marcados': form.goals_scored,
        'gols_sofridos': form.goals_conceded,
        'xg_medio': float(form.xg_avg) if form.xg_avg else None,
        'xga_medio': float(form.xga_avg) if form.xga_avg else None,
    }


def _top_players(team_id: int, competition_id: int | None, s_label: str) -> list[dict]:
    """Return top 3 players by goals+assists for the team in the current season."""
    rows = (
        PlayerSeasonStats.query
        .filter_by(team_id=team_id, season=s_label)
        .filter(PlayerSeasonStats.minutes_played > 90)
        .all()
    )
    if competition_id:
        filtered = [r for r in rows if r.competition_id == competition_id]
        if filtered:
            rows = filtered

    rows.sort(key=lambda r: (r.goals or 0) + (r.assists or 0), reverse=True)
    result = []
    for row in rows[:3]:
        player = Player.query.get(row.player_id)
        if not player:
            continue
        entry: dict = {
            'nome': player.name_short or player.name,
            'posicao': player.position,
            'gols': row.goals,
            'assistencias': row.assists,
            'aparicoes': row.appearances,
            'minutos': row.minutes_played,
        }
        if row.xg:
            entry['xg'] = float(row.xg)
        if row.xg_per90:
            entry['xg_por90'] = float(row.xg_per90)
        result.append(entry)
    return result
