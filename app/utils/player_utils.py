"""Player data utilities: name normalization, SVG fallback, per-90 calc."""
import re
import unicodedata

# Priority list for Onda 1 seed — Brazilians abroad
BRASILEIROS_PRIORITY = [
    {'name': 'Vinicius Junior', 'team': 'Real Madrid', 'league': 'La Liga'},
    {'name': 'Rodrygo', 'team': 'Real Madrid', 'league': 'La Liga'},
    {'name': 'Endrick', 'team': 'Real Madrid', 'league': 'La Liga'},
    {'name': 'Raphinha', 'team': 'Barcelona', 'league': 'La Liga'},
    {'name': 'Gabriel Magalhaes', 'team': 'Arsenal', 'league': 'Premier League'},
    {'name': 'Gabriel Martinelli', 'team': 'Arsenal', 'league': 'Premier League'},
    {'name': 'Gabriel Jesus', 'team': 'Arsenal', 'league': 'Premier League'},
    {'name': 'Richarlison', 'team': 'Tottenham', 'league': 'Premier League'},
    {'name': 'Ederson', 'team': 'Manchester City', 'league': 'Premier League'},
    {'name': 'Alisson', 'team': 'Liverpool', 'league': 'Premier League'},
    {'name': 'Lucas Paqueta', 'team': 'West Ham', 'league': 'Premier League'},
    {'name': 'Bruno Guimaraes', 'team': 'Newcastle', 'league': 'Premier League'},
    {'name': 'Danilo', 'team': 'Juventus', 'league': 'Serie A'},
    {'name': 'Bremer', 'team': 'Juventus', 'league': 'Serie A'},
]

# ISO2 nationality → flag emoji
_ISO2_FLAGS: dict[str, str] = {
    'BR': '🇧🇷', 'GB': '🏴󠁧󠁢󠁥󠁮󠁧󠁿', 'ES': '🇪🇸', 'DE': '🇩🇪',
    'FR': '🇫🇷', 'IT': '🇮🇹', 'PT': '🇵🇹', 'AR': '🇦🇷',
    'US': '🇺🇸', 'NL': '🇳🇱', 'BE': '🇧🇪', 'HR': '🇭🇷',
}


def normalize_player_name(name: str) -> str:
    """Lowercase ASCII, strip accents, articles and punctuation for fuzzy matching."""
    nfkd = unicodedata.normalize('NFKD', name)
    ascii_name = nfkd.encode('ASCII', 'ignore').decode('ASCII')
    clean = re.sub(r'[^a-z0-9 ]', '', ascii_name.lower())
    for article in ['de ', 'da ', 'das ', 'do ', 'dos ', 'van ', 'van den ',
                    'van der ', 'von ', 'el ', 'al ', 'bin ']:
        clean = clean.replace(article, '')
    return clean.strip()


def calc_per90(value, minutes: int | None) -> float | None:
    """Return value per 90 minutes; None if minutes <= 0 or value is None."""
    if value is None or not minutes or minutes <= 0:
        return None
    return round(float(value) / minutes * 90, 3)


def position_group(raw_position: str | None) -> str:
    """Normalise raw position string to GK | DEF | MID | ATT."""
    if not raw_position:
        return 'MID'
    pos = raw_position.upper()
    if 'GK' in pos or 'GOAL' in pos or 'PORTEIRO' in pos or 'GOLEIRO' in pos:
        return 'GK'
    if any(x in pos for x in ['DEF', 'BACK', 'ZAGU', 'LATERA']):
        return 'DEF'
    if any(x in pos for x in ['ATT', 'FOR', 'WING', 'ATTACK', 'AVANT']):
        return 'ATT'
    return 'MID'


def generate_svg_fallback(initials: str, bg_color: str = '#1a237e') -> str:
    """Return an SVG string with player initials as fallback avatar."""
    letters = (initials or 'FX')[:2].upper()
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="80" height="80" '
        f'viewBox="0 0 80 80"><circle cx="40" cy="40" r="40" fill="{bg_color}"/>'
        f'<text x="40" y="46" font-family="Arial,sans-serif" font-size="28" '
        f'font-weight="bold" fill="#ffffff" text-anchor="middle">{letters}</text></svg>'
    )


def parse_market_value(raw: str) -> int | None:
    """Parse '€45M' or '€500K' or '45,000,000' into integer euros."""
    if not raw:
        return None
    raw = raw.replace(',', '').replace(' ', '').upper()
    raw = re.sub(r'[€$]', '', raw)
    try:
        if 'M' in raw:
            return int(float(raw.replace('M', '')) * 1_000_000)
        if 'K' in raw:
            return int(float(raw.replace('K', '')) * 1_000)
        return int(float(raw))
    except (ValueError, TypeError):
        return None


def flag_emoji(iso2: str | None) -> str:
    return _ISO2_FLAGS.get((iso2 or '').upper(), '')
