"""Worker — Deduplicate teams across sources using name matching.

Problem: the same Arsenal FC can exist as both source_name='football-data' (from
fixtures_worker) and source_name='api-football' (from squad_refresh_worker). This
breaks JOINs between fixtures and player stats.

Solution: set canonical_team_id on each duplicate row pointing to the api-football
entry, which is the authoritative source (has squads, logos, IDs for all other workers).

Run after squad_refresh_worker whenever new teams are added.
"""
import logging
import unicodedata
import re

from ..models import db, Team

logger = logging.getLogger(__name__)

# Sources in priority order — api-football is canonical
SOURCE_PRIORITY = ['api-football', 'football-data', 'statsbomb', 'understat']


def run() -> int:
    """Set canonical_team_id for all non-canonical duplicate teams.

    Returns number of teams updated.
    """
    all_teams = Team.query.all()
    updated = _resolve_duplicates(all_teams)
    db.session.commit()
    logger.info("team_dedup_worker: %d teams linked to canonical entry", updated)
    return updated


def _resolve_duplicates(teams: list[Team]) -> int:
    # Build a map: normalised_name → list of Team objects
    name_groups: dict[str, list[Team]] = {}
    for team in teams:
        key = _normalise(team.name)
        name_groups.setdefault(key, []).append(team)

    updated = 0
    for key, group in name_groups.items():
        if len(group) < 2:
            continue

        # Pick canonical: highest priority source with a source_id
        canonical = _pick_canonical(group)
        if not canonical:
            continue

        for team in group:
            if team.id == canonical.id:
                team.canonical_team_id = None  # canonical points to itself = NULL
                continue
            if team.canonical_team_id != canonical.id:
                team.canonical_team_id = canonical.id
                updated += 1
                logger.debug(
                    "dedup: %r (src=%s id=%s) → canonical id=%d (src=%s)",
                    team.name, team.source_name, team.source_id,
                    canonical.id, canonical.source_name,
                )

    return updated


def _pick_canonical(group: list[Team]) -> Team | None:
    for preferred_source in SOURCE_PRIORITY:
        for team in group:
            if team.source_name == preferred_source and team.source_id:
                return team
    return group[0] if group else None


def _normalise(name: str) -> str:
    """Lower-case, remove accents, strip common suffixes for fuzzy matching."""
    name = name.lower().strip()
    # Remove accents
    name = ''.join(
        c for c in unicodedata.normalize('NFD', name)
        if unicodedata.category(c) != 'Mn'
    )
    # Remove common suffixes
    for suffix in (' fc', ' cf', ' sc', ' ac', ' if', ' bv', ' afc', ' fk', ' sk'):
        if name.endswith(suffix):
            name = name[: -len(suffix)].strip()
    # Collapse whitespace and non-alphanumeric
    name = re.sub(r'[^a-z0-9 ]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name
