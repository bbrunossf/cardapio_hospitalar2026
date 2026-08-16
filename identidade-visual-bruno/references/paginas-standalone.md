# Páginas standalone (fora do admin) — padrão validado ago/2026

O dashboard estende o chrome do Flask-Admin (`admin/master.html`), mas rotas próprias
(`/composicao-view`, `/otimizacao`, resultados) usam templates HTML **completos e
independentes**: `composicao.html`, `otimizacao_form.html`, `otimizacao_retrato.html`,
`otimizacao_paisagem.html` — todos em `<projeto>/templates/`.

## Técnica-chave: manter NOMES das variáveis CSS que o JS inline usa

Essas páginas têm JavaScript inline que referencia variáveis CSS diretamente
(`style="background:var(--danger)"`, `color: var(--text2)` em template literals).
**Para restylar sem tocar no JS: mantenha os MESMOS nomes de variável e troque só os
valores.** O CSS unificado `static/css/identidade_paginas.css` redefine:

```css
:root {
  --bg: #F4F7FA;       /* era dark #1a1a2e */
  --surface: #FFFFFF;  /* era #16213e */
  --surface2: #E6F0FA; /* era #0f3460 */
  --text: #1F2933;     /* era #e0e0e0 */
  --text2: #5C6B7A;    /* era #a0a0a0 */
  --primary: #005EB8;  /* era #4fc3f7 */
  --danger: #C2410C;   /* era #ef5350 — NUNCA vermelho puro */
  --warning: #E8A33D;
  --success: #0B7A75;  /* era #66bb6a — NUNCA verde puro */
  --border: #D9E1E8;
  --radius: 8px;
}
```

Resultado: **zero mudança na lógica JS** — só o visual muda. Isso é o que torna o
restyle de páginas com JS inline barato e seguro.

## O que mais mudou no restyle

- `data-theme="dark"` removido do `<html>`; tema claro por padrão.
- Emojis substituídos por SVG inline estilo Lucide — INCLUSIVE os gerados no JS
  (statusIcon ✅/⚠️ → check/triângulo SVG em template literal; botão ✕ → SVG X;
  "✓ salvo" → SVG check + texto).
- Ícones novos: header (utensils), lupa (form otimização), play (botão executar),
  calendário/relógio (dias/refeições), seta (empty-state "selecione um prato").
- Badges de status: `.badge.ok` teal `#DDF0EE`/`#065F5A`, `.badge.warn` âmbar
  `#FBF0DC`/`#7A5300` — nunca verde/vermelho puros.
- Saída JSON do otimizador: HTML-escape (`replace(/</g,'&lt;')`) + classe `.json-output`
  (fundo surface, fonte mono) em vez de `<pre>` cru com cor hardcoded.
- Corrigido bug pré-existente: `otimizacao_retrato.html` tinha DOCTYPE/html aninhados
  duplicados — limpar na reescrita.
- Classes de componente adicionadas no CSS: `pg-container`, `pg-form`, `pg-result`,
  `pg-wrap`, `pg-h1`, `dia-card`, `dia-titulo`, `refeicao-nome`, `tipo-badge`,
  `status-badge`/`status-ok`/`status-warn`, `table-wrapper`, `paisagem-table`,
  `celula-*`, `json-output`/`json-back`.

## Verificação

1. Sintaxe Jinja: `python3 -c "from jinja2 import Environment, FileSystemLoader; Environment(loader=FileSystemLoader('templates')).get_template('X.html')"`.
2. Grep de emojis: `grep -P '[\x{1F300}-\x{1FAFF}\x{2600}-\x{27BF}]' templates/*.html`.
3. Teste real com o app rodando (ver pitfall de cache abaixo):
   `curl -s http://127.0.0.1:5000/composicao-view | grep -c identidade_paginas.css`
4. Otimização: `curl -s -X POST http://127.0.0.1:5000/api/otimizacao/executar -H "Content-Type: application/json" -d '{"dieta":"LIVRE","dias":1,"objetivo":"max_energia","formato":"html"}'` (retrato) e `formato":"html_paisagem"` (paisagem) — conferir classes da identidade e 0 emojis.
5. Browser: estilos computados (getComputedStyle) — fundo rgb(244,247,250), botão rgb(0,94,184), fonte IBM Plex Sans.
