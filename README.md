# FutMetricX

**Futebol com inteligência.**

FutMetricX é uma plataforma de análise de futebol orientada a dados e alimentada por LLM, que transforma métricas, notícias e contexto tático em relatórios narrativos inteligentes — para torcedores e profissionais, no mesmo produto.

---

## O Problema

O mercado tem dois extremos mal conectados:

- **Plataformas enterprise** (Hudl, StatsBomb, Wyscout): €3.000–€10.000/ano, inacessíveis para quem não é clube profissional.
- **Ferramentas gratuitas** (FBref, WhoScored): entregam tabelas de números sem contexto narrativo, tático ou extra-campo.

No meio ficam analistas de academias, jornalistas esportivos, narradores, scouts independentes e torcedores avançados — todos sem uma ferramenta que fale sua língua, no seu idioma, no seu preço.

**FutMetricX fecha esse gap.**

---

## Para Quem

| Perfil | O que busca |
|---|---|
| Torcedor casual | Análise leve e narrativa, mobile, compartilhável nas redes |
| Profissional de transmissão | Briefing rápido, verbalizável, confiável para pré-jogo |
| Analista / scout semi-profissional | Insights táticos e de scouting sem custo enterprise |

---

## Funcionalidades

### Relatório Pré-Jogo Dual-Tone
O core do produto. Para cada partida, dois relatórios gerados da mesma base de dados:

- **Modo Torcedor** — tom narrativo e descontraído: momento de forma, história do confronto, curiosidades sobre os jogadores-chave.
- **Modo Profissional** — tom técnico e analítico: linguagem tática, métricas contextualizadas, padrões de jogo, insights verbalizáveis para transmissão ao vivo.

O usuário alterna entre os dois com um toggle central na interface.

### Relatório Pós-Jogo Narrativo
Gerado automaticamente após o apito final. Explica o que aconteceu taticamente além do placar: pontos de virada, impacto de substituições, fases do jogo e padrões que se confirmaram ou quebraram.

### Perfil Narrativo do Jogador
Card do jogador mais relevante para a partida — trajetória, momento atual, estatística interessante explicada de forma humana. Alto potencial de viralização.

### Cobertura de Brasileiros no Exterior
Relatórios semanais e pré-jogo focados em jogadores brasileiros na Europa e em outras ligas internacionais, em português. Nicho sem concorrente direto no mercado brasileiro.

### Contexto Histórico entre Clubes
Retrospecto de confrontos diretos com narrativa — padrões históricos, recordes e curiosidades que enriquecem a análise do confronto atual.

### Modo Locutor
Formato específico para rádio e streaming: frases curtas, dados verbalizáveis, estatísticas que soam bem faladas e cabem numa respiração.

### Feed de Notícias com Análise de Impacto
Agregação de notícias de fontes credenciadas via RSS. Cada notícia é processada pela LLM para extrair contexto extra-campo relevante (lesões, transferências, clima interno) e incorporado automaticamente aos relatórios. Botão **"Analisar impacto"** em cada notícia.

---

## Arquitetura Técnica

```
Fontes de Dados (StatsBomb / FBref / RSS)
        ↓
Pipeline de Ingestão (jobs agendados)
        ↓
PostgreSQL (dados estruturados)
        ↓
RAG (banco vetorial — contexto histórico, perfis, notícias)
        ↓
LLM — Claude API (geração narrativa por prompts especializados)
        ↓
Backend FastAPI
        ↓
Frontend Next.js (PWA, mobile-first, toggle dual-tone)
```

**Stack planejada:**
- Backend: Python + FastAPI
- Frontend: Next.js (PWA, mobile-first)
- LLM: Claude API
- RAG: Pinecone ou Supabase pgvector
- Banco de dados: PostgreSQL
- Ingestão: StatsBomb Open Data + FBref (MVP) → Opta/Stats Perform ou SportRadar
- Infra MVP: Railway ou Render

---

## Roadmap de MVP

**Fase 1 — Core**
- [ ] Relatório pré-jogo dual-tone (Premier League + Brasileirão Série A)
- [ ] Perfil narrativo do jogador-chave
- [ ] Cobertura de brasileiros no exterior
- [ ] Feed de notícias com RSS

**Fase 2 — Engajamento**
- [ ] Relatório pós-jogo narrativo
- [ ] Contexto histórico entre clubes
- [ ] Botão "Analisar impacto" nas notícias
- [ ] Cards compartilháveis para Instagram e X

**Fase 3 — Profissional**
- [ ] Modo Locutor
- [ ] Scouting por linguagem natural
- [ ] Exportação de relatórios em PDF
- [ ] API para integração com ferramentas de terceiros

---

## Diferenciais

- **LLM como camada de interpretação** — não de decoração. Transforma dados em argumentos, não em gráficos mais bonitos.
- **Contexto extra-campo integrado** — performance + notícias + bastidores, cruzados automaticamente.
- **Foco ibero-americano** — análise de qualidade em português, com preço acessível e cobertura de ligas brasileiras.
- **Dual-tone nativo** — um produto, dois públicos, a mesma engine.

---

*FMX — FutMetricX*
