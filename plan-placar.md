# plan-placar.md — Plano: Atualização de Resultados em Tempo Real

## Problema Atual

O `livescore_worker` existente chama `get_live_fixtures(league_id)` para **cada uma das 7 ligas, a cada minuto**, usando a API-Football.

**Cálculo do desperdício:**
```
7 ligas × 60 min/h × 24 h/dia = 10.080 req/dia consumidos
Orçamento real (2 chaves × 100 req/dia)  = 200 req/dia
Excedente: 9.880 req/dia — 50× acima do limite
```

O sistema está quebrado por design: nunca passou de meia-noite sem esgotar o crédito.

---

## Diagnóstico das APIs Disponíveis

### API-Football (`v3.football.api-sports.io`)
- **Limite:** 100 req/dia por chave × 2 chaves = **200 req/dia total**
- **O que entrega:** placar ao vivo por liga, estatísticas de equipe por jogo, estatísticas de jogadores por jogo
- **Problema:** chamada por liga = 7 req/poll — escala mal
- **Uso ideal:** reservado para dados ricos que só existem aqui (stats de jogador/equipe), acionados uma vez por jogo em momentos pontuais

### football-data.org (`api.football-data.org/v4`)
- **Limite:** 10 req/min por chave × 2 chaves = **20 req/min = 28.800 req/dia**
- **Endpoint chave:** `GET /v4/matches?status=IN_PLAY` → retorna **todos os jogos ao vivo de todas as ligas em UMA única requisição**
- **Uso ideal:** polling de placar ao vivo — uma req cobre tudo simultaneamente

### Conclusão de design
> Usar **football-data.org como fonte primária de placar ao vivo** (generoso, um req cobre tudo).
> Usar **API-Football exclusivamente para stats ricas** (equipe e jogadores), acionadas apenas em marcos do jogo (intervalo, fim de jogo).

---

## Arquitetura da Solução

### Visão geral

```
APScheduler (1 min)
        │
        ▼
LivescoreOrchestrator.run()
        │
        ├─ Há jogos hoje/ao vivo? ──► NÃO → exit (0 req)
        │
        ├─ Calcular fase atual e intervalo-alvo
        │
        ├─ Intervalo-alvo decorrido desde último poll? ──► NÃO → exit (0 req)
        │
        ├─ Poll football-data.org (1 req, todos os jogos ao vivo)
        │         └── atualiza fixtures no banco
        │
        └─ Detectar transições de fase por fixture
                  ├─ Início detectado    → log
                  ├─ Intervalo detectado → API-Football team stats (1 req) [se budget OK]
                  └─ Fim detectado       → API-Football player stats (1 req) [se budget OK]
                                           → agenda xg_enrichment
```

### Controle de estado (Redis + fallback in-memory)

Para cada fixture ao vivo, o sistema mantém no Redis:
```
fmx:fixture:{id}:ht_done  → "1" (se stats de intervalo já foram buscadas)
fmx:fixture:{id}:ft_done  → "1" (se stats de fim já foram buscadas)
fmx:livescore:last_poll   → timestamp ISO do último poll ao football-data.org
fmx:apifootball:used:{YYYYMMDD} → contador de req API-Football consumidas hoje
```

TTL de todas as chaves: 48 horas (limpeza automática).

---

## Estratégia de Polling por Fase

O orquestrador determina o **intervalo-alvo** com base nos jogos ativos:

| Situação | Intervalo-alvo | Motivo |
|---|---|---|
| Nenhum jogo hoje | ∞ (sem polls) | Economia total |
| Jogo em <60 min (iminente) | 10 minutos | Confirmar horário/kickoff |
| 1º tempo em andamento | 2 minutos | Cobertura ativa |
| Intervalo (HT) | 5 minutos | Pausa no jogo |
| 2º tempo em andamento | 2 minutos | Cobertura ativa |
| Prorrogação (ET) | 1 minuto | Momento decisivo |
| Penaltis | 1 minuto | Momento decisivo |
| Todos finalizados | ∞ (sem polls) | Jornada encerrada |

Quando há múltiplos jogos simultâneos em fases diferentes, usa-se o **intervalo mais curto** entre eles.

---

## Orçamento API-Football (200 req/dia)

### Alocação proposta

| Uso | Req/jogo | Max jogos/dia | Total |
|---|---|---|---|
| Stats de equipe (intervalo) | 1 | 15 | 15 |
| Stats de jogadores (fim) | 1 | 15 | 15 |
| Worker seed/temporada | — | — | 50 |
| Reserva de segurança | — | — | 120 |
| **Total** | | | **200** |

### Guardrail de budget

Antes de qualquer req API-Football, o sistema verifica:
```
se req_usadas_hoje >= 180:
    skip stats ricas, manter só placar via football-data.org
    logar aviso de budget crítico
```

A contagem de requisições é feita no Redis e resetada à meia-noite UTC.

---

## Marcos de Jogo e Gatilhos

### Transição: `scheduled → live` (início detectado)
- Nenhuma req de API externa adicional
- Loga início do jogo
- Registra `kickoff_at` no Redis para cálculo de minuto

### Transição: `live (1H) → live (HT)` (intervalo detectado)
- **1 req API-Football:** `GET /fixtures/statistics?fixture={id}` (stats de equipe)
- Salva em `AdvancedMetrics` (xG da equipe, finalizações, posse)
- Marca `fmx:fixture:{id}:ht_done = 1`

### Transição: `live → finished` (fim detectado)
- **1 req API-Football:** `GET /fixtures/players?fixture={id}` (stats de jogadores)
- Upsert em `MatchStats` para todos os jogadores
- Agenda `enrich_xg_for_fixture(fixture_id)` (Understat, 2-4h depois)
- Marca `fmx:fixture:{id}:ft_done = 1`

---

## Implementação

### Arquivos criados/modificados

| Arquivo | Ação |
|---|---|
| `app/services/budget_tracker.py` | **Novo** — rastreia uso diário de API-Football no Redis |
| `app/workers/livescore_worker.py` | **Reescrito** — orquestrador inteligente |
| `app/clients/football_data.py` | **Estendido** — `get_live_matches()` global |
| `app/clients/api_football.py` | Já tem os endpoints necessários |

### Fluxo de req por dia (estimativa com 2 rodadas/semana)

**Dia com jogos (12 partidas):**
```
football-data.org:
  Poll a cada 2 min por ~3h de jogos = 90 polls × 1 req = 90 req  ✓ (budget: 28.800)

API-Football:
  Stats de equipe (HT): 12 jogos × 1 req = 12 req
  Stats de jogador (FT): 12 jogos × 1 req = 12 req
  Workers de seed/temporada: ~30 req
  Total: 54 req  ✓ (budget: 200)
```

**Dia sem jogos:**
```
football-data.org: 0 req
API-Football: 0 req (livescore) + ~10 req (workers)
Total: 10 req  ✓
```

---

## Checklist de Implementação

- [x] Criar `app/services/budget_tracker.py`
- [x] Reescrever `app/workers/livescore_worker.py`
- [x] Adicionar `get_live_matches()` em `app/clients/football_data.py`
- [x] Atualizar scheduler (nenhuma mudança necessária — mantém 1 min)
- [ ] Validar manualmente em dia de jogos ao vivo
- [ ] Configurar alertas de budget (opcional: Telegram/email quando >150 req/dia)

---

*FutMetricX — Futebol com inteligência.*
