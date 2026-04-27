"""Central season configuration — import from here, never hardcode season strings."""

CURRENT_SEASON_YEAR: int = 2025          # API-Football / Understat season param
SEASON_LABEL_EUROPE: str = '2025-26'     # Competition.season for European leagues
SEASON_LABEL_BRASIL: str = '2025'        # Competition.season for Brasileirão

BRASILEIRAO_LEAGUES: frozenset = frozenset({'Brasileirão'})


def season_label(competition_name: str) -> str:
    """Return canonical season string for a competition."""
    return SEASON_LABEL_BRASIL if competition_name in BRASILEIRAO_LEAGUES else SEASON_LABEL_EUROPE
