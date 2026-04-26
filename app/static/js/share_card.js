function _roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + r);
  ctx.lineTo(x + w, y + h - r);
  ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  ctx.lineTo(x + r, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - r);
  ctx.lineTo(x, y + r);
  ctx.quadraticCurveTo(x, y, x + r, y);
  ctx.closePath();
}

function _avatar(ctx, x, y, r, color, initials) {
  ctx.beginPath();
  ctx.arc(x, y, r, 0, Math.PI * 2);
  ctx.fillStyle = color;
  ctx.fill();
  ctx.strokeStyle = 'rgba(255,255,255,0.25)';
  ctx.lineWidth = 2;
  ctx.stroke();
  ctx.fillStyle = '#fff';
  ctx.font = `bold ${Math.round(r * 0.55)}px Arial`;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(initials, x, y + 1);
  ctx.textBaseline = 'alphabetic';
}

function compartilharCard() {
  const d = window.MATCH_DATA;
  if (!d) return;

  const W = 680, H = 340;
  const canvas = document.createElement('canvas');
  canvas.width = W; canvas.height = H;
  const ctx = canvas.getContext('2d');

  // Background gradient
  const bg = ctx.createLinearGradient(0, 0, W, H);
  bg.addColorStop(0, '#1a472a');
  bg.addColorStop(1, '#0d2318');
  _roundRect(ctx, 0, 0, W, H, 14);
  ctx.fillStyle = bg;
  ctx.fill();

  // Subtle grid overlay
  ctx.strokeStyle = 'rgba(255,255,255,0.04)';
  ctx.lineWidth = 1;
  for (let x = 0; x < W; x += 24) {
    ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke();
  }

  // Top divider
  ctx.strokeStyle = 'rgba(255,255,255,0.12)';
  ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(24, 56); ctx.lineTo(W - 24, 56); ctx.stroke();

  // Brand
  ctx.fillStyle = '#52b788';
  ctx.font = 'bold 16px Arial';
  ctx.textAlign = 'left';
  ctx.fillText('FutMetricX', 24, 36);

  // Competition pill
  ctx.fillStyle = 'rgba(255,255,255,0.12)';
  _roundRect(ctx, W - 220, 18, 196, 28, 6);
  ctx.fill();
  ctx.fillStyle = 'rgba(255,255,255,0.75)';
  ctx.font = '11px Arial';
  ctx.textAlign = 'right';
  ctx.fillText(d.competicao.toUpperCase() + (d.temporada ? '  ' + d.temporada : ''), W - 28, 37);

  // Team avatars
  _avatar(ctx, 160, 160, 48, d.cor_casa,      d.ini_casa);
  _avatar(ctx, W - 160, 160, 48, d.cor_visitante, d.ini_visitante);

  // Team names
  ctx.fillStyle = '#fff';
  ctx.font = 'bold 20px Arial';
  ctx.textAlign = 'center';
  ctx.fillText(d.time_casa,       160, 230);
  ctx.fillText(d.time_visitante,  W - 160, 230);

  // Score / VS
  ctx.textAlign = 'center';
  if (d.status === 'encerrada' && d.placar_casa !== null && d.placar_visitante !== null) {
    ctx.fillStyle = '#f4a261';
    ctx.font = 'bold 58px Arial';
    ctx.fillText(`${d.placar_casa}  –  ${d.placar_visitante}`, W / 2, 190);
  } else {
    ctx.fillStyle = 'rgba(255,255,255,0.35)';
    ctx.font = 'bold 30px Arial';
    ctx.fillText('vs', W / 2, 180);
  }

  // Bottom divider
  ctx.strokeStyle = 'rgba(255,255,255,0.12)';
  ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(24, 260); ctx.lineTo(W - 24, 260); ctx.stroke();

  // Date + round
  const meta = [d.data_str, d.rodada ? 'Rodada ' + d.rodada : ''].filter(Boolean).join(' · ');
  ctx.fillStyle = 'rgba(255,255,255,0.45)';
  ctx.font = '13px Arial';
  ctx.textAlign = 'center';
  ctx.fillText(meta, W / 2, 296);

  // Download
  canvas.toBlob(blob => {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${d.time_casa.replace(/ /g, '_')}_vs_${d.time_visitante.replace(/ /g, '_')}.png`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, 'image/png');
}
