/* Toggle Torcedor / Profissional */
document.querySelectorAll('.btn-modo').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.btn-modo').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    document.querySelectorAll('.modo-content').forEach(c => c.style.display = 'none');
    const target = document.getElementById('content-' + btn.dataset.modo);
    if (target) target.style.display = 'block';
  });
});

/* SSE streaming — player profile */
function gerarPerfil(jogadorId) {
  const outputEl = document.getElementById('output-perfil_jogador');
  const btnEl    = document.getElementById('btn-gerar-perfil_jogador');
  const loadWrap = document.getElementById('loading-perfil_jogador');

  if (!outputEl) return;
  if (btnEl) btnEl.disabled = true;
  if (loadWrap) loadWrap.style.display = 'block';
  outputEl.textContent = '';
  outputEl.classList.remove('report-error');

  const src = new EventSource('/jogador/' + jogadorId + '/gerar');

  src.onmessage = function (e) {
    const data = JSON.parse(e.data);
    if (data.chunk) outputEl.textContent += data.chunk;
    if (data.texto) outputEl.textContent = data.texto;
    if (data.done) {
      src.close();
      if (loadWrap) loadWrap.style.display = 'none';
      if (btnEl) btnEl.style.display = 'none';
    }
    if (data.error) {
      src.close();
      if (loadWrap) loadWrap.style.display = 'none';
      outputEl.textContent = 'Erro: ' + data.error;
      outputEl.classList.add('report-error');
      if (btnEl) btnEl.disabled = false;
    }
  };

  src.onerror = function () {
    src.close();
    if (loadWrap) loadWrap.style.display = 'none';
    if (outputEl.textContent === '') {
      outputEl.textContent = 'Falha na conexão. Tente novamente.';
      outputEl.classList.add('report-error');
    }
    if (btnEl) btnEl.disabled = false;
  };
}

/* SSE streaming */
function gerarRelatorio(partidaId, tipo) {
  const outputEl  = document.getElementById('output-' + tipo);
  const btnEl     = document.getElementById('btn-gerar-' + tipo);
  const loadWrap  = document.getElementById('loading-' + tipo);

  if (!outputEl) return;

  if (btnEl) btnEl.disabled = true;
  if (loadWrap) loadWrap.style.display = 'block';
  outputEl.textContent = '';
  outputEl.classList.remove('report-error');

  const src = new EventSource('/partida/' + partidaId + '/gerar?tipo=' + tipo);

  src.onmessage = function (e) {
    const data = JSON.parse(e.data);

    if (data.chunk) {
      outputEl.textContent += data.chunk;
    }

    if (data.texto) {
      // cached report — render all at once
      outputEl.textContent = data.texto;
    }

    if (data.done) {
      src.close();
      if (loadWrap) loadWrap.style.display = 'none';
      if (btnEl) btnEl.style.display = 'none';
    }

    if (data.error) {
      src.close();
      if (loadWrap) loadWrap.style.display = 'none';
      outputEl.textContent = 'Erro: ' + data.error;
      outputEl.classList.add('report-error');
      if (btnEl) btnEl.disabled = false;
    }
  };

  src.onerror = function () {
    src.close();
    if (loadWrap) loadWrap.style.display = 'none';
    if (outputEl.textContent === '') {
      outputEl.textContent = 'Falha na conexão. Tente novamente.';
      outputEl.classList.add('report-error');
    }
    if (btnEl) btnEl.disabled = false;
  };
}
