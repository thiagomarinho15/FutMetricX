"""FBref advanced stats via soccerdata library."""
import logging
from typing import Any

logger = logging.getLogger(__name__)

# soccerdata league slugs that FBref supports
FBREF_LEAGUES: dict[str, str] = {
    'Premier League': 'ENG-Premier League',
    'La Liga': 'ESP-La Liga',
    'Bundesliga': 'GER-Bundesliga',
    'Serie A': 'ITA-Serie A',
    'Ligue 1': 'FRA-Ligue 1',
    'Champions League': 'INT-UEFA Champions League',
}


def get_player_stats(league: str, season: str) -> list[dict[str, Any]]:
    """
    Fetch advanced player season stats from FBref via soccerdata.
    Returns list of dicts with: player_name, team, progressive_carries,
    progressive_passes, pressures, defensive_actions.

    season format: "2024" (soccerdata uses the calendar year of season start).
    """
    slug = FBREF_LEAGUES.get(league)
    if not slug:
        logger.warning("fbref: league %r not supported", league)
        return []
    try:
        import soccerdata as sd
        fbref = sd.FBref(leagues=slug, seasons=int(season))

        # Standard stats (goals, assists, minutes)
        std = fbref.read_player_season_stats(stat_type='standard')

        # Possession stats (carries, progressive passes)
        try:
            pos = fbref.read_player_season_stats(stat_type='possession')
        except Exception:
            pos = None

        # Defensive stats (pressures, def actions)
        try:
            dfn = fbref.read_player_season_stats(stat_type='defense')
        except Exception:
            dfn = None

        return _merge_stats(std, pos, dfn)
    except ImportError:
        logger.error("fbref: soccerdata not installed — run: pip install soccerdata")
        return []
    except Exception as e:
        logger.error("fbref get_player_stats %s %s: %s", league, season, e)
        return []


def _merge_stats(std, pos, dfn) -> list[dict]:
    """Flatten and merge soccerdata DataFrames into list of dicts."""
    try:
        import pandas as pd
        result: dict[str, dict] = {}

        def _add(df, fields: dict[str, str]):
            if df is None:
                return
            df = df.reset_index()
            for _, row in df.iterrows():
                key = str(row.get('player', '')).lower().strip()
                if key not in result:
                    result[key] = {'player_name': row.get('player', ''), 'team': row.get('team', '')}
                for col, alias in fields.items():
                    val = row.get(col)
                    if val is not None and not (isinstance(val, float) and pd.isna(val)):
                        result[key][alias] = int(val) if isinstance(val, (int, float)) else val

        _add(std, {'MP': 'appearances', 'Min': 'minutes_played',
                   'Gls': 'goals', 'Ast': 'assists'})
        _add(pos, {'PrgC': 'progressive_carries', 'PrgP': 'progressive_passes'})
        _add(dfn, {'Press': 'pressures', 'Tkl': 'defensive_actions'})

        return list(result.values())
    except Exception as e:
        logger.error("fbref _merge_stats: %s", e)
        return []
