/* Registro Alimentar 48h — consumo do paciente antes do plano
 * (plano: docs/registro_alimentar_48h.md).
 * Fluxo novo: processar (dry-run) -> revisar ambíguos/quantidades -> confirmar.
 * Fluxo salvo: lista por paciente + detalhe com correção de itens (recálculo
 * no servidor) e exclusão soft. */
(function () {
  'use strict';

  const $ = id => document.getElementById(id);

  let itensAtuais = [];   // resposta do /processar (mesma ordem do /confirmar)
  let registroSalvo = false;
  let detalheAberto = null;  // registro_id com detalhe aberto

  const ROTULO_REFEICAO = {
    cafe_da_manha: 'Café da manhã', colacao: 'Colação', almoco: 'Almoço',
    lanche: 'Lanche', jantar: 'Jantar', ceia: 'Ceia', outro: 'Outro',
  };
  const ROTULO_ORIGEM = {
    prato: 'Prato', industrializado: 'Industrializado',
    ingrediente: 'Ingrediente', estimado: 'Estimado',
  };
  const ROTULO_NUTRI = {
    energia_kcal: 'Energia (kcal)', carboidratos_g: 'Carboidratos (g)',
    proteinas_g: 'Proteínas (g)', gorduras_totais_g: 'Gorduras (g)',
    fibras_g: 'Fibras (g)', sodio_mg: 'Sódio (mg)', calcio_mg: 'Cálcio (mg)',
    ferro_mg: 'Ferro (mg)', potassio_mg: 'Potássio (mg)',
    fosforo_mg: 'Fósforo (mg)', vit_c_mg: 'Vit. C (mg)',
  };
  const TOTAIS_DIA = ['energia_kcal', 'carboidratos_g', 'proteinas_g',
    'gorduras_totais_g', 'fibras_g', 'sodio_mg', 'calcio_mg', 'ferro_mg',
    'potassio_mg', 'fosforo_mg', 'vit_c_mg'];

  function esc(s) {
    return String(s ?? '').replace(/&/g, '&amp;').replace(/"/g, '&quot;')
      .replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  function fmt(v) {
    return (v == null || isNaN(v)) ? '—' : Number(v).toFixed(0);
  }

  function badgeStatus(st) {
    return `<span class="badge-status ${esc(st)}">${esc(st)}</span>`;
  }

  /* ---------------- pacientes ---------------- */
  async function carregarPacientes() {
    try {
      const resp = await fetch('/api/pacientes');
      if (!resp.ok) throw new Error('HTTP ' + resp.status);
      const lista = await resp.json();
      const sel = $('selPaciente');
      sel.innerHTML = '<option value="">Selecione...</option>' +
        lista.map(p => `<option value="${p.id}">${esc(p.nome)}</option>`).join('');
      if (lista.length === 1) { sel.value = lista[0].id; carregarRegistros(); }
    } catch (e) {
      $('selPaciente').innerHTML = '<option value="">Erro ao carregar pacientes</option>';
    }
  }

  /* ================= registros salvos (lista) ================= */
  async function carregarRegistros() {
    const pid = $('selPaciente').value;
    const zona = $('regsSalvos');
    if (!pid) { zona.innerHTML = ''; return; }
    zona.innerHTML = '<div class="carregando">Carregando registros salvos...</div>';
    try {
      const resp = await fetch(`/api/registro-alimentar?paciente_id=${pid}`);
      if (!resp.ok) throw new Error('HTTP ' + resp.status);
      const lista = await resp.json();
      renderLista(zona, lista);
    } catch (e) {
      zona.innerHTML = `<div class="sem-registros">Erro ao carregar registros: ${esc(e.message)}</div>`;
    }
  }

  function renderLista(zona, lista) {
    if (!lista.length) {
      zona.innerHTML = '<div class="sem-registros">Nenhum registro salvo para este paciente.</div>';
      return;
    }
    let h = '<div class="card"><h3>Registros salvos</h3>';
    for (const r of lista) {
      h += `<div class="reg-linha">
        <b>#${r.id}</b> ${esc(r.data_inicio || '?')} a ${esc(r.data_fim || '?')}
        ${badgeStatus(r.status)}
        <span class="k">${r.n_itens} itens · d1: ${fmt(r.kcal_dia1)} kcal · d2: ${fmt(r.kcal_dia2)} kcal</span>
        <span class="k">por ${esc(r.criado_por_nome || '—')}</span>
        <span class="espaco">
          <button class="btn-mini" data-ver="${r.id}">Ver</button>
          <button class="btn-mini perigo" data-excluir="${r.id}">Excluir</button>
        </span></div>`;
    }
    h += '</div>';
    zona.innerHTML = h;
    zona.querySelectorAll('[data-ver]').forEach(b =>
      b.addEventListener('click', () => verRegistro(Number(b.dataset.ver))));
    zona.querySelectorAll('[data-excluir]').forEach(b =>
      b.addEventListener('click', () => excluirRegistro(Number(b.dataset.excluir))));
  }

  /* ================= detalhe ================= */
  async function verRegistro(id) {
    const zona = $('detalhe');
    zona.innerHTML = '<div class="carregando">Carregando registro...</div>';
    try {
      const resp = await fetch(`/api/registro-alimentar/${id}`);
      if (!resp.ok) throw new Error('HTTP ' + resp.status);
      const d = await resp.json();
      detalheAberto = id;
      renderDetalhe(zona, d);
    } catch (e) {
      zona.innerHTML = `<div class="sem-registros">Erro: ${esc(e.message)}</div>`;
    }
  }

  function renderDetalhe(zona, d) {
    let h = `<div class="card"><h3>Registro #${d.registro_id}</h3>
      <div class="detalhe-topo">
        <span>Status:
          <select id="selStatus">
            <option value="rascunho"${d.status === 'rascunho' ? ' selected' : ''}>rascunho</option>
            <option value="processado"${d.status === 'processado' ? ' selected' : ''}>processado</option>
            <option value="revisado"${d.status === 'revisado' ? ' selected' : ''}>revisado</option>
          </select>
          <button class="btn-mini" id="btnStatus">Salvar status</button></span>
        <span class="k">${esc(d.data_inicio || '?')} a ${esc(d.data_fim || '?')} ·
          criado por #${d.criado_por ?? '—'} em ${esc(d.criado_em || '?')}</span>
      </div>
      <details><summary class="k">Relato original</summary>
        <div class="obs" style="white-space:pre-wrap">${esc(d.texto_original || '')}</div></details>
      <table class="totais"><tr>`;
    for (const dia of d.totais_por_dia) {
      h += `<td style="vertical-align:top;padding-right:24px"><b>Dia ${dia.dia}</b> (${dia.itens} itens)<table>`;
      for (const k of TOTAIS_DIA) {
        const v = dia.nutrientes[k];
        h += `<tr><td>${ROTULO_NUTRI[k]}</td><td>${v != null ? fmt(v) : '<span class="nao-info">não informado</span>'}</td></tr>`;
      }
      h += '</table></td>';
    }
    h += '</tr></table>';
    h += '<table class="itens" style="margin-top:10px"><tr><th>Dia</th><th>Refeição</th>' +
      '<th>Descrição</th><th>Qtd (g)</th><th>Origem</th><th>kcal</th><th>Ações</th></tr>';
    for (const it of d.itens) {
      const badgeEstimado = it.estimado ? '<span class="badge badge-estimado">ESTIMADO</span>' : '';
      h += `<tr data-item="${it.id}">
        <td>${it.dia}</td><td>${ROTULO_REFEICAO[it.refeicao] || it.refeicao}</td>
        <td>${esc(it.descricao)}${it.observacao ? `<div class="obs">${esc(it.observacao)}</div>` : ''}</td>
        <td class="num"><input class="ed-qtd" type="number" min="1" step="1"
          value="${it.quantidade_g != null ? fmt(it.quantidade_g) : ''}" placeholder="—">
          <button class="btn-mini" data-salvar-item="${it.id}">Salvar</button></td>
        <td>${ROTULO_ORIGEM[it.origem] || it.origem}${badgeEstimado}</td>
        <td class="num" data-kcal>${fmt(it.nutrientes.energia_kcal)}</td>
        <td><button class="btn-mini perigo" data-excluir-item="${it.id}">Excluir item</button></td></tr>`;
    }
    h += '</table></div>';
    zona.innerHTML = h;

    $('btnStatus').addEventListener('click', () => salvarStatus(d.registro_id));
    zona.querySelectorAll('[data-salvar-item]').forEach(b =>
      b.addEventListener('click', () => corrigirItem(Number(b.dataset.salvarItem))));
    zona.querySelectorAll('[data-excluir-item]').forEach(b =>
      b.addEventListener('click', () => excluirItem(Number(b.dataset.excluirItem))));
  }

  async function salvarStatus(id) {
    try {
      const resp = await fetch(`/api/registro-alimentar/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: $('selStatus').value }),
      });
      const j = await resp.json();
      if (!resp.ok) throw new Error(j.erro || 'HTTP ' + resp.status);
      carregarRegistros();  // atualiza o badge na lista
    } catch (e) {
      $('msgErro').textContent = 'Erro ao salvar status: ' + e.message;
    }
  }

  async function corrigirItem(itemId) {
    const input = document.querySelector(`tr[data-item="${itemId}"] .ed-qtd`);
    const qg = parseFloat(input.value);
    if (isNaN(qg) || qg <= 0) { $('msgErro').textContent = 'Informe a quantidade em gramas (valor > 0).'; return; }
    try {
      const resp = await fetch(`/api/registro-alimentar/itens/${itemId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ quantidade_g: qg }),
      });
      const j = await resp.json();
      if (!resp.ok) throw new Error(j.erro || 'HTTP ' + resp.status);
      // atualiza kcal na linha e recarrega o detalhe (totais + status revisado)
      const tr = document.querySelector(`tr[data-item="${itemId}"]`);
      const kcal = j.nutrientes ? fmt(j.nutrientes.energia_kcal) : '—';
      tr.querySelector('[data-kcal]').textContent = kcal;
      if (detalheAberto) verRegistro(detalheAberto);
      carregarRegistros();
    } catch (e) {
      $('msgErro').textContent = 'Erro ao corrigir item: ' + e.message;
    }
  }

  async function excluirRegistro(id) {
    if (!confirm(`Excluir o registro #${id}? (exclusão suave — some da lista, auditoria preservada)`)) return;
    try {
      const resp = await fetch(`/api/registro-alimentar/${id}`, { method: 'DELETE' });
      const j = await resp.json();
      if (!resp.ok) throw new Error(j.erro || 'HTTP ' + resp.status);
      if (detalheAberto === id) { $('detalhe').innerHTML = ''; detalheAberto = null; }
      carregarRegistros();
    } catch (e) {
      $('msgErro').textContent = 'Erro ao excluir: ' + e.message;
    }
  }

  async function excluirItem(itemId) {
    if (!confirm('Excluir este item? (exclusão suave)')) return;
    try {
      const resp = await fetch(`/api/registro-alimentar/itens/${itemId}`, { method: 'DELETE' });
      const j = await resp.json();
      if (!resp.ok) throw new Error(j.erro || 'HTTP ' + resp.status);
      if (detalheAberto) verRegistro(detalheAberto);
      carregarRegistros();
    } catch (e) {
      $('msgErro').textContent = 'Erro ao excluir item: ' + e.message;
    }
  }

  /* ================= processar (dry-run) ================= */
  async function processar() {
    const pid = $('selPaciente').value;
    const texto = $('txtRelato').value.trim();
    $('msgErro').textContent = '';
    $('alertas').innerHTML = '';
    if (!pid) { $('msgErro').textContent = 'Selecione um paciente primeiro.'; return; }
    if (!texto) { $('msgErro').textContent = 'Cole o relato de 48h do paciente.'; return; }

    $('resultado').innerHTML = '<div class="carregando">Estruturando e buscando no cadastro...</div>';
    registroSalvo = false;
    try {
      const resp = await fetch('/api/registro-alimentar/processar', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ paciente_id: Number(pid), texto }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.erro || 'HTTP ' + resp.status);
      itensAtuais = data.itens || [];
      renderAlertas(data.alertas || []);
      renderTotais(data.totais_por_dia || []);
      renderItens(itensAtuais);
    } catch (e) {
      $('resultado').innerHTML = '';
      $('msgErro').textContent = 'Erro: ' + e.message;
    }
  }
  $('btnProcessar').addEventListener('click', processar);

  function renderAlertas(alertas) {
    $('alertas').innerHTML = alertas.map(a =>
      `<div class="alerta">${esc(a)}</div>`).join('');
  }

  /* ---------------- totais por dia ---------------- */
  function renderTotais(totais) {
    const zona = $('resultado');
    if (!totais.length) return;
    let h = '<div class="card"><h3>Totais consumidos</h3><div class="totais">';
    for (const dia of totais) {
      h += `<div class="dia-card"><b>Dia ${dia.dia}</b> (${dia.itens} itens)<table>`;
      for (const k of TOTAIS_DIA) {
        const v = dia.nutrientes[k];
        h += `<tr><td>${ROTULO_NUTRI[k]}</td><td>${v != null ? fmt(v) : '<span class="nao-info">não informado</span>'}</td></tr>`;
      }
      h += '</table></div>';
    }
    h += '</div></div>';
    zona.innerHTML = h;
  }

  /* ---------------- itens ---------------- */
  function renderItens(itens) {
    const zona = $('resultado');
    if (!itens.length) {
      zona.innerHTML += '<div class="card">Nenhum item identificado — revise o relato.</div>';
      return;
    }
    let h = '<div class="card"><h3>Itens identificados</h3><table class="itens">' +
      '<tr><th>Dia</th><th>Refeição</th><th>Descrição</th><th>Qtd</th>' +
      '<th>Origem</th><th>kcal</th><th>Revisar / escolher</th></tr>';
    itens.forEach((it, i) => {
      const badgeOrigem = it.origem
        ? `<span class="badge badge-origem">${ROTULO_ORIGEM[it.origem] || it.origem}</span>` : '';
      const badgeEstimado = it.estimado ? '<span class="badge badge-estimado">ESTIMADO</span>' : '';
      const badgeRevisar = it.revisar ? '<span class="badge badge-revisar">revisar</span>' : '';
      const kcal = it.nutrientes ? fmt(it.nutrientes.energia_kcal) : '—';
      const obs = it.observacao ? `<div class="obs">${esc(it.observacao)}</div>` : '';
      const fonte = it.nome_encontrado ? `<div class="fonte">${esc(it.nome_encontrado)}</div>` : '';
      h += `<tr class="${it.revisar ? 'revisar' : ''}" data-idx="${i}">` +
        `<td>${it.dia}</td><td>${ROTULO_REFEICAO[it.refeicao] || it.refeicao}</td>` +
        `<td>${esc(it.descricao)}${fonte}</td>` +
        `<td class="num">${it.quantidade_texto ? esc(it.quantidade_texto) + ' · ' : ''}${it.quantidade_g != null ? fmt(it.quantidade_g) + ' g' : '—'}</td>` +
        `<td>${badgeOrigem}${badgeEstimado}${badgeRevisar}</td>` +
        `<td class="num">${kcal}</td>` +
        `<td>${acaoRevisao(it, i)}</td></tr>` + obs;
    });
    h += '</table>';
    if (itens.some(it => it.revisar)) {
      h += '<div class="obs" style="margin-top:8px">Itens em amarelo precisam de revisão: ' +
        'escolha o alimento na lista ou informe as gramas antes de salvar.</div>';
    }
    h += `<div class="acoes">
      <button class="btn btn-primary" id="btnConfirmar">Confirmar e salvar</button>
      <span id="msgOk"></span></div></div>`;
    zona.innerHTML += h;
    $('btnConfirmar').addEventListener('click', confirmar);
  }

  function acaoRevisao(it, i) {
    if (it.ambiguo && it.candidatos && it.candidatos.length) {
      let opts = '<option value="">— estimar (não cadastrado)</option>';
      for (const c of it.candidatos) {
        opts += `<option value="${c.tipo}|${c.id}">${esc(c.nome)}${c.kcal_100g != null ? ` (${fmt(c.kcal_100g)} kcal/100g)` : ''}</option>`;
      }
      return `<select data-cand="${i}">${opts}</select>`;
    }
    if (it.origem == null) {
      return '<span class="obs">Não encontrado — será <b>estimado</b> ao salvar</span>' +
        (it.quantidade_g == null ? '<br><input type="number" min="1" data-gramas="' + i + '" placeholder="gramas">' : '');
    }
    if (it.quantidade_g == null) {
      return '<input type="number" min="1" data-gramas="' + i + '" placeholder="gramas">';
    }
    return '';
  }

  /* ---------------- confirmar (grava) ---------------- */
  async function confirmar() {
    if (registroSalvo) return;
    const pid = $('selPaciente').value;
    const texto = $('txtRelato').value.trim();
    $('msgOk').textContent = '';

    const itens = itensAtuais.map(it => ({
      dia: it.dia, refeicao: it.refeicao, descricao: it.descricao,
      valor: it.valor, unidade: it.unidade, quantidade_texto: it.quantidade_texto,
    }));
    for (const el of document.querySelectorAll('[data-cand]')) {
      const v = el.value;
      if (v) {
        const [tipo, id] = v.split('|');
        itens[Number(el.dataset.cand)].candidato_tipo = tipo;
        itens[Number(el.dataset.cand)].candidato_id = Number(id);
      }
    }
    for (const el of document.querySelectorAll('[data-gramas]')) {
      const v = parseFloat(el.value);
      if (!isNaN(v) && v > 0) {
        itens[Number(el.dataset.gramas)].quantidade_g = v;
      }
    }

    $('msgOk').textContent = 'Salvando...';
    try {
      const resp = await fetch('/api/registro-alimentar/confirmar', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ paciente_id: Number(pid), texto, itens }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.erro || 'HTTP ' + resp.status);
      registroSalvo = true;
      $('msgOk').innerHTML = `Registro <b>#${data.registro_id}</b> salvo com sucesso.`;
      $('btnConfirmar').disabled = true;
      renderAlertas(data.alertas || []);
      renderTotais(data.totais_por_dia || []);
      data.itens.forEach((it, i) => {
        const tr = document.querySelector(`tr[data-idx="${i}"]`);
        if (tr && it.estimado) {
          tr.querySelector('.badge-origem')?.remove();
          const td = tr.querySelectorAll('td')[4];
          if (td) td.innerHTML += '<span class="badge badge-estimado">ESTIMADO</span>';
        }
      });
      carregarRegistros();  // novo registro aparece na lista
    } catch (e) {
      $('msgOk').textContent = '';
      $('msgErro').textContent = 'Erro ao salvar: ' + e.message;
    }
  }

  /* ---------------- init ---------------- */
  $('selPaciente').addEventListener('change', () => {
    $('detalhe').innerHTML = '';
    detalheAberto = null;
    carregarRegistros();
  });
  document.addEventListener('DOMContentLoaded', carregarPacientes);
})();
