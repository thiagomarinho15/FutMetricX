# FutMetricX — Action Plan

Plano de construção do FutMetricX como aplicação web Flask, dockerizada, com banco de dados, segurança e geração de relatórios via LLM (Claude API). Arquitetura e padrões baseados nos projetos SynthesAIzer e ResumeX.

---

## Stack Definida

| Camada | Tecnologia |
|---|---|
| Backend | Python 3.12 + Flask |
| ORM | Flask-SQLAlchemy + Flask-Migrate (Alembic) |
| Banco de dados | MySQL 8.0 (Docker) |
| Auth | Flask-Login + Flask-Security + Argon2 |
| Formulários | Flask-WTF (CSRF + validação) |
| Admin | Flask-Admin |
| LLM | Claude API (Anthropic SDK) |
| Dados de futebol | StatsBomb Open Data + FBref |
| Notícias | RSS feeds (feedparser) |
| Jobs agendados | APScheduler |
| Streaming | SSE (Server-Sent Events) |
| Frontend | Jinja2 + CSS customizado + Vanilla JS |
| Font | Montserrat (Google Fonts) |
| Servidor | Gunicorn (produção) |
| Infra | Docker + docker-compose |

---

## Estrutura de Pastas

```
futmetricx/
├── main.py                        # Entrypoint Flask
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── entrypoint.sh                  # Gunicorn startup
├── seed.py                        # Popula DB com dados reais
├── .env.example
├── CLAUDE.md
├── action-plan.md
│
├── app/
│   ├── __init__.py                # App factory + extensões + security headers
│   ├── config.py                  # Config por env (dev/prod)
│   ├── models.py                  # ORM: User, Role, Partida, Jogador, Relatorio, Noticia, Historico
│   ├── views.py                   # Todas as rotas
│   ├── forms.py                   # WTForms (validação apenas, sem lógica)
│   ├── security.py                # Argon2: hash_senha(), verificar_senha()
│   ├── adm.py                     # Flask-Admin com AdminAccessMixin
│   │
│   ├── services/
│   │   ├── data_fetcher.py        # StatsBomb Open Data + FBref
│   │   ├── news_fetcher.py        # RSS aggregation + parsing
│   │   ├── report_generator.py    # Prompts + chamada Claude API (streaming)
│   │   └── scheduler.py           # APScheduler: jobs de ingestão e geração
│   │
│   ├── static/
│   │   ├── css/
│   │   │   ├── style.css          # CSS variables globais + reset
│   │   │   ├── navbar.css         # Navbar fixa (60px, padrão SynthesAIzer)
│   │   │   ├── cards.css          # Cards de partida/jogador com hover lift
│   │   │   ├── form.css           # Login/cadastro
│   │   │   ├── report.css         # Página de relatório + toggle dual-tone
│   │   │   ├── news.css           # Feed de notícias
│   │   │   └── loading.css        # Progress bar durante geração LLM
│   │   └── js/
│   │       ├── navbar.js          # Dropdown menu
│   │       ├── cards.js           # Renderização de cards, filtros
│   │       ├── report.js          # Toggle Torcedor/Profissional, streaming SSE
│   │       ├── news.js            # Feed de notícias + botão "Analisar impacto"
│   │       └── app.js             # Orquestrador principal
│   │
│   └── templates/
│       ├── base.html              # Template base Jinja2
│       ├── index.html             # Dashboard: próximas partidas
│       ├── partida.html           # Relatório pré/pós-jogo dual-tone
│       ├── jogador.html           # Perfil narrativo do jogador
│       ├── brasileiros.html       # Brasileiros no exterior
│       ├── noticias.html          # Feed de notícias + análise de impacto
│       ├── login.html
│       ├── cadastro.html
│       └── _flash_messages.html
│
└── migrations/
    └── versions/
```

---

## Modelos de Banco de Dados

```python
# app/models.py

# Autenticação (padrão SynthesAIzer/ResumeX)
User          — id, nome, email, senha (Argon2), active, tier, fs_uniquifier, roles[]
Role          — id, name, description
roles_users   — FK user_id + role_id (many-to-many, CASCADE)

# Domínio do futebol
Partida       — id, time_casa, time_visitante, competicao, temporada, rodada,
                data_partida, status ('agendada'|'encerrada'), stats_json (TEXT)

Jogador       — id, nome, time_atual, nacionalidade, posicao,
                stats_json (TEXT), temporada, ativo

Relatorio     — id, tipo ('pre_torcedor'|'pre_profissional'|'pos'|'jogador'|'locutor'),
                partida_id (FK nullable), jogador_id (FK nullable),
                conteudo (TEXT), gerado_em (DateTime UTC), user_tier_minimo

Noticia       — id, titulo, url, fonte, publicada_em, resumo_impacto (TEXT),
                time_relacionado, jogador_relacionado, impacto_processado (Bool)

ContextoHistorico — id, time1, time2, narrativa (TEXT), atualizado_em
```

---

## Segurança

Seguindo o padrão dos dois projetos de referência:

- **Senha**: Argon2 via `argon2-cffi` — `hash_senha()` / `verificar_senha()`
- **Sessão**: `SESSION_COOKIE_HTTPONLY=True`, `SESSION_COOKIE_SAMESITE='Lax'`, `PERMANENT_SESSION_LIFETIME=8h`
- **CSRF**: Flask-WTF global — todos os forms incluem `{{ form.csrf_token }}`
- **Rate limiting** no login: 5 tentativas / 60s por IP (in-memory, sem dependência externa)
- **Security headers** via `@app.after_request`:
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: SAMEORIGIN`
  - `Referrer-Policy: strict-origin-when-cross-origin`
  - `Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline'`
- **Enumeração de usuários**: mesmo retorno para "email não encontrado" e "senha errada"
- **SQLAlchemy ORM**: proteção contra SQL injection nativa
- **Segredos**: apenas via `.env` — nunca hardcoded
- **Tiers**: Standard / Pro / Max — rotas protegidas por `user.tier`

---

## Docker

**Dockerfile** (Python 3.12-slim + Gunicorn):
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
```

**entrypoint.sh**:
```bash
#!/bin/bash
set -e
flask db upgrade
exec gunicorn main:app --bind 0.0.0.0:8000 --workers 2 --timeout 180
```

**docker-compose.yml** (Flask + MySQL 8.0):
```yaml
services:
  web:
    build: .
    ports: ["8000:8000"]
    env_file: .env
    depends_on:
      db:
        condition: service_healthy
    restart: unless-stopped

  db:
    image: mysql:8.0
    environment:
      MYSQL_DATABASE: ${DB_NAME}
      MYSQL_USER: ${DB_USER}
      MYSQL_PASSWORD: ${DB_PASSWORD}
      MYSQL_ROOT_PASSWORD: ${DB_ROOT_PASSWORD}
    volumes: [futmetricx_mysql:/var/lib/mysql]
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-u${DB_USER}", "-p${DB_PASSWORD}"]
      interval: 10s
      retries: 5
    restart: unless-stopped

volumes:
  futmetricx_mysql:
```

---

## Motor LLM — Multi-provider

O motor de geração de relatórios suportará múltiplos provedores de LLM, seguindo o padrão do `summarizer.py` do ResumeX. As chaves gratuitas disponíveis serão adicionadas manualmente ao `.env` no início da Fase 2 — nenhuma chave será definida antes disso nem commitada no repositório.

**Providers planejados** (definição final na Fase 2):
- Provedores gratuitos com chaves disponíveis: a confirmar no início da Fase 2
- Fallback local via Ollama (sem chave, offline)

**Arquitetura do `report_generator.py`** (padrão `summarizer.py` do ResumeX):
```python
# app/services/report_generator.py

# Prompts especializados por formato:
PROMPTS = {
    'pre_torcedor':      "Tom narrativo e descontraído. Contexto de forma, curiosidades...",
    'pre_profissional':  "Tom técnico. Métricas contextualizadas, padrões táticos...",
    'pos':               "Análise pós-jogo. Pontos de virada, substituições, fases...",
    'jogador':           "Perfil narrativo. Trajetória, momento, stat interessante...",
    'locutor':           "Frases curtas, verbalizáveis. Dados que cabem numa respiração...",
    'impacto_noticia':   "Extraia contexto extra-campo relevante para o próximo relatório...",
}

# Streaming via SSE — provider selecionado por parâmetro:
def gerar_relatorio_stream(tipo, contexto, provider):
    prompt = montar_prompt(tipo, contexto)
    if provider == "groq":
        yield from _stream_groq(prompt)
    elif provider == "gemini":
        yield from _stream_gemini(prompt)
    elif provider == "ollama":
        yield from _stream_ollama(prompt)
    # ... demais providers adicionados na Fase 2
```

> **Fase 2 — Passo 0 (antes de qualquer código LLM):** Thiago adiciona as chaves disponíveis ao `.env` local. A partir das chaves presentes, definimos quais providers implementar e a ordem de fallback.

---

## Frontend (padrão SynthesAIzer)

**Paleta de cores** (CSS variables em `style.css`):
```css
:root {
  --verde-escuro:   #1a472a;   /* cor primária — futebol */
  --verde-medio:    #2d6a4f;   /* hover, botões secundários */
  --verde-claro:    #52b788;   /* acentos, badges */
  --dourado:        #f4a261;   /* destaques, tier Pro */
  --azul-pro:       #285E8E;   /* modo profissional */
  --fundo:          #f8f9fa;
  --card-bg:        #ffffff;
  --texto-escuro:   #333333;
  --texto-medio:    #555555;
  --borda:          #e0e0e0;
  --sombra:         rgba(0,0,0,0.07);
}
```

**Toggle Dual-Tone** (elemento central de UX):
```html
<!-- Inspirado no view switcher do SynthesAIzer (Cards / Mapa) -->
<div class="modo-toggle">
  <button class="btn-modo active" data-modo="torcedor">Torcedor</button>
  <button class="btn-modo" data-modo="profissional">Profissional</button>
</div>
<div id="conteudo-torcedor">...</div>
<div id="conteudo-profissional" style="display:none">...</div>
```

**Padrões reutilizados do SynthesAIzer:**
- Navbar fixa 60px (logo | brand | user dropdown)
- Cards com `translateY(-5px)` no hover + sombra
- Modais com backdrop `rgba(40,40,40,0.6)` + `fadeIn` cubic-bezier
- Loading bar verde durante geração LLM
- Flash messages como banner animado
- Filtros em dropdown posicionado com checkboxes

**Padrões reutilizados do ResumeX:**
- SSE streaming com output progressivo na tela
- Badges de tier (Standard / Pro / Max)
- Estrutura de formulário de login/cadastro
- `@app.after_request` security headers

---

## Rotas Principais

```
GET  /                          → Dashboard (próximas partidas)
GET  /partida/<id>              → Relatório da partida (dual-tone)
POST /partida/<id>/gerar        → Dispara geração LLM (streaming SSE)
GET  /jogador/<id>              → Perfil narrativo do jogador
GET  /brasileiros               → Brasileiros no exterior
GET  /noticias                  → Feed de notícias
POST /noticias/<id>/impacto     → Analisa impacto da notícia (streaming SSE)
GET  /login                     → Login
POST /login
GET  /cadastro                  → Cadastro
POST /cadastro
GET  /sair                      → Logout
GET  /admin/                    → Painel admin (role=admin)
```

---

## Roadmap de Execução

### Fase 0 — Fundação ✅ CONCLUÍDA
- [x] Criar estrutura de pastas completa
- [x] `Dockerfile` + `docker-compose.yml` + `entrypoint.sh`
- [x] `.env` local com todas as variáveis (nunca commitado; `.env` e `.env.example` no `.gitignore`)
- [x] `app/__init__.py` — factory, extensões, security headers
- [x] `app/config.py` — validação de env vars no startup
- [x] `app/models.py` — User, Role, roles_users
- [x] `app/security.py` — Argon2
- [x] `app/forms.py` — LoginForm, CadastroForm
- [x] `app/views.py` — rotas de auth (login, cadastro, logout)
- [x] Templates: `base.html`, `login.html`, `cadastro.html`, `_flash_messages.html`
- [x] CSS: `style.css` (variáveis), `navbar.css`, `form.css`
- [x] `app/adm.py` — Flask-Admin com AdminAccessMixin
- [x] `seed.py` — roles padrão + user admin
- [x] Testar: `docker compose up` → login funcional ✅ (testado em 2026-04-25)

### Fase 1 — Dados de Futebol
- [ ] `app/models.py` — adicionar Partida, Jogador
- [ ] `app/services/data_fetcher.py` — StatsBomb Open Data (Premier League + Brasileirão)
- [ ] `app/services/data_fetcher.py` — FBref (estatísticas de jogadores)
- [ ] Migration: tabelas Partida e Jogador
- [ ] `seed.py` — popular com partidas e jogadores reais da temporada atual
- [ ] Admin: views para Partida e Jogador
- [ ] Rota `GET /` — listar próximas partidas com cards
- [ ] CSS: `cards.css` — card de partida com times, data, competição
- [ ] Testar: dashboard com dados reais

### Fase 2 — Motor LLM
- [x] **Passo 0:** Chaves LLM adicionadas ao `.env` local (Groq ×3, Gemini ×3, Ollama local)
- [x] Providers definidos: Groq como primário, Gemini como secundário, Ollama como fallback offline
- [ ] `app/models.py` — adicionar Relatorio
- [ ] `app/services/report_generator.py` — multi-provider + 5 prompts especializados
- [ ] Streaming SSE no Flask (padrão ResumeX `summarizer.py`)
- [ ] `report.js` — consome SSE, renderiza output progressivo
- [ ] Loading bar durante geração
- [ ] Armazenar relatório gerado no DB (não regenerar se já existe)
- [ ] Testar: geração de relatório pré-jogo torcedor

### Fase 3 — Relatórios Core (MVP)
- [ ] `app/models.py` — Relatorio completo (ambos os tons)
- [ ] Rota `GET /partida/<id>` — página com toggle dual-tone
- [ ] Toggle Torcedor / Profissional (JS + CSS animado)
- [ ] Rota `POST /partida/<id>/gerar` — dispara geração dos dois tons
- [ ] `partida.html` — layout completo com stats + relatório
- [ ] Rota `GET /jogador/<id>` — perfil narrativo
- [ ] `jogador.html` — card do jogador com streaming
- [ ] CSS: `report.css` — layout do relatório, tipografia legível
- [ ] Testar: fluxo completo torcedor → profissional

### Fase 4 — Notícias e Contexto
- [ ] `app/models.py` — Noticia, ContextoHistorico
- [ ] `app/services/news_fetcher.py` — RSS (ESPN, UOL, The Athletic, Cazé TV)
- [ ] `app/services/scheduler.py` — APScheduler: fetch RSS a cada 30min
- [ ] Rota `GET /noticias` — feed paginado
- [ ] Rota `POST /noticias/<id>/impacto` — análise de impacto streaming
- [ ] `news.js` — botão "Analisar impacto" com loading state
- [ ] Rota `GET /brasileiros` — brasileiros no exterior
- [ ] ContextoHistorico: geração de retrospecto entre clubes
- [ ] Integrar contexto de notícias nos relatórios de partida
- [ ] CSS: `news.css` — feed com fonte, data, badge de impacto

### Fase 5 — Engajamento
- [ ] Relatório pós-jogo narrativo (trigger automático após `status='encerrada'`)
- [ ] Modo Locutor: prompt + formato de output curto/verbalizável
- [ ] Cards compartilháveis (PNG via `imgkit` ou canvas JS)
- [ ] Toggle para Modo Locutor na página da partida
- [ ] Scheduler: geração automática de relatórios pré-jogo (D-1)
- [ ] Tier gates: Pro = relatório profissional, Max = locutor + PDF

### Fase 6 — Polimento e Launch
- [ ] Mobile: breakpoints e layout responsivo em todos os templates
- [ ] PWA: `manifest.json` + service worker básico
- [ ] Cache: TTL para relatórios já gerados (não rechamar LLM)
- [ ] Otimização: lazy loading de imagens, minificação CSS/JS
- [ ] Auditoria de segurança: revisar CSP, rate limits, validações
- [ ] `README.md` atualizado com instruções de setup
- [ ] Variáveis de produção: `SESSION_COOKIE_SECURE=True`, debug off
- [ ] Testar deploy completo: `docker compose up --build`

---

## Variáveis de Ambiente (.env — nunca commitado)

```env
# Flask
SECRET_KEY=...
FLASK_HOST=0.0.0.0
FLASK_PORT=8000
FLASK_DEBUG=False

# Banco de dados
DB_HOST=db
DB_PORT=3306
DB_NAME=futmetricx
DB_USER=futmetricx_user
DB_PASSWORD=...
DB_ROOT_PASSWORD=...

# Sessão
SESSION_COOKIE_SECURE=False   # True em produção (HTTPS)

# Admin
ADMIN_EMAIL=...
ADMIN_PASSWORD=...

# Groq (primário)
GROQ_KEY_1=...
GROQ_KEY_2=...
GROQ_KEY_3=...
GROQ_MODEL=llama-3.3-70b-versatile

# Gemini (secundário)
GEMINI_KEY_1=...
GEMINI_KEY_2=...
GEMINI_KEY_3=...
GEMINI_MODEL=gemini-2.0-flash

# Ollama (fallback local)
OLLAMA_HOST=host.docker.internal
OLLAMA_MODEL=llama3.2
```

---

## Dependências (requirements.txt)

```
flask==3.1.0
flask-sqlalchemy==3.1.1
flask-migrate==4.0.7
flask-login==0.6.3
flask-security-too==5.5.2
flask-wtf==1.2.1
flask-admin==1.6.1
argon2-cffi==23.1.0
mysqlclient==2.2.4
groq==0.13.1
google-generativeai==0.8.3
statsbombpy==1.1.3
feedparser==6.0.11
apscheduler==3.10.4
gunicorn==23.0.0
python-dotenv==1.0.1
email-validator==2.1.2
WTForms==3.1.2
```

---

*Última atualização: 2026-04-25 — Fase 0 100% concluída e testada. App rodando em `docker compose up --build`. Próximo: Fase 1 (dados de futebol).*
