"""
Multi-provider LLM report generator with streaming.
Priority: Groq (3 keys) → Gemini (3 keys) → Ollama (local fallback).
"""
import json
import logging
import os
import urllib.request

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

def montar_contexto_jogador(jogador) -> dict:
    return {
        'nome':         jogador.nome,
        'time':         jogador.time_atual or 'Desconhecido',
        'posicao':      jogador.posicao or 'Desconhecida',
        'nacionalidade': jogador.nacionalidade or 'Desconhecida',
        'temporada':    jogador.temporada or '',
    }


def montar_contexto(partida) -> dict:
    stats = partida.stats()
    return {
        'time_casa':      partida.time_casa,
        'time_visitante': partida.time_visitante,
        'competicao':     partida.competicao,
        'temporada':      partida.temporada,
        'rodada':         partida.rodada,
        'data':           partida.data_partida.strftime('%d/%m/%Y') if partida.data_partida else None,
        'placar_casa':    stats.get('placar_casa'),
        'placar_visitante': stats.get('placar_visitante'),
    }


def _montar_prompt(tipo: str, ctx: dict) -> str:
    # Standalone player profile — different context structure (no match fields)
    if tipo == 'perfil_jogador':
        return (
            "Você é um jornalista esportivo especializado em perfis de jogadores.\n"
            "Escreva um perfil narrativo envolvente sobre este jogador.\n\n"
            f"Nome: {ctx.get('nome')}\n"
            f"Clube: {ctx.get('time')}\n"
            f"Posição: {ctx.get('posicao')}\n"
            f"Nacionalidade: {ctx.get('nacionalidade')}\n"
            f"Temporada: {ctx.get('temporada')}\n\n"
            "Tom: narrativo e humano. Destaque o estilo de jogo, características marcantes, "
            "trajetória na carreira e o que torna este jogador especial.\n"
            "Responda em português do Brasil. Máximo 300 palavras."
        )

    info = (
        f"Partida: {ctx['time_casa']} vs {ctx['time_visitante']}\n"
        f"Competição: {ctx['competicao']} | Temporada: {ctx['temporada']}"
        + (f" | Rodada {ctx['rodada']}" if ctx.get('rodada') else '')
        + (f"\nData: {ctx['data']}" if ctx.get('data') else '')
        + (
            f"\nResultado: {ctx['placar_casa']} x {ctx['placar_visitante']}"
            if ctx.get('placar_casa') is not None else ''
        )
    )

    templates = {
        'pre_torcedor': (
            "Você é um comentarista esportivo apaixonado e carismático.\n"
            "Escreva um relatório pré-jogo emocionante e envolvente.\n\n"
            f"{info}\n\n"
            "Tom: descontraído, narrativo, cheio de energia. Destaque a rivalidade, "
            "o momento das equipes, os jogadores-chave e o que está em jogo. "
            "Use linguagem popular e acessível.\n"
            "Responda em português do Brasil. Máximo 280 palavras."
        ),
        'pre_profissional': (
            "Você é um analista tático especializado em futebol.\n"
            "Escreva uma análise técnica pré-jogo.\n\n"
            f"{info}\n\n"
            "Tom: técnico e preciso. Analise sistemas táticos prováveis, pontos fortes "
            "e fracos de cada equipe, tendências estatísticas e prognóstico fundamentado. "
            "Use terminologia tática (pressão alta, bloco médio, transição, etc.).\n"
            "Responda em português do Brasil. Máximo 350 palavras."
        ),
        'pos': (
            "Você é um analista tático pós-jogo.\n"
            "Escreva uma análise aprofundada do resultado.\n\n"
            f"{info}\n\n"
            "Tom: analítico. Identifique pontos de virada, substituições decisivas, "
            "fases da partida e implicações do resultado.\n"
            "Responda em português do Brasil. Máximo 350 palavras."
        ),
        'jogador': (
            "Você é um jornalista esportivo especializado em perfis de jogadores.\n"
            "Escreva um perfil narrativo do jogador mais impactante desta partida.\n\n"
            f"{info}\n\n"
            "Tom: narrativo e humano. Destaque o desempenho, o momento e a trajetória do jogador.\n"
            "Responda em português do Brasil. Máximo 280 palavras."
        ),
        'locutor': (
            "Você é um locutor esportivo de rádio e streaming.\n"
            "Crie frases curtas e verbalizáveis para a partida abaixo.\n\n"
            f"{info}\n\n"
            "Gere 6 frases de impacto, ideais para transmissão ao vivo. "
            "Cada frase em uma linha separada. Sem numeração nem marcadores.\n"
            "Responda em português do Brasil."
        ),
    }
    return templates.get(tipo, templates['pre_torcedor'])


# ---------------------------------------------------------------------------
# Provider: Groq
# ---------------------------------------------------------------------------

def _stream_groq(prompt: str, key: str, model: str):
    from groq import Groq
    client = Groq(api_key=key)
    stream = client.chat.completions.create(
        model=model,
        messages=[{'role': 'user', 'content': prompt}],
        stream=True,
        max_tokens=700,
        temperature=0.8,
    )
    for chunk in stream:
        text = chunk.choices[0].delta.content
        if text:
            yield text


# ---------------------------------------------------------------------------
# Provider: Gemini
# ---------------------------------------------------------------------------

def _stream_gemini(prompt: str, key: str, model: str):
    import google.generativeai as genai
    genai.configure(api_key=key)
    gmodel = genai.GenerativeModel(model)
    response = gmodel.generate_content(
        prompt,
        stream=True,
        generation_config={'max_output_tokens': 700, 'temperature': 0.8},
    )
    for chunk in response:
        if chunk.text:
            yield chunk.text


# ---------------------------------------------------------------------------
# Provider: Ollama (local, no auth)
# ---------------------------------------------------------------------------

def _stream_ollama(prompt: str, host: str, model: str):
    url = f'http://{host}:11434/api/generate'
    payload = json.dumps({'model': model, 'prompt': prompt, 'stream': True}).encode()
    req = urllib.request.Request(
        url, data=payload, method='POST',
        headers={'Content-Type': 'application/json'},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        for line in resp:
            if line.strip():
                data = json.loads(line.decode())
                if 'response' in data and data['response']:
                    yield data['response']


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def gerar_relatorio_stream(tipo: str, ctx: dict):
    """Yield text chunks from the best available provider."""
    prompt = _montar_prompt(tipo, ctx)

    # --- Groq (primary) ---
    groq_model = os.getenv('GROQ_MODEL', 'llama-3.3-70b-versatile')
    for i in range(1, 4):
        key = os.getenv(f'GROQ_KEY_{i}')
        if not key:
            continue
        try:
            yield from _stream_groq(prompt, key, groq_model)
            return
        except Exception as exc:
            logger.warning('Groq key %d falhou: %s', i, exc)

    # --- Gemini (secondary) ---
    gemini_model = os.getenv('GEMINI_MODEL', 'gemini-2.0-flash')
    for i in range(1, 4):
        key = os.getenv(f'GEMINI_KEY_{i}')
        if not key:
            continue
        try:
            yield from _stream_gemini(prompt, key, gemini_model)
            return
        except Exception as exc:
            logger.warning('Gemini key %d falhou: %s', i, exc)

    # --- Ollama (local fallback) ---
    ollama_host = os.getenv('OLLAMA_HOST', 'host.docker.internal')
    ollama_model = os.getenv('OLLAMA_MODEL', 'llama3.2')
    try:
        yield from _stream_ollama(prompt, ollama_host, ollama_model)
        return
    except Exception as exc:
        logger.error('Ollama falhou: %s', exc)

    raise RuntimeError('Nenhum provider LLM disponível. Verifique as chaves no .env.')
