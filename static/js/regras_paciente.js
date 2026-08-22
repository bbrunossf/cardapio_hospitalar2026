/* Regras do cardápio por paciente — personalização Fase 1.
   Bloco em planos.html (id="regras-cardapio"). APIs em api/regras_paciente.py.
   Sem dependências externas; fetch same-origin (sessão do login). */
(function () {
  'use strict';

  var sec = document.getElementById('regras-cardapio');
  if (!sec) return;

  var pacienteId = sec.dataset.pacienteId;
  var tipos = JSON.parse(sec.dataset.tipos || '[]');
  var pratos = JSON.parse(sec.dataset.pratos || '[]');
  var ingredientes = JSON.parse(sec.dataset.ingredientes || '[]');

  var nomePorId = function (lista) {
    var m = {};
    lista.forEach(function (x) { m[x.id] = x.nome; });
    return m;
  };
  var nomeTipo = nomePorId(tipos);
  var nomePrato = nomePorId(pratos);
  var nomeIngrediente = nomePorId(ingredientes);

  var LABEL_ATRIBUTO = {
    consistencia: 'Consistência', textura: 'Textura',
    temperatura_servimento: 'Temperatura', cor_predominante: 'Cor'
  };
  var LABEL_NUTRIENTE = {
    energia: 'Energia (kcal)', proteina: 'Proteína (g)', carboidrato: 'Carboidrato (g)',
    lipidios: 'Lipídios (g)', fibra: 'Fibra (g)', sodio: 'Sódio (mg)',
    potassio: 'Potássio (mg)', fosforo: 'Fósforo (mg)', calcio: 'Cálcio (mg)',
    ferro: 'Ferro (mg)', gordura_saturada: 'Gordura saturada (g)'
  };

  function api(url, opts) {
    return fetch(url, opts).then(function (r) {
      return r.json().then(function (d) { return { ok: r.ok, status: r.status, d: d }; })
        .catch(function () { return { ok: false, status: r.status, d: null }; });
    });
  }

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function faixaTexto(r) {
    var partes = [];
    if (r.valor_minimo != null) partes.push('\u2265 ' + r.valor_minimo);
    if (r.valor_maximo != null) partes.push('\u2264 ' + r.valor_maximo);
    return (LABEL_NUTRIENTE[r.nutriente] || r.nutriente) + ' \u2014 ' + partes.join(' e ') || 'faixa';
  }

  function itemHtml(titulo, detalhe, regra) {
    return '<div class="regras-item">' +
      '<div><b>' + esc(titulo) + '</b>' + (detalhe ? '<span class="regras-badge">' + esc(detalhe) + '</span>' : '') + '</div>' +
      '<div class="acoes">' +
      '<button type="button" class="btn-editar" data-acao="editar" data-regra=\'' + esc(JSON.stringify(regra)) + '\'>Editar</button>' +
      '<button type="button" class="btn-excluir" data-acao="excluir" data-id="' + regra.id + '">Excluir</button>' +
      '</div></div>';
  }

  function renderFaixas(lista) {
    return lista.map(function (r) {
      var d = [];
      if (r.valor_minimo != null) d.push('m\u00edn ' + r.valor_minimo);
      if (r.valor_maximo != null) d.push('m\u00e1x ' + r.valor_maximo);
      return itemHtml(LABEL_NUTRIENTE[r.nutriente] || r.nutriente, d.join(' \u00b7 '), r);
    }).join('');
  }

  function renderElegibilidade(lista) {
    return lista.map(function (r) {
      return itemHtml(
        (LABEL_ATRIBUTO[r.atributo] || r.atributo),
        r.operador + ' (' + r.valores_permitidos.join('; ') + ')', r);
    }).join('');
  }

  function renderVariedade(lista) {
    return lista.map(function (r) {
      var d = [];
      if (r.frequencia_maxima_semanal === 0) d.push('nunca servir');
      else if (r.frequencia_maxima_semanal != null) d.push('m\u00e1x ' + r.frequencia_maxima_semanal + '/semana');
      if (r.dias_minimos_repeticao != null) d.push('m\u00edn ' + r.dias_minimos_repeticao + ' dias entre repeti\u00e7\u00f5es');
      return itemHtml(nomeTipo[r.tipo_prato_id] || ('Tipo ' + r.tipo_prato_id), d.join(' \u00b7 '), r);
    }).join('');
  }

  function renderExclusoes(lista) {
    return lista.map(function (r) {
      var nome = r.prato_id ? nomePrato[r.prato_id] : nomeIngrediente[r.ingrediente_id];
      var tipo = r.prato_id ? 'Prato' : 'Ingrediente';
      return itemHtml(nome || (tipo + ' ' + (r.prato_id || r.ingrediente_id)),
        (r.motivo ? 'motivo: ' + r.motivo : ''), r);
    }).join('');
  }

  var RENDER = {
    faixas: renderFaixas,
    elegibilidade: renderElegibilidade,
    variedade: renderVariedade,
    exclusoes: renderExclusoes
  };

  function carregar() {
    api('/api/pacientes/' + pacienteId + '/regras').then(function (res) {
      if (!res.ok) { alert(res.d && res.d.erro ? res.d.erro : 'Erro ao carregar regras.'); return; }
      Object.keys(RENDER).forEach(function (tab) {
        var lista = document.querySelector('#regras-' + tab + ' .regras-lista');
        var itens = RENDER[tab](res.d[tab] || []);
        lista.innerHTML = itens || '<div class="regras-vazio">Nenhuma regra — herda da dieta base.</div>';
      });
    });
  }

  // ── abas ──
  document.querySelectorAll('.regras-tab').forEach(function (btn) {
    btn.addEventListener('click', function () {
      document.querySelectorAll('.regras-tab').forEach(function (b) { b.classList.remove('ativo'); });
      document.querySelectorAll('.regras-panel').forEach(function (p) { p.classList.remove('ativo'); });
      btn.classList.add('ativo');
      document.getElementById('regras-' + btn.dataset.tab).classList.add('ativo');
    });
  });

  // ── submit (criar ou salvar edição) ──
  document.querySelectorAll('.regras-form').forEach(function (form) {
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var tipo = form.dataset.tipo;
      var payload = {};
      new FormData(form).forEach(function (v, k) { payload[k] = v === '' ? null : v; });

      // exclusão: validar que exatamente um lado foi escolhido
      if (tipo === 'exclusao' && !!payload.prato_id === !!payload.ingrediente_id) {
        alert('Escolha exatamente um: prato OU ingrediente.');
        return;
      }

      var editId = form.dataset.editId;
      var url = '/api/pacientes/' + pacienteId + '/regras/' + tipo +
                (editId ? '/' + editId : '');
      var opts = {
        method: editId ? 'PATCH' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      };

      api(url, opts).then(function (res) {
        if (!res.ok) { alert(res.d && res.d.erro ? res.d.erro : 'Erro ao salvar.'); return; }
        form.reset();
        delete form.dataset.editId;
        form.querySelector('button[type=submit]').textContent = 'Adicionar';
        carregar();
      });
    });
  });

  // ── editar / excluir (delegação nos itens) ──
  document.querySelectorAll('.regras-lista').forEach(function (lista) {
    lista.addEventListener('click', function (e) {
      var btn = e.target.closest('button[data-acao]');
      if (!btn) return;
      // tipo da API vem do data-tipo do painel (singular), NÃO do id (plural)
      var tipo = lista.closest('.regras-panel').dataset.tipo;
      var id = btn.dataset.id;

      if (btn.dataset.acao === 'excluir') {
        if (!confirm('Excluir esta regra do paciente?')) return;
        api('/api/pacientes/' + pacienteId + '/regras/' + tipo + '/' + id, { method: 'DELETE' })
          .then(function (res) { if (res.ok) carregar(); });
        return;
      }

      if (btn.dataset.acao === 'editar') {
        var regra = JSON.parse(btn.dataset.regra);
        preencherForm(tipo, regra);
      }
    });
  });

  function preencherForm(tipo, regra) {
    var form = document.querySelector('.regras-form[data-tipo="' + tipo + '"]');
    if (!form) return;
    if (tipo === 'faixa') {
      form.nutriente.value = regra.nutriente;
      form.valor_minimo.value = regra.valor_minimo == null ? '' : regra.valor_minimo;
      form.valor_maximo.value = regra.valor_maximo == null ? '' : regra.valor_maximo;
    } else if (tipo === 'elegibilidade') {
      form.atributo.value = regra.atributo;
      form.valores_permitidos.value = (regra.valores_permitidos || []).join(';');
      form.operador.value = regra.operador;
    } else if (tipo === 'variedade') {
      form.tipo_prato_id.value = regra.tipo_prato_id;
      form.dias_minimos_repeticao.value = regra.dias_minimos_repeticao == null ? '' : regra.dias_minimos_repeticao;
      form.frequencia_maxima_semanal.value = regra.frequencia_maxima_semanal == null ? '' : regra.frequencia_maxima_semanal;
    } else if (tipo === 'exclusao') {
      form.prato_id.value = regra.prato_id || '';
      form.ingrediente_id.value = regra.ingrediente_id || '';
      form.motivo.value = regra.motivo || '';
    }
    form.dataset.editId = regra.id;
    form.querySelector('button[type=submit]').textContent = 'Salvar';
    form.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }

  carregar();
})();
