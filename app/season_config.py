"""Central season configuration — import from here, never hardcode season strings."""

CURRENT_SEASON_YEAR: int = 2025          # API-Football / Understat season param (fixtures/xG)
# API-Football free tier only allows seasons up to 2024 for the /teams endpoint.
# Squads are fetched without a season param to get the most current roster.
SQUAD_API_SEASON: int = 2024            # Used for /teams listing on free tier
SEASON_LABEL_EUROPE: str = '2025-26'    # Competition.season for European leagues in our DB
SEASON_LABEL_BRASIL: str = '2025'       # Competition.season for Brasileirão in our DB

BRASILEIRAO_LEAGUES: frozenset = frozenset({'Brasileirão'})


def season_label(competition_name: str) -> str:
    """Return canonical season string for a competition."""
    return SEASON_LABEL_BRASIL if competition_name in BRASILEIRAO_LEAGUES else SEASON_LABEL_EUROPE
