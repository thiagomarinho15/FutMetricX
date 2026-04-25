# FutMetricX

## O que é

FutMetricX é uma plataforma de análise de futebol orientada a dados e alimentada por LLM, que transforma métricas, notícias e contexto tático em relatórios narrativos inteligentes. O produto atende simultaneamente ao torcedor que quer entender o jogo de forma acessível e ao profissional que precisa de insights técnicos para transmissões, análises e scouting.

O nome resume a proposta: **Fut** (futebol), **Metric** (dados, rigor analítico) e **X** (expansão, tecnologia, escala). A identidade secundária é **FMX**.

---

## Problema que resolve

O mercado hoje tem dois extremos mal conectados:

- Plataformas enterprise como Hudl/StatsBomb e Wyscout, que custam entre €3.000 e €10.000/ano e são inacessíveis para quem não é clube profissional.
- Ferramentas gratuitas como FBref e WhoScored, que entregam tabelas de números sem contexto narrativo, tático ou extra-campo.

No meio ficam analistas de academias, jornalistas esportivos, narradores, comentaristas, scouts independentes, criadores de conteúdo e torcedores avançados — todos sem uma ferramenta que fale sua língua, no seu idioma, no seu preço.

FutMetricX fecha esse gap.

---

## Público-alvo

**Torcedor casual** — consome análise de forma leve e descontraída antes e depois dos jogos. Quer entender o contexto sem precisar de formação técnica. Acessa principalmente via mobile e compartilha nas redes sociais.

**Profissional de transmissão** — narrador, comentarista, apresentador de podcast ou canal no YouTube. Precisa de briefing rápido, confiável e em formato verbalizável. Não tem tempo para pesquisa manual pré-jogo.

**Analista e scout semi-profissional** — trabalha em academias, clubes de menor porte ou jornalismo especializado. Precisa de insights táticos e de scouting sem pagar preço enterprise.

---

## Funcionalidades

### 1. Relatório pré-jogo dual-tone

O core do produto. Para cada partida, o sistema gera automaticamente dois relatórios a partir da mesma base de dados:

**Modo Torcedor** — tom descontraído e narrativo. Contexto de momento de forma, história do confronto, curiosidades sobre os jogadores-chave. Feito para ser lido 30 minutos antes do apito ou compartilhado como card nas redes sociais.

**Modo Profissional** — tom técnico e analítico. Linguagem de análise tática, métricas contextualizadas, padrões de jogo do adversário, insights verbalizáveis para uso em transmissão ao vivo ou comentário especializado.

O usuário alterna entre os dois modos com um toggle na interface.

### 2. Relatório pós-jogo narrativo

Gerado automaticamente após o apito final. Explica o que aconteceu taticamente além do placar: pontos de virada, impacto de substituições, fases do jogo, padrões que se confirmaram ou quebraram. Publicado nas horas de maior engajamento nas redes sociais, quando a concorrência ainda está editando vídeo.

### 3. Contexto de temporada e momento de forma

Análise factual de sequências, fases e tendências — sem predição de resultado. "O United não perde em casa há 7 jogos, mas enfrenta um Chelsea que venceu os últimos 4 confrontos diretos." Conteúdo jornalístico sólido, não especulação.

### 4. Perfil narrativo do jogador-chave

Card do jogador mais relevante para a partida: quem é, momento atual, trajetória, uma estatística interessante explicada de forma humana. Alto potencial de viralização porque personaliza o consumo do jogo para o torcedor.

### 5. Cobertura de brasileiros no exterior

Relatórios semanais e pré-jogo focados em jogadores brasileiros na Europa e em outras ligas internacionais, em português, com contexto de desempenho e momento de forma. Nicho sem concorrente direto hoje no mercado brasileiro.

### 6. Contexto histórico entre clubes

Retrospecto de confrontos diretos com narrativa — não apenas tabela de resultados. Padrões históricos, recordes, curiosidades e contexto que enriquecem a análise do confronto atual.

### 7. Modo Locutor

Formato específico para profissionais de rádio e streaming. Frases curtas, dados verbalizáveis, estatísticas que soam bem faladas e cabem numa respiração. Ignorado por todas as plataformas atuais, que pensam em visualização e não em verbalização.

### 8. Feed de notícias com análise de impacto

Agregação de notícias de fontes jornalísticas credenciadas (ESPN, Cazé TV, The Athletic, UOL Esporte, entre outras) e jornalistas de referência via RSS feeds públicos. Cada notícia é processada pela LLM para extrair contexto extra-campo relevante — conflitos de vestiário, lesões, transferências, clima interno — e incorporado automaticamente aos relatórios de análise.

O usuário pode clicar em qualquer notícia para ver o link original. O sistema não republica conteúdo protegido: cita, resume e referencia com link para a fonte.

Botão "Analisar impacto" em cada notícia: a LLM processa e adiciona o contexto ao próximo relatório do time ou jogador relacionado.

---

## Diferenciais estratégicos

**LLM como camada de interpretação, não de decoração.** A maioria das plataformas usa IA para gerar gráficos mais bonitos. FutMetricX usa LLM para transformar dados em narrativa contextualizada — a diferença entre um número e um argumento.

**Contexto extra-campo integrado.** Nenhuma plataforma de analytics cruza dados de performance com notícias e clima de bastidores. FutMetricX faz isso automaticamente, produzindo análises que refletem a realidade completa do jogo.

**Foco no mercado ibero-americano.** Análise de futebol de qualidade, em português, com preço acessível e cobertura de ligas brasileiras. O maior mercado de torcedores do mundo ainda não tem uma plataforma de analytics à sua altura.

**Dual-tone nativo.** Um produto, dois públicos, a mesma engine. O toggle entre modo casual e modo profissional é o elemento central da experiência.

---

## Arquitetura técnica

### Dados
- **MVP:** StatsBomb Open Data, FBref (dados abertos e gratuitos)
- **Médio prazo:** APIs pagas como Opta/Stats Perform ou SportRadar para cobertura em tempo real
- **Notícias:** RSS feeds públicos de veículos credenciados + fetch de conteúdo via URL para processamento pela LLM

### LLM e geração de conteúdo
- Claude ou GPT-4o via API como motor de geração narrativa
- Arquitetura RAG (Retrieval-Augmented Generation) com banco vetorial (Pinecone ou Supabase pgvector) para contextualizar relatórios com histórico de partidas, perfis de jogadores, notícias recentes e dados de temporada
- Prompts especializados por formato: modo torcedor, modo profissional, modo locutor, perfil de jogador, análise de impacto de notícia

### Backend
- Python com FastAPI
- PostgreSQL para dados estruturados de partidas e jogadores
- Pipeline de ingestão de dados com jobs agendados (Airflow ou cron no MVP)
- Worker assíncrono para processamento de notícias via RSS e geração de relatórios

### Frontend
- Next.js com foco em mobile-first
- Toggle central entre Modo Torcedor e Modo Profissional
- Cards compartilháveis gerados automaticamente para Instagram e X
- PWA para experiência mobile sem necessidade de app store no MVP

### Infraestrutura
- MVP: Railway ou Render (baixo custo operacional)
- Escala: AWS ou GCP com containerização via Docker

---

## Roadmap de MVP

**Fase 1 — Core**
- Relatório pré-jogo dual-tone para Premier League e Brasileirão Série A
- Perfil narrativo do jogador-chave
- Cobertura de brasileiros no exterior
- Feed de notícias com RSS das principais fontes

**Fase 2 — Engajamento**
- Relatório pós-jogo narrativo
- Contexto histórico entre clubes
- Botão "Analisar impacto" nas notícias
- Cards compartilháveis para redes sociais

**Fase 3 — Profissional**
- Modo Locutor com formato verbalizado
- Scouting por linguagem natural ("volante de contenção, menor de 24 anos, Brasileirão")
- Relatórios exportáveis em PDF para analistas
- API para integração com ferramentas de terceiros

---

## Posicionamento de mercado

FutMetricX não compete com StatsBomb ou Wyscout. Ataca o flanco que essas plataformas ignoram: o analista semi-profissional, o jornalista esportivo, o criador de conteúdo e o torcedor avançado do mercado ibero-americano. O preço, o idioma e a narrativa são os vetores de diferenciação — não o volume bruto de dados.

A longo prazo, o ativo mais valioso é a base de contexto proprietário construída pelo cruzamento de dados de performance com notícias, anotações de usuários e histórico de relatórios gerados — algo que nenhum concorrente pode replicar comprando uma API.

---

*FutMetricX — Futebol com inteligência.*
