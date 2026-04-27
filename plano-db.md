# FutMetricX — Plano de Banco de Dados e Fontes de Dados

## Princípio Central: Single Source of Truth (SSoT)

Usar múltiplas APIs simultaneamente é a estratégia correta para maximizar cobertura e resiliência. Porém, dados contraditórios entre fontes são um risco real — um jogador pode ter xG 1.4 em uma fonte e 1.7 em outra, ou um fixture pode ter horário divergente. A solução é um modelo de **hierarquia de fontes** com uma fonte declarada como detentora da verdade para cada tipo de dado.

O banco de dados interno do FutMetricX **nunca armazena dados brutos de múltiplas fontes para o mesmo campo**. Ele armazena o dado já resolvido pela hierarquia, com metadado de origem para auditoria.

---

## Hierarquia de Fontes (Truth Hierarchy)

Cada categoria de dado tem uma fonte primária (P), uma fonte de fallback (F) e uma fonte de validação cruzada (V).

| Categoria de Dado | Primária (P) | Fallback (F) | Validação (V) |
|---|---|---|---|
| Fixtures futuros e schedules | football-data.org | API-Football | Sportmonks |
| Resultados e placares ao vivo | API-Football | football-data.org | The-Odds-API |
| Estatísticas básicas (gols, assists, cartões) | API-Football | football-data.org | Understat |
| Métricas avançadas (xG, xA, npxG) | Understat | Sportmonks (free tier) | FBref (scraping) |
| Elencos e perfis de jogadores | API-Football | football-data.org | — |
| Odds e contexto de mercado | The-Odds-API | — | — |
| Dados históricos (5+ temporadas) | Understat | FBref (scraping) | openfootball |
| Ligas menores / testes de arquitetura | Sportmonks (free tier) | — | — |

**Regra de ouro:** quando a fonte primária retorna dado, ele é aceito sem consultar o fallback. O fallback só é acionado em caso de timeout, erro HTTP ou campo nulo. A validação cruzada roda em job assíncrono separado, apenas para detectar divergências acima de threshold configurável (ex: diferença de xG > 0.3 aciona alerta de inconsistência no log).

---

## Mapeamento Completo das Fontes

### 1. football-data.org
**Papel:** Primária para fixtures e schedules. Espinha dorsal estrutural do produto.

- **Plano:** Free forever
- **Cobertura relevante:** Premier League, Champions League, Brasileirão Série A, La Liga, Bundesliga, Serie A, Ligue 1
- **Dados disponíveis no free:** Fixtures futuros, resultados, tabela classificatória, schedules da temporada
- **Limitações:** Scores com delay, sem lineups/artilheiros/cartões no free, 10 req/min
- **Estratégia de uso:** Worker consulta a cada 6 segundos durante partidas. Dado cacheado no PostgreSQL. Atualizações distribuídas via WebSocket para o frontend. Latência média: ~6 segundos, custo: zero.
- **Crédito obrigatório:** Não — apenas proibido redistribuir dados brutos
- **URL:** https://www.football-data.org

---

### 2. API-Football (via RapidAPI)
**Papel:** Primária para estatísticas de jogadores, lineups e resultados ao vivo.

- **Plano:** Free — 100 requests/dia
- **Cobertura relevante:** +1.200 ligas, Premier League, Champions League, Brasileirão
- **Dados disponíveis:** Livescore, fixtures, lineups, eventos de jogo, estatísticas de jogadores, elencos, standings, odds, atualização a cada 15 segundos
- **Limitações:** 100 calls/dia é restritivo para produção — exige cache agressivo
- **Estratégia de uso:** Cache mandatory. Todo dado buscado é armazenado localmente com TTL configurável por tipo (fixture: 24h, player stats: 6h, livescore: 30s durante jogo). No MVP, 100 calls/dia é suficiente com cache bem implementado.
- **Crédito obrigatório:** Não
- **URL:** https://www.api-football.com

---

### 3. Sportmonks
**Papel:** Laboratório de arquitetura e fallback para métricas avançadas. Primária para ligas menores durante desenvolvimento.

- **Plano:** Free forever — 3.000 req/hora, ligas menores (ex: Superliga Dinamarquesa, Scottish Premiership)
- **Grande trunfo:** O plano free libera acesso à arquitetura Enterprise completa — **Webhooks em tempo real**, eventos push, estrutura orientada a eventos. Permite desenvolver e validar toda a arquitetura de tempo real sem custo, usando ligas menores como proxy.
- **Dados disponíveis:** xG por time e jogador (add-on), player stats, fixtures, lineups, standings, webhooks
- **Estratégia de uso:** Desenvolver e testar toda a pipeline de ingestão em tempo real com Sportmonks free. Quando o código estiver sólido e o produto validado, fazer upgrade de plano e trocar para ligas principais. Investimento zero na fase de desenvolvimento.
- **Dados de xG:** Disponíveis a partir de 2024, via add-on pago — usar Understat como primária no free
- **Crédito obrigatório:** Não
- **URL:** https://www.sportmonks.com

---

### 4. Understat
**Papel:** Primária para todas as métricas avançadas (xG, xA, npxG, xGChain, xGBuildup).

- **Plano:** Gratuito — site público sem API oficial
- **Cobertura:** Premier League, La Liga, Bundesliga, Serie A, Ligue 1, RFPL — histórico desde 2014/15
- **Dados disponíveis:** xG, xA, npg, npxG, xGChain, xGBuildup por jogador e time; shot maps; dados por partida; 18 métricas avançadas por jogador; 562+ jogadores por liga
- **Estratégia de acesso:** Understat embeda dados como JSON dentro de script tags — não usa HTML tables. Scraping via biblioteca `understatapi` (Python) ou scraper customizado. Rate limit respeitoso: máximo 8 req/min, 6 segundos entre requests.
- **Por que Understat e não FBref para xG:** FBref usa Cloudflare com proteção agressiva contra bots, exigindo scraping via browser headless (caro). Understat serve dados sem proteção agressiva, confiável e gratuito.
- **Job de atualização:** Rodar após cada rodada da liga. Não é tempo real — dados de xG ficam disponíveis após o fim da partida.
- **Crédito obrigatório:** Não — dados são públicos. Boas práticas: não sobrecarregar o servidor.
- **URL:** https://understat.com

---

### 5. The-Odds-API
**Papel:** Validação cruzada de placares ao vivo e contexto de mercado.

- **Plano:** Free — 500 req/mês
- **Dados disponíveis:** Odds pré-jogo e ao vivo, placar em andamento, status do jogo (tempo, interrupções)
- **Por que usar:** O modelo de negócio das casas de apostas exige precisão absoluta em tempo real. Placar e status de jogo têm velocidade e precisão excepcionais — serve como motor de validação para cruzar com outras APIs.
- **Estratégia de uso:** Usar pontualmente para validação cruzada de inconsistências detectadas nas fontes primárias. 500 req/mês é suficiente para validação assíncrona, não para polling contínuo.
- **Crédito obrigatório:** Não
- **URL:** https://the-odds-api.com

---

### 6. FBref (Sports Reference)
**Papel:** Fonte de dados históricos profundos e métricas Opta para contexto analítico.

- **Plano:** Gratuito — site público
- **Dados disponíveis:** Estatísticas avançadas com dados Opta (xG, xA, progressive passes, pressures, defensive actions), histórico extenso, comparações entre ligas e temporadas
- **Estratégia de acesso:** Biblioteca `soccerdata` (Python) para scraping estruturado. Usar com moderação — Cloudflare pode bloquear scraping agressivo. Ideal para jobs noturnos de enriquecimento histórico, não para tempo real.
- **Uso no FutMetricX:** Enriquecer perfis históricos de jogadores, comparações cross-temporada, contexto tático de longo prazo para a LLM.
- **Crédito:** A Sports Reference pede atribuição quando os dados são citados publicamente. Nos relatórios narrativos gerados pela LLM, citar "via FBref" quando dado histórico for mencionado diretamente.
- **URL:** https://fbref.com

---

### 7. openfootball (GitHub)
**Papel:** Fallback histórico e dados estruturados de fixtures para temporadas passadas.

- **Plano:** Totalmente gratuito, domínio público, sem API key
- **Dados disponíveis:** Fixtures e resultados históricos em JSON, Premier League, Bundesliga, La Liga, Champions League
- **Limitações:** Atualizado pela comunidade — pode ter gaps. Não serve para tempo real.
- **Uso no FutMetricX:** Seed inicial do banco de dados histórico. Contexto de confrontos diretos passados para a LLM.
- **Crédito obrigatório:** Não — domínio público
- **URL:** https://github.com/openfootball

---

## Arquitetura do Banco de Dados Interno

### Princípio de armazenamento

O PostgreSQL do FutMetricX é o **único banco que a LLM consulta**. Nenhuma API externa é chamada em tempo de geração de relatório — tudo já está no banco, normalizado e resolvido. As APIs são consultadas apenas pelos workers de ingestão, em background.

```
APIs Externas → Workers de Ingestão → Resolução de Conflitos → PostgreSQL → LLM → Relatório
```

### Schema principal (simplificado)

```sql
-- Competições
competitions (id, name, country, season, source_id, source_name)

-- Times
teams (id, name, short_name, country, competition_id, source_id, source_name)

-- Jogadores
players (
  id, name, nationality, position, age, team_id,
  source_id, source_name, -- fonte primária deste registro
  updated_at
)

-- Fixtures
fixtures (
  id, competition_id, home_team_id, away_team_id,
  scheduled_at, status, -- scheduled | live | finished
  home_score, away_score,
  source_primary, -- qual API é a verdade para este fixture
  updated_at
)

-- Estatísticas básicas por partida
match_stats (
  id, fixture_id, team_id, player_id,
  goals, assists, shots, shots_on_target,
  passes, pass_accuracy, yellow_cards, red_cards,
  minutes_played, source_name, updated_at
)

-- Métricas avançadas (xG layer)
advanced_metrics (
  id, fixture_id, team_id, player_id,
  xg, xa, npxg, xg_chain, xg_buildup,
  progressive_passes, pressures, defensive_actions,
  source_name, -- sempre Understat no MVP
  updated_at
)

-- Forma recente (calculada internamente)
team_form (
  id, team_id, competition_id, last_5, last_10,
  wins, draws, losses, goals_scored, goals_conceded,
  xg_avg, xga_avg, -- calculado sobre advanced_metrics
  updated_at
)

-- Log de inconsistências para auditoria
data_conflicts (
  id, entity_type, entity_id, field_name,
  value_primary, value_fallback, delta,
  source_primary, source_fallback,
  detected_at, resolved
)
```

---

## Pipeline de Ingestão

### Workers e frequência

| Worker | Frequência | Fonte | Dados |
|---|---|---|---|
| `fixtures_worker` | A cada 24h | football-data.org | Fixtures futuros da temporada |
| `livescore_worker` | A cada 6s (durante jogo) | API-Football | Placar, eventos, lineups ao vivo |
| `player_stats_worker` | Após fim de cada partida | API-Football | Estatísticas básicas pós-jogo |
| `xg_worker` | Após fim de cada rodada | Understat | Métricas avançadas xG/xA/npxG |
| `historical_worker` | Job noturno semanal | FBref / openfootball | Enriquecimento histórico |
| `odds_validator` | Assíncrono, sob demanda | The-Odds-API | Validação cruzada de placares |
| `conflict_resolver` | A cada 1h | Interno | Detecta e loga divergências entre fontes |

### Fluxo de resolução de conflitos

```
1. Worker primário insere/atualiza dado no PostgreSQL com campo source_name
2. Worker de fallback roda e compara valor com o que está no banco
3. Se delta > threshold configurado → insere em data_conflicts, mantém valor primário
4. conflict_resolver analisa data_conflicts periodicamente
5. Alertas no log para deltas críticos (ex: xG diverge > 0.5, fixture com horário diferente)
6. Revisão manual apenas para conflitos críticos — resto é automaticamente resolvido pela hierarquia
```

---

## Estratégia de Cache

Cache em dois níveis para minimizar chamadas de API e custo:

**Nível 1 — PostgreSQL (cache persistente):**
Todo dado já buscado fica armazenado localmente. TTL por tipo:
- Fixtures futuros: 24 horas
- Resultados finalizados: permanente (nunca mudam)
- Estatísticas pós-jogo: 6 horas (pode ser atualizado com dados finais)
- xG e métricas avançadas: permanente após jogo finalizado
- Livescore durante jogo: 30 segundos

**Nível 2 — Redis (cache de sessão para a LLM):**
Contexto de geração de relatório fica em Redis com TTL de 1 hora. Se dois usuários pedem relatório do mesmo jogo em sequência, o segundo recebe resposta instantânea sem re-consultar o banco.

---

## Cobertura por Competição no MVP

| Competição | Fixtures | Resultados ao vivo | Stats básicas | xG / Avançadas |
|---|---|---|---|---|
| Premier League | ✅ football-data.org | ✅ API-Football | ✅ API-Football | ✅ Understat |
| Champions League | ✅ football-data.org | ✅ API-Football | ✅ API-Football | ✅ Understat |
| Brasileirão Série A | ✅ football-data.org | ✅ API-Football | ✅ API-Football | ⚠️ Understat não cobre* |
| La Liga | ✅ football-data.org | ✅ API-Football | ✅ API-Football | ✅ Understat |
| Bundesliga | ✅ football-data.org | ✅ API-Football | ✅ API-Football | ✅ Understat |

*Para o Brasileirão, métricas avançadas ficam limitadas às disponíveis no API-Football (sem xG) no MVP. Resolver na Fase 2 via upgrade de plano ou fonte adicional.

---

## Custo Total na Fase MVP

| Fonte | Custo mensal |
|---|---|
| football-data.org | €0 |
| API-Football | $0 (100 req/dia free) |
| Sportmonks | $0 (free tier) |
| Understat | $0 (scraping público) |
| The-Odds-API | $0 (500 req/mês free) |
| FBref | $0 (scraping público) |
| openfootball | $0 (domínio público) |
| **Total** | **€0** |

Quando o produto escalar e gerar receita, o upgrade natural é:
- football-data.org → €29/mês (desbloqueia lineups, artilheiros, elencos, livescores)
- API-Football → plano pago (~$10-30/mês, remove limite de 100 req/dia)
- Sportmonks → upgrade de liga para Premier League + Champions League

---

## Resumo Executivo

O FutMetricX não depende de uma única fonte de dados. Ele opera uma **orquestra de APIs gratuitas** com hierarquia clara, cache agressivo e resolução automática de conflitos. A LLM nunca consulta APIs diretamente — ela só lê o PostgreSQL interno, que já contém dados limpos, normalizados e auditados.

O diferencial analítico do produto — métricas avançadas como xG, xA, npxG e xGChain — vem do Understat, gratuito, confiável e com histórico desde 2014. Isso coloca o FutMetricX no mesmo nível de profundidade analítica de plataformas pagas, com custo zero no MVP.

---

*FutMetricX — Futebol com inteligência.*
