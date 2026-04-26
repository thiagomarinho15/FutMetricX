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

## Stack Implementada

| Camada | Tecnologia |
|---|---|
| Backend | Python 3.12 + Flask |
| ORM | SQLAlchemy + Flask-Migrate |
| Banco | MySQL 8.0 |
| LLM | Groq (primário) → Gemini → Ollama (fallback) |
| Dados | StatsBomb Open Data |
| Notícias | feedparser (RSS — GE Globo, UOL, ESPN, BBC) |
| Jobs | APScheduler (RSS 30min + pré-jogo D-1) |
| Servidor | Gunicorn |
| Infra | Docker + docker-compose |
| PWA | manifest.json + service worker |

---

## Quick Start

### Pré-requisitos

- Docker + docker-compose
- Chave Groq gratuita: [console.groq.com](https://console.groq.com)

### 1. Clone

```bash
git clone https://github.com/thiagomarinho15/FutMetricX.git
cd FutMetricX
```

### 2. Crie o `.env`

```env
SECRET_KEY=<string-aleatoria-forte>
DB_HOST=db
DB_PORT=3306
DB_NAME=futmetricx
DB_USER=futmetricx_user
DB_PASSWORD=<senha>
DB_ROOT_PASSWORD=<senha-root>
SESSION_COOKIE_SECURE=False
ADMIN_EMAIL=admin@futmetricx.com
ADMIN_PASSWORD=<senha-admin>

GROQ_KEY_1=<sua-chave-groq>
GROQ_MODEL=llama-3.3-70b-versatile

GEMINI_KEY_1=
GEMINI_MODEL=gemini-2.0-flash

OLLAMA_HOST=host.docker.internal
OLLAMA_MODEL=llama3.2
```

### 3. Inicie

```bash
docker compose up --build
```

Na primeira execução (~60s o app sobe, seed demora ~30s mais):
- Migrações geradas e aplicadas automaticamente
- 416 partidas importadas (StatsBomb Open Data)
- 236 jogadores com posições e nacionalidades
- Notícias importadas dos feeds RSS

**Acesse: http://localhost:8000**

Painel admin: `/admin/` (credenciais do `.env`)

---

## Desenvolvimento

Ao modificar `models.py` (novos campos/tabelas):

```bash
docker compose down -v && docker compose up --build
```

Ao modificar apenas templates, CSS ou JS, primeiro rebuild a imagem:

```bash
docker compose up --build -d
```

> Não há bind mount — código é baked na imagem. Qualquer mudança Python requer rebuild.

---

## Produção

Antes de expor publicamente:

```env
SESSION_COOKIE_SECURE=True
```

Trocar `ADMIN_PASSWORD` por senha forte.

---

## Diferenciais

- **Dual-tone nativo** — um produto, dois públicos, a mesma engine
- **Contexto extra-campo** — notícias RSS cruzadas com dados de performance
- **Multi-provider LLM** — Groq → Gemini → Ollama, sem ponto único de falha
- **Foco ibero-americano** — em português, ligas europeias + abertura para brasileirão

---

*FMX — FutMetricX*
