"""Worker 7 — Generate LLM narrative bios for players.

Monthly + triggered after transfers or career milestones.
Uses the existing multi-provider LLM pipeline (Groq → Gemini → Ollama).
"""
import json
import logging
from datetime import datetime, timezone

from ..models import db, Player, PlayerSeasonStats, PlayerMarketValue
from ..services.report_generator import gerar_relatorio_stream

logger = logging.getLogger(__name__)

SEASON_LABEL = '2024-25'


def run(player_ids: list[int] | None = None, force: bool = False) -> int:
    """Generate or refresh bio_llm for players that need it.

    force=True regenerates even if bio_llm already exists.
    """
    if player_ids:
        players = Player.query.filter(Player.id.in_(player_ids)).all()
    else:
        query = Player.query
        if not force:
            query = query.filter(Player.bio_llm.is_(None))
        players = query.limit(20).all()  # batch of 20 to avoid LLM rate limits

    generated = 0
    for player in players:
        try:
            if _generate_bio(player):
                generated += 1
        except Exception as e:
            logger.error("player_bio_worker player %d: %s", player.id, e)

    db.session.commit()
    logger.info("player_bio_worker: %d bios generated", generated)
    return generated


def _generate_bio(player: Player) -> bool:
    ctx = _build_context(player)
    prompt = _build_prompt(player, ctx)

    try:
        bio = ''.join(gerar_relatorio_stream('bio_jogador', {'_prompt_override': prompt}))
        if bio:
            player.bio_llm = bio[:3000]
            player.updated_at = datetime.now(timezone.utc)
            return True
    except Exception as e:
        logger.warning("bio generation for %s: %s", player.name, e)
    return False


def _build_context(player: Player) -> dict:
    season_stats = PlayerSeasonStats.query.filter_by(
        player_id=player.id, season=SEASON_LABEL,
    ).first()
    market_value = (
        PlayerMarketValue.query
        .filter_by(player_id=player.id)
        .order_by(PlayerMarketValue.value_date.desc())
        .first()
    )

    ctx: dict = {
        'name': player.name_short or player.name,
        'nationality': player.nationality or 'Desconhecida',
        'position': player.position or 'Desconhecida',
        'age': player.age,
        'team': None,
        'bio_source': player.bio_text,
        'market_value_eur': market_value.value_eur if market_value else None,
    }

    if player.team_id:
        from ..models import Team
        team = Team.query.get(player.team_id)
        if team:
            ctx['team'] = team.name

    if season_stats:
        ctx.update({
            'goals': season_stats.goals,
            'assists': season_stats.assists,
            'minutes': season_stats.minutes_played,
            'appearances': season_stats.appearances,
            'xg': float(season_stats.xg) if season_stats.xg else None,
            'xa': float(season_stats.xa) if season_stats.xa else None,
            'xg_per90': float(season_stats.xg_per90) if season_stats.xg_per90 else None,
            'rating_avg': float(season_stats.rating_avg) if season_stats.rating_avg else None,
        })

    return ctx


def _build_prompt(player: Player, ctx: dict) -> str:
    data_json = json.dumps(ctx, ensure_ascii=False, indent=2)
    return (
        "Você é um analista esportivo do FutMetricX.\n"
        "Com base nos dados a seguir, escreva uma bio analítica em 3 parágrafos:\n"
        "- Parágrafo 1: quem é o jogador, perfil de jogo, características principais\n"
        "- Parágrafo 2: temporada atual em números e contexto\n"
        "- Parágrafo 3: trajetória e momento de carreira\n\n"
        "Tom: analítico mas acessível. Sem clichês. Direto.\n"
        "Responda em português do Brasil. Máximo 350 palavras.\n\n"
        f"Dados:\n{data_json}"
    )
