/* Busca de Alimentos Semelhantes — busca semântica independente do "Posso Comer?" */
(() => {
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g,
    (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const fmt = (n) => (n == null ? '—' : Number(n).toLocaleString('pt-BR'));

  const resultado = $('resultado');
  const msgErro = $('msgErro');

  function mostrarErro(msg) {
    msgErro.textContent = msg || '';
  }

  async function buscar() {
    const query = $('txtQuery').value.trim();
    if (!query) { mostrarErro('Digite um texto para buscar.'); return; }
    mostrarErro('');
    resultado.innerHTML = '<div class="carregando">Buscando alimentos semelhantes...</div>';

    try {
      const resp = await fetch('/api/busca-semelhantes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, top_k: parseInt($('selTopK').value, 10) }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.erro || `HTTP ${resp.status}`);
      renderizar(query, data.resultados || []);
    } catch (e) {
      resultado.innerHTML = '<div class="vazio">Nenhum resultado.</div>';
      mostrarErro('Erro: ' + e.message);
    }
  }

  function renderizar(query, itens) {
    if (!itens.length) {
      resultado.innerHTML = `<div class="vazio">Nenhum alimento semelhante encontrado para "${esc(query)}".</div>`;
      return;
    }
    const cards = itens.map((x) => `
      <div class="card">
        <div class="resultado-topo">
          <div>
            <span class="resultado-nome">${esc(x.nome)}</span>
            ${x.tipo ? `<span class="badge-tipo">${esc(x.tipo)}</span>` : ''}
          </div>
          <div class="distancia">distância: ${fmt(x.distancia)} <small>(menor = mais próximo)</small></div>
        </div>
        <div class="kcal">${x.kcal_100g != null ? fmt(x.kcal_100g) + ' kcal/100g' : 'kcal indisponível'}</div>
        ${x.texto_semantico ? `<div class="texto-semantico">${esc(x.texto_semantico)}</div>` : ''}
      </div>`).join('');
    resultado.innerHTML = `
      <div class="vazio">${itens.length} resultado(s) para "${esc(query)}" — mais próximo primeiro:</div>
      ${cards}`;
  }

  $('btnBuscar').addEventListener('click', buscar);
  $('txtQuery').addEventListener('keydown', (e) => { if (e.key === 'Enter') buscar(); });
})();
