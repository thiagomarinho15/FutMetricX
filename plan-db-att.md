# Plano de Atualização de Dados — Temporada 2025/2026

**Objetivo:** substituir dados desatualizados (StatsBomb histórico + elencos 2024) por dados
atuais da temporada 2025/2026, usando API-Football como fonte primária de elencos,
football-data.org para fixtures/standings, TheSportsDB para assets visuais e Understat para xG.

---

## Diagnóstico do estado atual

| Problema | Origem |
|---|---|
| Relatórios usam `Partida`/`Jogador` — dados StatsBomb de temporadas 2003–2020 | `seed.py` importa StatsBomb Open Data |
| `player_seed_worker.py` usa `CURRENT_SEASON = 2024` | hardcoded, nunca atualizado |
| Times duplicados: tabela `teams` tem entradas separadas para `source_name='football-data'` e `source_name='api-football'` | sem deduplicação cross-source |
| Sem cliente Understat | nenhum arquivo em `app/clients/` |
| Temporada europeia referenciada como `"2025"` em vez de `"2025-26"` | fixtures_worker e Competition model usam apenas o ano de início |

---

## Fontes de dados e responsabilidades

| Fonte | Responsabilidade | Endpoint / método |
|---|---|---|
| **API-Football** | Elencos, identidade do jogador (DOB, altura, pé, camisa), foto, stats por partida | `/players/squads`, `/players`, `/fixtures/players` |
| **football-data.org** | Fixtures, resultados, standings | `/competitions/{id}/matches`, `/competitions/{id}/standings` |
| **TheSportsDB** | Logo de times, foto cutout e bio de jogadores | `/searchplayers.php`, `/searchteams.php` |
| **Understat** | xG, xA, npxG, xG_chain por temporada (europeus) | scrape HTML + JSON embutido |

---

## Etapas

### Etapa 1 — Corrigir formato da temporada em todo o projeto

**Arquivo:** `app/workers/fixtures_worker.py`, `app/workers/player_seed_worker.py`

- Trocar `CURRENT_SEASON = 2024` → `CURRENT_SEASON = 2025` no `player_seed_worker.py`
- Adotar a string `"2025-26"` como valor canônico de `Competition.season` para a temporada europeia
- Adotar `"2025"` para o Brasileirão (temporada civil)
- Criar constante `SEASON_LABEL` (ex. `"2025-26"`) separada de `SEASON_YEAR` (`2025`) para não misturar os dois usos

### Etapa 2 — Worker de atualização de elencos (API-Football)

**Arquivo novo:** `app/workers/squad_refresh_worker.py`

Fluxo:
```
para cada Competition com season "2025" ou "2025-26":
    GET /teams?league={league_id}&season=2025  → lista de teams com source_id api-football
    upsert Team (logo_url via API-Football, dedup por source_id+source_name)
    GET /players/squads?team={team_id}&season=2025
    para cada jogador no squad:
        upsert Player (source_id, name, age, position, photo, shirt_number)
        se o jogador mudou de time → atualizar player.team_id
```

Critério de deduplicação de Player: `source_id + source_name='api-football'`  
Critério de deduplicação de Team: `source_id + source_name='api-football'`

**Atenção ao rate limit:** API-Football free tier = 100 req/dia → worker deve processar uma
liga por execução e registrar progresso em tabela `worker_log` ou arquivo de estado.

### Etapa 3 — Deduplicação de times cross-source

**Arquivo novo:** `app/workers/team_dedup_worker.py`

Problema: o mesmo Arsenal tem `source_name='football-data'` e `source_name='api-football'`
como entradas distintas, quebrando JOINs entre fixtures e stats de jogadores.

Solução:
- Adicionar coluna `canonical_team_id` em `teams` (FK para o próprio `teams.id`)
- Fazer matching por nome normalizado (`tsvector` ou `difflib`) + país
- Worker seta `canonical_team_id` apontando sempre para a entrada `api-football` (fonte primária)
- Todas as queries que buscam time de um jogador passam a usar `canonical_team_id`

**Migration necessária:** adicionar `teams.canonical_team_id` e `teams.logo_url`.

### Etapa 4 — Cliente e worker Understat

**Arquivo novo:** `app/clients/understat.py`

Understat não tem API oficial — usa scrape do HTML com JSON embutido no `<script>`.

```python
# endpoints relevantes
GET https://understat.com/league/{league_slug}/{year}
# retorna JSON com playersData embutido → xG, xA, npxG, xG_chain, xG_buildup por jogador

leagues = {
    'EPL': 'epl',        # Premier League
    'La liga': 'la_liga',
    'Bundesliga': 'bundesliga',
    'Serie A': 'serie_a',
    'Ligue 1': 'ligue_1',
}
# Brasileirão não está no Understat
```

**Arquivo novo:** `app/workers/understat_worker.py`

- Para cada liga europeia trackeada, baixa temporada 2025
- Faz match de nome com Player existente via `difflib.SequenceMatcher` (threshold > 0.85)
- Upsert em `PlayerSeasonStats`: campos `xg`, `xa`, `npxg`, `xg_chain`, `xg_buildup`, `source_advanced='understat'`

### Etapa 5 — Enriquecimento de assets visuais (TheSportsDB)

**Já existe:** `app/clients/thesportsdb.py` (usado em `player_seed_worker.py`)

Adicionar ao `squad_refresh_worker.py`:
- Após upsert de cada time, chamar `thesportsdb.search_team(team_name)` → salvar `logo_url` e `banner_url` em `Team`
- Para jogadores sem `photo_url_apifootball`, tentar `thesportsdb.search_player(name)` → cutout

**Migration necessária:** adicionar `teams.logo_url`, `teams.banner_url`.

### Etapa 6 — Fixtures 2025/2026 atualizados

**Arquivo existente:** `app/workers/fixtures_worker.py`

Mudanças:
- `CURRENT_SEASON = 2025` (já correto)
- Mudar `Competition.season` de `"2025"` para `"2025-26"` nas ligas europeias, manter `"2025"` para Brasileirão
- Adicionar standings: após importar fixtures, chamar `football_data.get_standings(comp_id)` e popular `TeamForm`

### Etapa 7 — Deprecar dados StatsBomb do relatório

**Arquivos:** `app/services/data_fetcher.py`, templates de relatório

- Os modelos `Partida` e `Jogador` ficam no banco (histórico), mas o gerador de relatório
  deve priorizar `Fixture` + `Player` + `PlayerSeasonStats` como fonte principal
- Atualizar o contexto enviado ao LLM para usar apenas dados de `"2025-26"` / `"2025"`
- Adicionar filtro `season='2025-26'` em todas as queries do gerador

### Etapa 8 — Trigger manual no painel admin

**Arquivo existente:** `app/adm.py` ou rota admin nova

Adicionar endpoints admin (acessível apenas com role `admin`):
```
POST /admin/workers/squad-refresh?league=Premier+League
POST /admin/workers/understat-refresh?league=EPL
POST /admin/workers/fixtures-refresh
```

Cada endpoint roda o worker via `threading.Thread` (ou Celery se disponível) e retorna um
job_id para polling de status.

### Etapa 9 — Migration Alembic

Criar uma migration com:
```sql
ALTER TABLE teams ADD COLUMN logo_url VARCHAR(500);
ALTER TABLE teams ADD COLUMN banner_url VARCHAR(500);
ALTER TABLE teams ADD COLUMN canonical_team_id INTEGER REFERENCES teams(id);

-- worker_log para rastrear execuções
CREATE TABLE worker_log (
    id SERIAL PRIMARY KEY,
    worker_name VARCHAR(100) NOT NULL,
    status VARCHAR(20) DEFAULT 'running',  -- running | done | error
    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    rows_affected INTEGER,
    error_msg TEXT
);
```

---

## Ordem de execução (primeira rodada)

```
1. flask db upgrade          (Etapa 9 — migration)
2. squad_refresh_worker      (Etapa 2 — times + elencos 2025/2026)
3. team_dedup_worker         (Etapa 3 — resolver duplicatas cross-source)
4. fixtures_worker           (Etapa 6 — fixtures 2025/2026)
5. understat_worker          (Etapa 4 — xG europeus)
6. player_seed_worker        (enriquecimento complementar de identidade)
```

Após a primeira rodada, os workers 2, 4 e 5 devem rodar semanalmente via cron ou scheduler.

---

## Critérios de sucesso

- [ ] Nenhum relatório pré-jogo cita jogador em time errado
- [ ] `Player.team_id` reflete elenco atual para 100% dos times rastreados
- [ ] `PlayerSeasonStats` tem dados de 2025-26 para pelo menos 80% dos jogadores com `appearances > 0`
- [ ] `xg` preenchido para jogadores das 5 ligas europeias via Understat
- [ ] Fixtures 2025-26 presentes para todas as competições rastreadas
- [ ] Admin consegue triggerar qualquer worker sem SSH

---

## Riscos e mitigações

| Risco | Mitigação |
|---|---|
| API-Football 100 req/dia (free) esgota rápido | Processar 1 liga por dia; usar 2 chaves via `API_FOOTBALL_KEY_1`/`_2` já suportado |
| Understat bloqueia scraping | Adicionar `User-Agent` de browser + delay de 2s entre requests; fallback: dados de temporada anterior |
| Nome de jogador não dá match cross-source | Threshold 0.85 + fallback por data de nascimento quando disponível |
| Times duplicados causam FK inconsistente | `canonical_team_id` resolve no nível de query sem precisar deletar dados |
