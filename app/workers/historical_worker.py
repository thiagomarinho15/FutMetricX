"""Nightly enrichment of historical data via FBref and openfootball."""
import logging

logger = logging.getLogger(__name__)

# FBref uses Cloudflare — access via soccerdata library with browser-like headers.
# openfootball is raw GitHub JSON, no auth required.
# Both run in nightly jobs to avoid hitting rate limits during peak hours.


def run_openfootball(competition: str | None = None) -> int:
    """
    Seed historical fixtures from openfootball GitHub JSON files.
    https://github.com/openfootball
    Useful for seeding head-to-head context for historical matches.
    """
    logger.info("historical_worker (openfootball): starting")
    # TODO: implement openfootball seed once match ID mapping is established
    # Data available at: https://github.com/openfootball/eng-england (Premier League)
    # and https://github.com/openfootball/champions-league
    logger.info("historical_worker (openfootball): stub — not yet implemented")
    return 0


def run_fbref(league: str | None = None, season: int | None = None) -> int:
    """
    Enrich player profiles with historical stats from FBref via soccerdata.
    Used for cross-season comparisons in narrative reports.
    Runs weekly overnight — Cloudflare requires respectful access.
    """
    logger.info("historical_worker (fbref): starting")
    # TODO: implement via soccerdata library
    # pip install soccerdata
    # import soccerdata as sd
    # fbref = sd.FBref(leagues=["ENG-Premier League"], seasons=[season])
    # player_stats = fbref.read_player_season_stats()
    logger.info("historical_worker (fbref): stub — not yet implemented")
    return 0
