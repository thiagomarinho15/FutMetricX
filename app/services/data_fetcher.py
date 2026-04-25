import json
import logging
import math
from datetime import datetime, timezone

from statsbombpy import sb

from ..models import db, Partida

logger = logging.getLogger(__name__)

# Most relevant competitions for the Ibero-American audience
TARGET_COMPETITIONS = [
    (11, 'La Liga'),
    (16, 'Champions League'),
    (2,  'Premier League'),
]


def popular_partidas_iniciais():
    """Import one season per competition from StatsBomb Open Data. Idempotent."""
    if Partida.query.count() > 0:
        return
    logger.info('StatsBomb: iniciando importação de dados...')
    try:
        comps = sb.competitions()
        for comp_id, comp_name in TARGET_COMPETITIONS:
            subset = comps[comps['competition_id'] == comp_id]
            if subset.empty:
                continue
            latest = _latest_season_row(subset)
            season_id = int(latest['season_id'])
            season_name = str(latest['season_name'])
            try:
                n = _importar_temporada(comp_id, season_id, comp_name, season_name)
                logger.info('%d partidas importadas: %s %s', n, comp_name, season_name)
                print(f'  → {n} partidas: {comp_name} {season_name}')
            except Exception as exc:
                logger.warning('Falha em %s: %s', comp_name, exc)
    except Exception as exc:
        logger.warning('StatsBomb indisponível: %s', exc)
        print(f'  Aviso: dados StatsBomb não carregados ({exc})')


def _importar_temporada(comp_id, season_id, comp_name, season_name):
    matches = sb.matches(competition_id=comp_id, season_id=season_id)
    added = 0
    for _, row in matches.iterrows():
        sid = int(row['match_id'])
        if Partida.query.filter_by(statsbomb_id=sid).first():
            continue
        p = Partida(
            statsbomb_id=sid,
            time_casa=_team_name(row.get('home_team', '')),
            time_visitante=_team_name(row.get('away_team', '')),
            competicao=comp_name,
            temporada=season_name,
            rodada=_safe_int(row.get('match_week')),
            data_partida=_parse_date(row.get('match_date')),
            status='encerrada',
            stats_json=json.dumps({
                'placar_casa': _safe_int(row.get('home_score')),
                'placar_visitante': _safe_int(row.get('away_score')),
            }),
        )
        db.session.add(p)
        added += 1
    db.session.commit()
    return added


def _latest_season_row(rows):
    """Pick the season with the most recent year from season_name (e.g. '2019/2020' → 2020)."""
    def _max_year(name):
        parts = str(name).replace('/', ' ').split()
        years = [int(p) for p in parts if p.isdigit() and len(p) == 4]
        return max(years) if years else 0
    idx = rows['season_name'].apply(_max_year).idxmax()
    return rows.loc[idx]


def _team_name(val) -> str:
    if isinstance(val, dict):
        for key in ('home_team_name', 'away_team_name', 'team_name', 'name'):
            if key in val:
                return str(val[key])
        # fallback: first string value found
        for v in val.values():
            if isinstance(v, str):
                return v
        return ''
    return str(val) if val else ''


def _parse_date(val):
    if not val:
        return None
    try:
        if isinstance(val, float) and math.isnan(val):
            return None
        return datetime.strptime(str(val)[:10], '%Y-%m-%d').replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def _safe_int(val):
    if val is None:
        return None
    try:
        f = float(val)
        return None if math.isnan(f) else int(f)
    except (TypeError, ValueError):
        return None
