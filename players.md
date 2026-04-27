# FutMetricX — Plano de Dados de Jogadores (players.md)

## Objetivo

Construir um perfil rico e atualizado para cada jogador do banco de dados do FutMetricX, cobrindo foto, dados biográficos, estatísticas da temporada atual, histórico de métricas avançadas e valor de mercado. Todos os dados devem ser armazenados no PostgreSQL interno e servidos à LLM sem chamadas externas em tempo de geração de relatório.

---

## Anatomia do Perfil de Jogador

Cada jogador no FutMetricX tem quatro camadas de dados:

**Camada 1 — Identidade:** quem é o jogador (foto, nome, nacionalidade, posição, idade, time atual).

**Camada 2 — Performance atual:** estatísticas da temporada em curso (gols, assistências, minutos jogados, avaliação, métricas avançadas xG/xA).

**Camada 3 — Histórico:** séries temporais de performance por temporada desde 2014/15 (onde disponível).

**Camada 4 — Contexto:** valor de mercado, bio narrativa, status de lesão/suspensão, forma recente (últimos 5 jogos).

---

## Fontes por Camada de Dado

### Camada 1 — Identidade

| Campo | Fonte Primária | Fallback |
|---|---|---|
| Foto (busto/perfil) | API-Football | TheSportsDB |
| Nome completo | API-Football | TheSportsDB |
| Nome curto / apelido | TheSportsDB | Manual |
| Nacionalidade + flag | API-Football | TheSportsDB |
| Data de nascimento | API-Football | TheSportsDB |
| Altura e peso | API-Football | TheSportsDB |
| Posição principal | API-Football | TheSportsDB |
| Posições secundárias | TheSportsDB | Manual |
| Pé dominante | TheSportsDB | — |
| Time atual + escudo | API-Football | football-data.org |
| Número da camisa | API-Football | — |
| Bio narrativa | TheSportsDB (crowd-sourced) | Gerada pela LLM |

**Sobre as fotos:**
API-Football retorna URL de foto de perfil por jogador no endpoint de estatísticas. TheSportsDB retorna `strThumb`, `strCutout` e `strRender` — três tipos de imagem por jogador. Usar `strCutout` (fundo removido) como preferencial para exibição em cards e `strThumb` como fallback.

Armazenar a URL da imagem no PostgreSQL e servir via proxy interno. Nunca apontar diretamente para a URL da API no frontend — se a API mudar a URL, o produto quebra.

---

### Camada 2 — Performance Atual (temporada em curso)

| Campo | Fonte | Endpoint |
|---|---|---|
| Gols | API-Football | `/players?season=YYYY&league=ID` |
| Assistências | API-Football | idem |
| Finalizações totais / no alvo | API-Football | idem |
| Passes totais / precisão | API-Football | idem |
| Dribles tentados / completados | API-Football | idem |
| Duelos ganhos / aéreos | API-Football | idem |
| Cartões amarelos / vermelhos | API-Football | idem |
| Minutos jogados | API-Football | idem |
| Jogos como titular / reserva | API-Football | idem |
| Avaliação geral (0-10) | API-Football | idem |
| xG temporada | Understat | `/player/{id}` |
| xA temporada | Understat | idem |
| npxG (xG sem pênaltis) | Understat | idem |
| xG por 90 minutos | Calculado internamente | — |
| xA por 90 minutos | Calculado internamente | — |
| Progressive carries | FBref (scraping semanal) | — |
| Progressive passes | FBref (scraping semanal) | — |
| Pressões aplicadas | FBref (scraping semanal) | — |
| Defensive actions | FBref (scraping semanal) | — |

**Campos calculados internamente (não vêm de API):**
- xG por 90: `(xg_total / minutes_played) * 90`
- xA por 90: `(xa_total / minutes_played) * 90`
- Percentil vs média da liga para cada métrica (calculado sobre todos os jogadores da liga na mesma posição)
- Forma recente: média dos últimos 5 jogos para cada métrica

---

### Camada 3 — Histórico por Temporada

| Campo | Fonte | Cobertura Histórica |
|---|---|---|
| Gols / Assistências por temporada | API-Football | Variável por liga |
| xG / xA / npxG por temporada | Understat | 2014/15 → atual |
| Times anteriores + período | TheSportsDB | Variável |
| Valor de mercado histórico | Transfermarkt (scraping) | 2010 → atual |

O histórico de xG do Understat é o ativo mais valioso aqui — cobre 10+ temporadas das 5 grandes ligas europeias e permite análise de evolução de performance que nenhuma API gratuita entrega.

---

### Camada 4 — Contexto

| Campo | Fonte | Frequência de Atualização |
|---|---|---|
| Valor de mercado atual | Transfermarkt (scraping) | Semanal |
| Status (ativo / lesionado / suspenso) | API-Football | Diária |
| Próximos jogos do time | football-data.org | Diária |
| Notícias recentes sobre o jogador | RSS feeds (ESPN, GE, BBC Sport) | Contínua |
| Análise narrativa de forma | Gerada pela LLM | Após cada jogo |

---

## Fontes de Assets Visuais

### Fotos de Jogadores

**API-Football:**
Retorna URL de foto no campo `photo` do endpoint de jogador. Resolução média, suficiente para cards. Não exige crédito. 100% dos jogadores das ligas principais têm foto disponível.

```
GET https://v3.football.api-sports.io/players?id={player_id}&season={year}
Header: X-RapidAPI-Key: {key}

Retorna: player.photo → "https://media.api-sports.io/football/players/{id}.png"
```

**TheSportsDB:**
Três tipos de imagem por jogador:
- `strThumb` → foto retangular com fundo (melhor para perfil completo)
- `strCutout` → jogador recortado sem fundo (melhor para cards e sobreposição no campo)
- `strRender` → renderização em alta qualidade (quando disponível)

```
GET https://www.thesportsdb.com/api/v1/json/{key}/searchplayers.php?p={nome}

Retorna: strThumb, strCutout, strRender
```

**Estratégia de armazenamento de imagens:**
1. No momento do seed inicial e a cada atualização semanal, buscar as URLs das fotos das APIs
2. Baixar as imagens e armazenar em bucket S3/R2 (Cloudflare R2 tem free tier generoso — 10GB grátis)
3. Servir todas as imagens via CDN próprio — nunca apontar para URL da API no frontend
4. Se a imagem não existir em nenhuma fonte: usar fallback SVG com iniciais do jogador + cor do time

```
Hierarquia de fallback para foto:
API-Football photo → TheSportsDB strCutout → TheSportsDB strThumb → SVG gerado com iniciais
```

---

### Escudos de Times

**Download inicial (SVG vetorial):**

- **FootyLogos** (footylogos.com) → Premier League, Champions League, La Liga, Bundesliga, Serie A, Ligue 1, Brasileirão — todos em SVG limpo com fundo transparente. Download manual por liga.
- **BrandLogos.net** → Packs completos por temporada em SVG+EPS. Baixar o pack 2025-26 de cada liga relevante.

**Fallback via API (para times não cobertos nos packs manuais):**

TheSportsDB retorna `strBadge` e `strBadgeAlternate` em PNG para qualquer time buscado. Usar como fallback automático quando o SVG local não existir.

```
GET https://www.thesportsdb.com/api/v1/json/{key}/searchteams.php?t={team_name}

Retorna: strBadge → URL do escudo em PNG
```

**Armazenamento:**
Todos os escudos ficam em `/public/crests/{team_slug}.svg` no projeto. SVGs locais têm prioridade absoluta. O worker de ingestão verifica semanalmente se há novos times no banco sem escudo local e faz fallback automático para TheSportsDB.

---

## Schema do Banco de Dados — Tabelas de Jogadores

```sql
-- Perfil base do jogador
CREATE TABLE players (
  id                    SERIAL PRIMARY KEY,
  external_id_apifootball INT,
  external_id_sportsdb    VARCHAR(50),
  external_id_understat   INT,
  external_id_transfermarkt VARCHAR(50),
  external_id_fbref       VARCHAR(100),

  -- Identidade
  name_full             VARCHAR(200) NOT NULL,
  name_short            VARCHAR(100),       -- apelido / nome conhecido
  nationality           VARCHAR(100),
  nationality_iso2      CHAR(2),            -- para emoji de bandeira
  date_of_birth         DATE,
  age                   INT GENERATED ALWAYS AS (
                          EXTRACT(YEAR FROM AGE(date_of_birth))
                        ) STORED,
  height_cm             INT,
  weight_kg             INT,
  position_primary      VARCHAR(50),        -- GK, DEF, MID, ATT
  position_secondary    VARCHAR(50)[],      -- array de posições secundárias
  foot_dominant         VARCHAR(10),        -- left, right, both

  -- Time atual
  team_id               INT REFERENCES teams(id),
  shirt_number          INT,
  contract_until        DATE,

  -- Assets visuais
  photo_url_local       VARCHAR(500),       -- URL no CDN próprio (preferencial)
  photo_url_apifootball VARCHAR(500),
  photo_url_sportsdb_thumb   VARCHAR(500),
  photo_url_sportsdb_cutout  VARCHAR(500),

  -- Bio
  bio_text              TEXT,               -- crowd-sourced do TheSportsDB
  bio_llm               TEXT,               -- gerada pela LLM, atualizada mensalmente

  -- Controle
  source_primary        VARCHAR(50) DEFAULT 'api-football',
  is_active             BOOLEAN DEFAULT true,
  created_at            TIMESTAMPTZ DEFAULT NOW(),
  updated_at            TIMESTAMPTZ DEFAULT NOW()
);

-- Estatísticas por temporada (uma linha por jogador/temporada/competição)
CREATE TABLE player_season_stats (
  id                    SERIAL PRIMARY KEY,
  player_id             INT REFERENCES players(id) ON DELETE CASCADE,
  team_id               INT REFERENCES teams(id),
  competition_id        INT REFERENCES competitions(id),
  season                VARCHAR(10) NOT NULL,     -- ex: "2024-25"

  -- Volume
  appearances           INT DEFAULT 0,
  starts                INT DEFAULT 0,
  minutes_played        INT DEFAULT 0,

  -- Ataque
  goals                 INT DEFAULT 0,
  assists               INT DEFAULT 0,
  shots_total           INT DEFAULT 0,
  shots_on_target       INT DEFAULT 0,
  shot_accuracy_pct     NUMERIC(5,2),

  -- Passe
  passes_total          INT DEFAULT 0,
  pass_accuracy_pct     NUMERIC(5,2),
  key_passes            INT DEFAULT 0,

  -- Drible e duelo
  dribbles_attempted    INT DEFAULT 0,
  dribbles_success      INT DEFAULT 0,
  duels_total           INT DEFAULT 0,
  duels_won             INT DEFAULT 0,
  aerial_duels_won      INT DEFAULT 0,

  -- Disciplina
  yellow_cards          INT DEFAULT 0,
  red_cards             INT DEFAULT 0,
  fouls_committed       INT DEFAULT 0,
  fouls_drawn           INT DEFAULT 0,

  -- Métricas avançadas (Understat)
  xg                    NUMERIC(6,3),
  xa                    NUMERIC(6,3),
  npxg                  NUMERIC(6,3),       -- xG sem pênaltis
  xg_chain              NUMERIC(6,3),
  xg_buildup            NUMERIC(6,3),

  -- Métricas por 90 (calculadas)
  xg_per90              NUMERIC(5,3),
  xa_per90              NUMERIC(5,3),
  goals_per90           NUMERIC(5,3),
  assists_per90         NUMERIC(5,3),

  -- Métricas FBref
  progressive_carries   INT,
  progressive_passes    INT,
  pressures             INT,
  defensive_actions     INT,

  -- Avaliação
  rating_avg            NUMERIC(4,2),       -- média da avaliação API-Football (0-10)

  -- Controle
  source_base           VARCHAR(50) DEFAULT 'api-football',
  source_advanced       VARCHAR(50) DEFAULT 'understat',
  updated_at            TIMESTAMPTZ DEFAULT NOW(),

  UNIQUE (player_id, competition_id, season)
);

-- Forma recente — últimos N jogos do jogador
CREATE TABLE player_match_stats (
  id                    SERIAL PRIMARY KEY,
  player_id             INT REFERENCES players(id) ON DELETE CASCADE,
  fixture_id            INT REFERENCES fixtures(id) ON DELETE CASCADE,
  team_id               INT REFERENCES teams(id),

  -- Participação
  minutes_played        INT DEFAULT 0,
  position_played       VARCHAR(20),
  rating                NUMERIC(4,2),
  is_captain            BOOLEAN DEFAULT false,

  -- Performance na partida
  goals                 INT DEFAULT 0,
  assists               INT DEFAULT 0,
  shots_total           INT DEFAULT 0,
  shots_on_target       INT DEFAULT 0,
  passes_total          INT DEFAULT 0,
  pass_accuracy_pct     NUMERIC(5,2),
  dribbles_success      INT DEFAULT 0,
  duels_won             INT DEFAULT 0,
  yellow_cards          INT DEFAULT 0,
  red_cards             INT DEFAULT 0,

  -- Avançados (disponíveis após fim da partida via Understat)
  xg                    NUMERIC(5,3),
  xa                    NUMERIC(5,3),
  npxg                  NUMERIC(5,3),

  updated_at            TIMESTAMPTZ DEFAULT NOW(),

  UNIQUE (player_id, fixture_id)
);

-- Histórico de valor de mercado (Transfermarkt)
CREATE TABLE player_market_value (
  id                    SERIAL PRIMARY KEY,
  player_id             INT REFERENCES players(id) ON DELETE CASCADE,
  value_eur             BIGINT,             -- valor em euros
  value_date            DATE NOT NULL,      -- data da avaliação
  team_id               INT REFERENCES teams(id),
  source                VARCHAR(50) DEFAULT 'transfermarkt',
  created_at            TIMESTAMPTZ DEFAULT NOW(),

  UNIQUE (player_id, value_date)
);

-- Percentis por posição e liga (recalculado a cada rodada)
CREATE TABLE player_percentiles (
  id                    SERIAL PRIMARY KEY,
  player_id             INT REFERENCES players(id) ON DELETE CASCADE,
  competition_id        INT REFERENCES competitions(id),
  season                VARCHAR(10),
  position_group        VARCHAR(20),        -- GK, DEF, MID, ATT

  -- Percentil de cada métrica vs jogadores da mesma posição e liga
  pct_goals             SMALLINT,           -- 0-100
  pct_assists           SMALLINT,
  pct_xg                SMALLINT,
  pct_xa                SMALLINT,
  pct_xg_per90          SMALLINT,
  pct_progressive_passes SMALLINT,
  pct_progressive_carries SMALLINT,
  pct_pressures         SMALLINT,
  pct_pass_accuracy     SMALLINT,
  pct_aerial_duels_won  SMALLINT,
  pct_dribbles_success  SMALLINT,

  updated_at            TIMESTAMPTZ DEFAULT NOW(),

  UNIQUE (player_id, competition_id, season)
);

-- Índices para performance
CREATE INDEX idx_player_season_stats_player ON player_season_stats(player_id);
CREATE INDEX idx_player_season_stats_season ON player_season_stats(season);
CREATE INDEX idx_player_match_stats_player ON player_match_stats(player_id);
CREATE INDEX idx_player_match_stats_fixture ON player_match_stats(fixture_id);
CREATE INDEX idx_player_market_value_player ON player_market_value(player_id);
CREATE INDEX idx_players_team ON players(team_id);
CREATE INDEX idx_players_nationality ON players(nationality_iso2);
```

---

## Workers de Ingestão de Dados de Jogadores

### Worker 1 — Seed Inicial de Jogadores
**Trigger:** uma única vez ao inicializar o sistema, depois sob demanda para novas ligas.
**Fonte:** API-Football
**O que faz:**
1. Para cada competição no banco, busca todos os times da temporada atual
2. Para cada time, busca o elenco completo (`/players/squads?team={id}`)
3. Para cada jogador, cria registro em `players` com dados de identidade
4. Busca foto via API-Football e tenta enriquecer com TheSportsDB
5. Faz download das imagens e faz upload para o CDN próprio
6. Busca bio no TheSportsDB via nome do jogador

**Rate limit:** respeitar 100 req/dia do API-Football. O seed inicial de toda a Premier League (~500 jogadores) pode requerer 2-3 dias de seed incremental. Priorizar titulares e jogadores mais relevantes primeiro.

```python
# Pseudocódigo do seed worker
def seed_players_for_competition(competition_id, season):
    teams = get_teams_from_db(competition_id)
    for team in teams:
        squad = api_football.get_squad(team.external_id, season)
        for player_data in squad:
            player = upsert_player(player_data)
            photo_url = download_and_store_photo(player_data['photo'])
            bio = thesportsdb.search_player(player_data['name'])
            update_player_assets(player.id, photo_url, bio)
            sleep(0.5)  # respeitar rate limits
```

---

### Worker 2 — Estatísticas da Temporada Atual
**Trigger:** após cada rodada de jogos finalizada
**Fonte:** API-Football (stats básicas) + Understat (xG/xA)
**O que faz:**
1. Identifica jogadores que participaram da rodada
2. Busca estatísticas atualizadas da temporada no API-Football
3. Busca xG/xA/npxG no Understat para os mesmos jogadores
4. Upsert em `player_season_stats`
5. Recalcula percentis em `player_percentiles` para a liga afetada

---

### Worker 3 — Estatísticas por Partida
**Trigger:** 30 minutos após fim de cada partida
**Fonte:** API-Football
**O que faz:**
1. Busca box score da partida (`/fixtures/players?fixture={id}`)
2. Insere/atualiza `player_match_stats` para cada jogador da partida
3. Aguarda Understat (geralmente 2-4 horas) e complementa com xG/xA por jogo

---

### Worker 4 — Valor de Mercado (Transfermarkt)
**Trigger:** semanal (toda segunda-feira)
**Fonte:** Transfermarkt via scraping
**Biblioteca:** `transfermarkt-scraper` (PyPI) ou scraper customizado

```python
import requests
from bs4 import BeautifulSoup

def get_market_value(transfermarkt_id: str) -> dict:
    url = f"https://www.transfermarkt.com/player/profil/spieler/{transfermarkt_id}"
    headers = {"User-Agent": "Mozilla/5.0 ..."}
    soup = BeautifulSoup(requests.get(url, headers=headers).content)
    value_element = soup.find("a", class_="data-header__market-value-wrapper")
    # extrair e normalizar valor (€45M → 45000000)
    return {"value_eur": parsed_value, "value_date": today}
```

**Mapeamento de IDs:** Transfermarkt usa IDs numéricos próprios. Manter tabela de mapeamento `player_id → transfermarkt_id`, construída inicialmente via busca por nome + validação manual para os top 200 jogadores mais relevantes do banco.

---

### Worker 5 — Métricas FBref
**Trigger:** semanal (job noturno de domingo)
**Fonte:** FBref via biblioteca `soccerdata` (Python)
**O que faz:**
1. Baixa tabela de estatísticas avançadas da temporada para cada liga coberta
2. Cruza com jogadores do banco via nome normalizado
3. Atualiza `progressive_carries`, `progressive_passes`, `pressures`, `defensive_actions` em `player_season_stats`

```python
import soccerdata as sd

def update_fbref_stats(league: str, season: str):
    fbref = sd.FBref(leagues=league, seasons=season)
    stats = fbref.read_player_season_stats(stat_type="standard")
    # normalizar nomes e fazer match com player_id no banco
    # respeitar rate limit — usar sleep entre requests
```

---

### Worker 6 — Assets Visuais (fotos e escudos)
**Trigger:** semanal + sob demanda para novos jogadores
**O que faz:**
1. Verifica jogadores em `players` sem `photo_url_local`
2. Tenta download via URL do API-Football
3. Fallback para TheSportsDB (`strCutout` → `strThumb`)
4. Upload para CDN (Cloudflare R2 ou AWS S3)
5. Atualiza `photo_url_local` no banco
6. Verifica times sem escudo SVG local e faz fallback para TheSportsDB badge

---

### Worker 7 — Bio Narrativa (LLM)
**Trigger:** mensal + após transferências ou marcos importantes
**O que faz:**
Para jogadores sem bio ou com bio desatualizada:
1. Agrega: dados de identidade + estatísticas da temporada + histórico + valor de mercado + últimas notícias
2. Chama LLM com prompt especializado
3. Gera bio narrativa de 3-4 parágrafos no estilo editorial do FutMetricX
4. Armazena em `players.bio_llm`

```
Prompt base:
"Você é um analista esportivo do FutMetricX. Com base nos dados a seguir,
escreva uma bio analítica de {jogador} em 3 parágrafos:
- Parágrafo 1: quem é o jogador, perfil de jogo, características principais
- Parágrafo 2: temporada atual em números e contexto
- Parágrafo 3: trajetória e momento de carreira

Tom: analítico mas acessível. Sem clichês. Dados: {json_completo}"
```

---

## Mapeamento de IDs Entre Fontes

O maior desafio técnico de usar múltiplas fontes é o mapeamento de IDs — cada API tem seu próprio identificador para o mesmo jogador.

```sql
-- Tabela de mapeamento de IDs externos
CREATE TABLE player_id_mapping (
  player_id             INT REFERENCES players(id) ON DELETE CASCADE,
  source                VARCHAR(50) NOT NULL,   -- api-football, understat, sportsdb, transfermarkt, fbref
  external_id           VARCHAR(100) NOT NULL,
  confidence            VARCHAR(20) DEFAULT 'auto',  -- auto | manual | verified
  created_at            TIMESTAMPTZ DEFAULT NOW(),

  UNIQUE (source, external_id)
);
```

**Estratégia de match automático:**
1. Match por nome completo normalizado (remover acentos, lowercase, trim)
2. Validação por time atual + data de nascimento quando disponível
3. Confidence `auto` → revisão humana opcional para top jogadores
4. Todos os mapeamentos de jogadores com >10.000 minutos jogados devem ser verificados manualmente antes do lançamento

---

## Normalização de Nomes

Jogadores com nomes em diferentes alfabetos ou grafias entre fontes são o principal problema de mapeamento. Implementar função de normalização:

```python
import unicodedata
import re

def normalize_player_name(name: str) -> str:
    # Remover acentos
    nfkd = unicodedata.normalize('NFKD', name)
    ascii_name = nfkd.encode('ASCII', 'ignore').decode('ASCII')
    # Lowercase e remover pontuação
    clean = re.sub(r'[^a-z0-9 ]', '', ascii_name.lower())
    # Remover artigos comuns
    for article in ['de ', 'da ', 'van ', 'van den ', 'von ', 'el ']:
        clean = clean.replace(article, '')
    return clean.strip()

# Exemplos:
# "Vinicius Júnior" → "vinicius junior"
# "Van Dijk" → "dijk"  ← cuidado, validar com time
# "Rodrygo Goes" → "rodrygo goes"
```

---

## Priorização de Jogadores para o MVP

Não é viável fazer seed de todos os jogadores de todas as ligas de uma vez com 100 req/dia. Priorizar em ondas:

**Onda 1 (semana 1) — Top 200 jogadores mais relevantes**
Critérios: titulares dos top 8 times da Premier League + titulares dos grupos da Champions League + todos os brasileiros no exterior com >1.000 minutos na temporada.

**Onda 2 (semana 2-3) — Elencos completos Premier League**
Todos os 20 times da Premier League, titulares e reservas.

**Onda 3 (semana 3-4) — Grupos Champions League**
Todos os times ainda na competição.

**Onda 4 (contínua) — Brasileirão e demais ligas**
Incrementalmente conforme os workers rodam.

---

## Cobertura de Brasileiros no Exterior

Lista de prioridade máxima — esses jogadores devem estar na Onda 1 com perfil completo:

| Jogador | Time | Liga |
|---|---|---|
| Vinicius Jr | Real Madrid | La Liga |
| Rodrygo | Real Madrid | La Liga |
| Endrick | Real Madrid | La Liga |
| Raphinha | Barcelona | La Liga |
| Gabriel Magalhães | Arsenal | Premier League |
| Gabriel Martinelli | Arsenal | Premier League |
| Gabriel Jesus | Arsenal | Premier League |
| Richarlison | Tottenham | Premier League |
| Ederson | Manchester City | Premier League |
| Alisson | Liverpool | Premier League |
| Lucas Paquetá | West Ham | Premier League |
| Bruno Guimarães | Newcastle | Premier League |
| Danilo | Juventus | Serie A |
| Bremer | Juventus | Serie A |

Para esses jogadores: bio LLM completa, histórico de xG desde 2014 (onde aplicável), valor de mercado atualizado, foto em alta resolução verificada manualmente.

---

## Custo Total desta Stack

| Fonte | Custo |
|---|---|
| API-Football (fotos + stats) | $0 (100 req/dia free) |
| TheSportsDB (bio + imagens) | $0 (free) / $9/mês (sem watermark) |
| Understat (xG histórico) | $0 |
| FBref via soccerdata | $0 |
| Transfermarkt (scraping) | $0 |
| FootyLogos / BrandLogos (escudos SVG) | $0 (download manual) |
| Cloudflare R2 (storage de imagens) | $0 até 10GB |
| **Total MVP** | **$0** |

Primeiro upgrade recomendado quando houver receita: TheSportsDB Patreon $9/mês — desbloqueia fotos sem watermark em alta resolução e uso comercial explícito das imagens.

---

## Checklist de Implementação para o Claude Code

- [ ] Criar migrations PostgreSQL com todas as tabelas acima
- [ ] Implementar `normalize_player_name()` como função utilitária
- [ ] Implementar `player_id_mapping` com confidence scoring
- [ ] Worker 1: seed de elencos via API-Football
- [ ] Worker 2: stats da temporada (API-Football + Understat)
- [ ] Worker 3: stats por partida com xG pós-jogo
- [ ] Worker 4: valor de mercado via Transfermarkt scraping
- [ ] Worker 5: métricas FBref via soccerdata
- [ ] Worker 6: download e CDN de fotos e escudos
- [ ] Worker 7: geração de bio LLM
- [ ] Calcular e manter `player_percentiles` após cada rodada
- [ ] Calcular campos `_per90` automaticamente via trigger ou worker
- [ ] Implementar fallback SVG com iniciais para jogadores sem foto
- [ ] Validar manualmente mapeamento dos top 200 jogadores prioritários
- [ ] Seed completo da lista de brasileiros no exterior (Onda 1)

---

*FutMetricX — Futebol com inteligência.*
