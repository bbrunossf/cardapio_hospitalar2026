/* Posso Comer? — módulo de consequências de alimento fora do cardápio
 * (plano: docs/posso_comer.md). Página fixa com scroll vertical; não é chat. */
(function () {
  'use strict';

  let fotoB64 = null;
  let fotoMime = null;
  let fotoURL = null;

  const $ = id => document.getElementById(id);

  function esc(s) {
    return String(s ?? '').replace(/&/g, '&amp;').replace(/"/g, '&quot;')
      .replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  function fmt(v) {
    return (v == null || isNaN(v)) ? '—' : Number(v).toFixed(0);
  }

  /* ---------------- pacientes e contexto ---------------- */
  async function carregarPacientes() {
    try {
      const resp = await fetch('/api/pacientes');
      if (!resp.ok) throw new Error('HTTP ' + resp.status);
      const lista = await resp.json();
      const sel = $('selPaciente');
      sel.innerHTML = '<option value="">Selecione...</option>' +
        lista.map(p => `<option value="${p.id}">${esc(p.nome)}</option>`).join('');
      if (lista.length === 1) { sel.value = lista[0].id; carregarContexto(); }
    } catch (e) {
      $('selPaciente').innerHTML = '<option value="">Erro ao carregar pacientes</option>';
    }
  }

  async function carregarContexto() {
    const pid = $('selPaciente').value;
    const card = $('ctxCard');
    if (!pid) { card.textContent = 'Selecione um paciente'; return; }
    try {
      const resp = await fetch(`/api/posso-comer/contexto/${pid}`);
      const ctx = await resp.json();
      const fonte = ctx.fonte === 'cardapio' ? 'cardápio' : ctx.fonte === 'plano' ? 'plano' : 'sem cardápio';
      card.innerHTML = `Dia de referência: <b>${fmt(ctx.kcal_dia)} kcal</b>` +
        (ctx.sodio_mg_dia != null ? ` · <b>${fmt(ctx.sodio_mg_dia)} mg</b> sódio` : '') +
        ` <span style="opacity:.7">(${fonte})</span>`;
    } catch (e) {
      card.textContent = 'Contexto indisponível';
    }
  }

  /* ---------------- entrada ---------------- */
  function lerFoto(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        const b64 = reader.result.split(',')[1];
        resolve({ b64, mime: file.type || 'image/jpeg' });
      };
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  }

  $('fileFoto').addEventListener('change', async (e) => {
    const f = e.target.files[0];
    if (!f) { fotoB64 = null; fotoMime = null; return; }
    try {
      const { b64, mime } = await lerFoto(f);
      fotoB64 = b64;
      fotoMime = mime;
      if (fotoURL) URL.revokeObjectURL(fotoURL);
      fotoURL = URL.createObjectURL(f);
      $('msgErro').textContent = 'Foto anexada (' + f.name + ') — clique em "Ver impacto".';
    } catch (err) {
      $('msgErro').textContent = 'Não foi possível ler a foto: ' + err.message;
    }
  });

  async function consultar(payload) {
    $('msgErro').textContent = '';
    $('resultado').innerHTML = '<div class="carregando">Consultando...</div>';
    try {
      const resp = await fetch('/api/posso-comer/consultar', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.erro || 'HTTP ' + resp.status);
      renderizar(data);
    } catch (e) {
      $('resultado').innerHTML = '';
      $('msgErro').textContent = 'Erro: ' + e.message;
    }
  }

  $('btnConsultar').addEventListener('click', () => {
    const pid = $('selPaciente').value;
    if (!pid) { $('msgErro').textContent = 'Selecione um paciente primeiro.'; return; }
    const texto = $('txtAlimento').value.trim();
    const porcao = $('txtPorcao').value.trim();
    if (!texto && !fotoB64) { $('msgErro').textContent = 'Digite o nome do alimento ou anexe uma foto.'; return; }
    const payload = { paciente_id: Number(pid) };
    if (porcao) payload.porcao_g = Number(porcao);
    if (fotoB64) { payload.imagem_base64 = fotoB64; payload.mime = fotoMime; }
    else payload.texto = texto;
    consultar(payload);
  });

  /* ---------------- render ---------------- */
  function renderizar(d) {
    const zona = $('resultado');
    if (d.ambiguo) { renderCandidatos(zona, d); return; }
    if (d.precisa_descricao) { renderDescricao(zona, d); return; }
    renderResultado(zona, d);
  }

  function renderCandidatos(zona, d) {
    const pid = $('selPaciente').value;
    let h = '<div class="card"><h3>Encontrei vários alimentos — escolha um</h3>';
    for (const c of d.candidatos) {
      h += `<div class="candidato" data-tipo="${c.tipo}" data-id="${c.id}">
        <div><b>${esc(c.nome)}</b><div class="k">${c.tipo} · ${fmt(c.kcal_100g)} kcal/100g · ${fmt(c.sodio_mg_100g)} mg sódio/100g</div></div>
        <span>escolher &rarr;</span></div>`;
    }
    h += `<div class="candidato" id="nenhumDesses">
        <div><b>Nenhum desses</b><div class="k">Descrever o alimento para estimar os valores</div></div>
        <span>descrever &rarr;</span></div>`;
    h += '</div>';
    zona.innerHTML = h;
    for (const el of zona.querySelectorAll('.candidato[data-id]')) {
      el.addEventListener('click', () => {
        consultar({
          paciente_id: Number(pid),
          candidato_tipo: el.dataset.tipo,
          candidato_id: Number(el.dataset.id),
          porcao_g: Number($('txtPorcao').value) || 100,
        });
      });
    }
    $('nenhumDesses').addEventListener('click', () => {
      renderDescricao(zona, { nome_sugerido: d.nome_sugerido || '' });
    });
  }

  function renderDescricao(zona, d) {
    const pid = $('selPaciente').value;
    zona.innerHTML = `<div class="card">
      <h3>Não encontrei "${esc(d.nome_sugerido || '')}" no cadastro</h3>
      <p class="mensagem">Descreva o alimento para eu estimar os valores (kcal e sódio):</p>
      <div style="display:flex;gap:10px;margin-top:10px;flex-wrap:wrap">
        <input type="text" id="txtDescricao" style="flex:1;min-width:220px;padding:8px 10px;border:1px solid var(--border);border-radius:6px;font-family:var(--font)"
               placeholder="Ex.: bolo de chocolate com cobertura de brigadeiro"
               value="${esc(d.nome_sugerido || '')}">
        <button class="btn btn-primary" id="btnEstimar">Estimar valores</button>
      </div>
    </div>`;
    $('btnEstimar').addEventListener('click', () => {
      const desc = $('txtDescricao').value.trim();
      if (!desc) return;
      consultar({
        paciente_id: Number(pid),
        modo: 'estimar',
        descricao: desc,
        porcao_g: Number($('txtPorcao').value) || 100,
      });
    });
  }

  function renderResultado(zona, d) {
    const a = d.alimento;
    const imp = d.impacto;
    const ctx = d.contexto;

    const rotulos = { verde: 'Liberado', amarelo: 'Moderação', vermelho: 'Evitar' };
    const semClasse = imp.semafaro ? `semaforo ${imp.semafaro}` : 'semaforo sem';
    const rotulo = imp.semafaro ? rotulos[imp.semafaro] : 'Sem referência';

    const imagem = fotoURL
      ? `<img src="${fotoURL}" alt="${esc(a.nome)}">`
      : '<div class="placeholder">&#127869;</div>';

    const estimado = a.estimado
      ? '<span class="badge-estimado">ESTIMADO</span>' : '';

    // tabela
    let tab = `<table class="nutri">
      <tr><th></th><th>Este alimento</th><th>Total do dia</th><th>Com o alimento</th></tr>
      <tr><td>Energia</td><td><b>${fmt(a.kcal_porcao)} kcal</b></td>
          <td>${fmt(ctx.kcal_dia)} kcal</td>
          <td>${fmt((ctx.kcal_dia ?? 0) + a.kcal_porcao)} kcal${imp.kcal_pct != null ? ` <span style="color:var(--text2)">(+${imp.kcal_pct}%)</span>` : ''}</td></tr>`;
    if (ctx.sodio_mg_dia != null) {
      tab += `<tr><td>Sódio</td><td><b>${fmt(a.sodio_mg_porcao)} mg</b></td>
          <td>${fmt(ctx.sodio_mg_dia)} mg</td>
          <td>${fmt(ctx.sodio_mg_dia + a.sodio_mg_porcao)} mg${imp.sodio_pct != null ? ` <span style="color:var(--text2)">(+${imp.sodio_pct}%)</span>` : ''}</td></tr>`;
    }
    tab += '</table>';

    // gráfico (barras CSS)
    const maxKcal = Math.max(1, (ctx.kcal_dia ?? 0) + a.kcal_porcao);
    const wDia = ctx.kcal_dia != null ? Math.max(2, (ctx.kcal_dia / maxKcal) * 100) : 0;
    const wTotal = Math.max(2, ((ctx.kcal_dia ?? 0) + a.kcal_porcao) / maxKcal * 100);
    const corSem = imp.semafaro === 'verde' ? '#1e8449' : imp.semafaro === 'amarelo' ? '#b7950b' : '#c0392b';
    const grafico = ctx.kcal_dia != null ? `<div class="grafico">
      <div class="barra-linha"><span class="rot">Cardápio do dia</span>
        <div class="pista"><div class="fill" style="width:${wDia}%;background:#2e86c1"></div></div>
        <span class="val">${fmt(ctx.kcal_dia)} kcal</span></div>
      <div class="barra-linha"><span class="rot">Com o alimento</span>
        <div class="pista"><div class="fill" style="width:${wTotal}%;background:${corSem}"></div></div>
        <span class="val">${fmt((ctx.kcal_dia ?? 0) + a.kcal_porcao)} kcal (+${imp.kcal_pct ?? 0}%)</span></div>
    </div>` : '';

    const alternativas = imp.alternativas && imp.alternativas.length
      ? `<div class="card"><h3>Alternativas com menos energia</h3><ul class="alternativas">
          ${imp.alternativas.map(x => `<li><b>${esc(x.nome)}</b> — ${fmt(x.kcal_100g)} kcal/100g</li>`).join('')}
        </ul></div>` : '';

    const estimadoAviso = a.estimado
      ? '<p class="aviso-estimado">Valores estimados pelo sistema — o alimento não está cadastrado.</p>' : '';

    zona.innerHTML = `
      <div class="${semClasse}">
        <div class="bola"></div>
        <div>
          <div class="rotulo">${rotulo}</div>
          <div class="pct">${imp.mensagem ? esc(imp.mensagem) : 'Paciente sem cardápio estabelecido — valores informativos.'}</div>
        </div>
      </div>
      <div class="card">
        <div class="alimento-topo">
          ${imagem}
          <div>
            <div class="alimento-nome">${esc(a.nome)}${estimado}</div>
            <div class="alimento-sub">Porção: ${fmt(a.porcao_g)} g</div>
          </div>
        </div>
        ${tab}
        ${grafico}
      </div>
      ${estimadoAviso}
      ${alternativas}`;
  }

  /* ---------------- init ---------------- */
  $('selPaciente').addEventListener('change', carregarContexto);
  document.addEventListener('DOMContentLoaded', carregarPacientes);
})();
