"""
Team logo URLs (Wikipedia Commons SVG) + CSS avatar helpers.
For teams without a mapped URL the template falls back to a coloured
initial-based avatar, so broken / missing entries degrade gracefully.
"""

# Wikipedia Commons direct SVG URLs — no auth required, stable links
TEAM_LOGOS: dict[str, str] = {
    # Premier League
    'Arsenal':                  'https://upload.wikimedia.org/wikipedia/en/5/53/Arsenal_FC.svg',
    'Chelsea':                  'https://upload.wikimedia.org/wikipedia/en/c/cc/Chelsea_FC.svg',
    'Manchester United':        'https://upload.wikimedia.org/wikipedia/en/7/7a/Manchester_United_FC_crest.svg',
    'Liverpool':                'https://upload.wikimedia.org/wikipedia/en/0/0c/Liverpool_FC.svg',
    'Manchester City':          'https://upload.wikimedia.org/wikipedia/en/e/eb/Manchester_City_FC_badge.svg',
    'Tottenham Hotspur':        'https://upload.wikimedia.org/wikipedia/en/b/b4/Tottenham_Hotspur.svg',
    'Newcastle United':         'https://upload.wikimedia.org/wikipedia/en/5/56/Newcastle_United_Logo.svg',
    'Everton':                  'https://upload.wikimedia.org/wikipedia/en/7/7c/Everton_FC_logo.svg',
    'Aston Villa':              'https://upload.wikimedia.org/wikipedia/en/f/f9/Aston_Villa_FC_crest_%282016%29.svg',
    'Leeds United':             'https://upload.wikimedia.org/wikipedia/en/5/54/Leeds_United_F.C._logo.svg',
    'Blackburn Rovers':         'https://upload.wikimedia.org/wikipedia/en/0/0f/Blackburn_Rovers.svg',
    'Bolton Wanderers':         'https://upload.wikimedia.org/wikipedia/en/8/82/Bolton_Wanderers_FC_logo.svg',
    'Fulham':                   'https://upload.wikimedia.org/wikipedia/en/e/eb/Fulham_FC_%28shield%29.svg',
    'Southampton':              'https://upload.wikimedia.org/wikipedia/en/c/c9/FC_Southampton.svg',
    'Birmingham City':          'https://upload.wikimedia.org/wikipedia/en/6/68/Birmingham_City_FC_logo.svg',
    'Charlton Athletic':        'https://upload.wikimedia.org/wikipedia/en/2/2e/Charlton_Athletic_FC_crest.svg',
    'Leicester City':           'https://upload.wikimedia.org/wikipedia/en/2/2d/Leicester_City_crest.svg',
    'Middlesbrough':            'https://upload.wikimedia.org/wikipedia/en/2/2c/Middlesbrough_FC_crest.svg',
    'Portsmouth':               'https://upload.wikimedia.org/wikipedia/en/3/3d/Portsmouth_FC_logo.svg',
    'Wolverhampton Wanderers':  'https://upload.wikimedia.org/wikipedia/en/f/fc/Wolverhampton_Wanderers.svg',
    # La Liga / Champions League
    'Real Madrid':              'https://upload.wikimedia.org/wikipedia/en/5/56/Real_Madrid_CF.svg',
    'Barcelona':                'https://upload.wikimedia.org/wikipedia/en/4/47/FC_Barcelona_%28crest%29.svg',
    'Juventus':                 'https://upload.wikimedia.org/wikipedia/commons/1/15/Juventus_FC_2017_icon_%28black%29.svg',
    'Ajax':                     'https://upload.wikimedia.org/wikipedia/en/7/79/Ajax_Amsterdam.svg',
    # Brazilian clubs (for future seasons)
    'Flamengo':                 'https://upload.wikimedia.org/wikipedia/commons/2/2e/Flamengo_braz_logo.svg',
    'Palmeiras':                'https://upload.wikimedia.org/wikipedia/commons/1/10/Palmeiras_logo.svg',
    'Corinthians':              'https://upload.wikimedia.org/wikipedia/commons/5/59/Sport_Club_Corinthians_Paulista_crest.svg',
    'São Paulo':                'https://upload.wikimedia.org/wikipedia/commons/6/63/S%C3%A3o_Paulo_FC_escudo.svg',
    'Atlético Mineiro':         'https://upload.wikimedia.org/wikipedia/commons/c/c6/Atletico_mineiro_galo.svg',
    'Santos':                   'https://upload.wikimedia.org/wikipedia/commons/1/14/Santos_FC_logo.svg',
}

# Deterministic colour palette — same team always gets the same colour
_PALETTE = [
    '#c0392b', '#1a472a', '#2d6a4f', '#285E8E',
    '#7b2d8b', '#d35400', '#1d3557', '#16a085',
    '#8e44ad', '#2c3e50', '#b7950b', '#117a65',
]


def team_logo(name: str) -> str | None:
    return TEAM_LOGOS.get(name)


def team_initial(name: str) -> str:
    words = name.split()
    if len(words) >= 2:
        return (words[0][0] + words[-1][0]).upper()
    return name[:2].upper()


def team_color(name: str) -> str:
    return _PALETTE[sum(ord(c) for c in name) % len(_PALETTE)]
