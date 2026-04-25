# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

FutMetricX (FMX) is an LLM-powered football analytics platform that transforms match metrics, news, and tactical context into dual-audience narrative reports. The product serves two audiences simultaneously through a single interface: casual fans (accessible, narrative-driven) and semi-professional analysts/broadcasters (technical, data-rich). Target market is Ibero-American, primarily in Portuguese.

**Current status**: Specification/planning phase. `about.md` contains the full product spec; no application code exists yet.

---

## Planned Architecture

### Stack

- **Backend**: Python + FastAPI, PostgreSQL
- **Frontend**: Next.js (mobile-first, PWA)
- **LLM**: Claude API (preferred) or GPT-4o — narrative generation engine
- **RAG**: Pinecone or Supabase pgvector — retrieval-augmented context
- **Data ingestão**: StatsBomb Open Data + FBref (MVP), then Opta/Stats Perform or SportRadar
- **News**: Public RSS feeds (ESPN, The Athletic, UOL Esporte, Cazé TV, etc.) + URL fetch for LLM processing
- **Workers**: Async jobs for RSS ingestion and report generation (cron for MVP, Airflow later)
- **Infra MVP**: Railway or Render; scale to AWS/GCP with Docker

### Data Flow

```
Data Sources (StatsBomb/FBref/RSS)
        ↓
Ingestão Pipeline (scheduled jobs)
        ↓
PostgreSQL (structured match + player data)
        ↓
RAG layer (vector DB with historical context, player profiles, recent news)
        ↓
LLM (specialized prompts per format)
        ↓
Report API (FastAPI)
        ↓
Frontend (Next.js, dual-mode toggle)
```

### Core Report Types

1. **Pré-jogo dual-tone** — same data, two outputs: *Modo Torcedor* (casual, narrative) and *Modo Profissional* (tactical, technical)
2. **Pós-jogo narrativo** — tactical breakdown beyond the scoreline
3. **Perfil narrativo do jogador** — player card for key match figure
4. **Cobertura de brasileiros no exterior** — weekly reports on Brazilian players abroad
5. **Contexto histórico** — head-to-head narrative, not just results table
6. **Modo Locutor** — short, vocalizable phrases for radio/streaming professionals
7. **Feed de notícias + análise de impacto** — RSS aggregation with "Analyze impact" button that feeds context into upcoming reports

---

## Key Concepts

- **Dual-tone**: The central UX concept. A single toggle switches the entire report between fan mode and professional mode. All generation pipelines must produce both variants.
- **Extra-campo context**: News and behind-the-scenes information (injuries, transfers, locker room climate) is automatically cross-referenced with performance data — a key differentiator from pure analytics platforms.
- **Proprietary context base**: The long-term moat. Cross-referenced performance data, news, user annotations, and generated report history that accumulates over time.
- **MVP scope**: Premier League + Brasileirão Série A, Phase 1 features only (see `about.md` roadmap).

---

## Development Notes

Commands, linting, and test setup will be documented here as the project is built. When adding the backend, use FastAPI with async endpoints and structure around the report types listed above. When adding the frontend, Next.js with a central fan/professional mode toggle is the UX anchor.
