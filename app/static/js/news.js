function analisarImpacto(noticiaId) {
  const btn     = document.getElementById('btn-impacto-' + noticiaId);
  const output  = document.getElementById('output-impacto-' + noticiaId);
  const loadEl  = document.getElementById('loading-impacto-' + noticiaId);
  const areaEl  = document.getElementById('impacto-area-' + noticiaId);

  if (!output) return;
  if (btn) btn.disabled = true;
  if (loadEl) loadEl.style.display = 'block';
  if (areaEl) areaEl.style.display = 'block';
  output.textContent = '';
  output.classList.remove('report-error');

  const src = new EventSource('/noticias/' + noticiaId + '/impacto');

  src.onmessage = function (e) {
    const data = JSON.parse(e.data);
    if (data.chunk) output.textContent += data.chunk;
    if (data.texto) output.textContent = data.texto;
    if (data.done) {
      src.close();
      if (loadEl) loadEl.style.display = 'none';
      if (btn) {
        btn.textContent = '✅ Processado';
        btn.disabled = true;
      }
    }
    if (data.error) {
      src.close();
      if (loadEl) loadEl.style.display = 'none';
      output.textContent = 'Erro: ' + data.error;
      output.classList.add('report-error');
      if (btn) btn.disabled = false;
    }
  };

  src.onerror = function () {
    src.close();
    if (loadEl) loadEl.style.display = 'none';
    if (output.textContent === '') {
      output.textContent = 'Falha na conexão. Tente novamente.';
      output.classList.add('report-error');
    }
    if (btn) btn.disabled = false;
  };
}
