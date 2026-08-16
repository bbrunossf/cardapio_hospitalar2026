---
name: identidade-visual-bruno
description: "Use when creating, redesigning, or styling any frontend UI for Bruno Oliveira's projects (cardápio hospitalar Flask-Admin, horas_plena Remix, dashboards, relatórios HTML). Applies his personal visual identity: institutional clean, NHS Blue #005EB8, IBM Plex Sans, off-white backgrounds, sidebar-first, no emojis, colorblind-safe (manager has deuteranopia/protanopia)."
version: 1.0.0
author: Bruno Oliveira + Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [design, identidade-visual, frontend, acessibilidade, daltonismo, tailwind, flask-admin]
    related_skills: [design-md, claude-design, popular-web-designs, sketch, tabelas-bruno]
---

# Identidade Visual Bruno (Cardápio Plena)

Identidade visual pessoal do Bruno para TODOS os seus projetos com UI. Vibe: **institucional limpo, clean, bem legível, com toques de azul**. Construída em conjunto (ago/2026), validada no projeto cardápio hospitalar.

## When to Use

- Criar ou redesenhar qualquer UI dos projetos do Bruno (cardápio Flask-Admin, horas_plena Remix, dashboards, HTMLs de relatório)
- Gerar gráficos/visualizações (aplicar paleta acessível)
- Estilizar componentes novos (tabelas, cards, badges, botões, modais)
- Perguntas de design: "qual cor/fonte/layout usar?"

**Don't use for:** backends sem UI, documentos de texto puro, ou projetos de terceiros (a menos que ele peça).

## Tokens Canônicos

Fonte da verdade: `/home/plena/novo_cardapio/DESIGN.md` (formato Google, validado com `npx @google/design.md lint` — 0 erros WCAG). Export Tailwind: `tailwind.theme.json` no mesmo diretório. SEMPRE consultar o DESIGN.md antes de estilizar; se o DESIGN.md evoluir, atualizar a skill.

### Cores (NHS Blue — saúde/institucional)

- **primary** `#005EB8` — NHS Blue, ÚNICO driver de interação (botões, links, nav ativa, foco)
- **primary-hover** `#004E99`
- **primary-soft** `#E6F0FA` — headers de tabela, hover, badges, seleção
- **background** `#F4F7FA` — off-white (NUNCA branco puro como fundo de página — cansa a vista em sessões longas)
- **surface** `#FFFFFF` — só cards/sidebar/modais (elevação), nunca página inteira
- **text** `#1F2933` · **text-muted** `#5C6B7A` · **border** `#D9E1E8`
- Semânticas (sempre com ícone/texto junto — ver pitfall daltonismo):
  - sucesso `#0B7A75` (teal) · badge-bg `#DDF0EE` · texto `#065F5A`
  - aviso `#E8A33D` (âmbar) · badge-bg `#FBF0DC` · texto `#7A5300`
  - erro `#C2410C` (laranja queimado) · badge-bg `#F9E4DC` · texto `#9A3309`

### Tipografia

- **IBM Plex Sans** em tudo (sem serifa, personalidade, legibilidade). Nunca serifada/decorativa.
- Hierarquia estilo Markdown H1→H4: `2rem/700` · `1.5rem/700` · `1.25rem/600` · `1.125rem/600`
- **Números SEMPRE tabulares** (`font-feature-settings: "tnum"`) — alinhamento em colunas + segurança OCR (Bruno teve falha de OCR com fontes decorativas onde 0/O e 1/l colidiam)
- body `1rem/400/lh1.5` · sm `0.875rem` · label `0.8125rem/600/+0.04em`

### Layout

- **Sidebar sempre** (240px, branca, item ativo = texto primary + bg primary-soft). Marca registrada do Bruno.
- Header 64px (título H1 + ações contextuais)
- **Largura máxima da tela** (sem "gaiola" de largura fixa)
- Ícones: **SVG inline (estilo Lucide). NUNCA emojis** na UI.
- Cards: brancos, raio 8px, padding 24px, borda hairline `#D9E1E8` (sombra só em modal/dropdown: `0 1px 3px rgba(15,23,42,0.08)`)
- Raios: sm 4px (botões/inputs) · md 8px (cards/tabelas) · lg 12px (badges/pills)
- Espaçamento base: 16px entre seções, 8px dentro de células

### Componentes

- `button-primary` — bg `#005EB8`, texto branco, raio 4px, padding 12px; hover `#004E99`
- `button-secondary` — bg `primary-soft`, texto primary
- `table-header` — bg `primary-soft`, texto `#1F2933`, células numéricas tabulares
- **Tabelas** — mecanismo e snippets na skill `tabelas-bruno`: apresentação = CSS sticky puro (0KB JS); interativa (busca/sort/paginação + header fixo) = Grid.js. NUNCA DataTables/Tabulator/AG Grid
- `badge-*` — pills com cor + rótulo/ícone (nunca cor sozinha)
- Motion: 150-200ms, respeitar `prefers-reduced-motion`, nada de animação pesada/autoplay

## Stack por Projeto

- **Cardápio hospitalar (Flask-Admin, Jinja + Bootstrap):** sobrescrever tema Bootstrap com CSS scoped ou Tailwind CDN. SEM React, SEM shadcn, SEM Material Components JS (estética Material via CSS puro está ok). DOIS CSS distintos: `identidade.css` (dashboard que estende `admin/master.html`, escopado em `.idv-dashboard`) e `identidade_paginas.css` (páginas standalone: composicao, otimizacao_form/retrato/paisagem). Ver `references/paginas-standalone.md`.
- **horas_plena (Remix/React):** tokens via Tailwind (export `tailwind.theme.json`) ou CSS modules.
- **Relatórios HTML/Plotly:** paleta Blues/NHS Blue, fundo escuro ok p/ densidade, legenda nunca depender só de cor.

## Common Pitfalls

1. **Vermelho/verde como único diferenciador** — o gerente do Bruno tem deuteranopia/protanopia. Sucesso/erro/aviso SEMPRE carregam ícone ou texto, nunca só cor. Usar teal/âmbar/laranja queimado (distinguíveis por matiz E luminância).
2. **Branco puro como fundo de página** — Bruno odeia brilho extremo. Fundo é `#F4F7FA`; branco é só pra elevação (cards).
3. **Emojis na UI** — proibido. Ícones SVG inline.
4. **Fonte decorativa ou serifada** — proibida. IBM Plex Sans sempre. Números sem tnum = coluna desalinhada + risco OCR.
5. **Largura fixa de conteúdo** — Bruno quer largura máxima da tela.
6. **shadcn/React no Flask-Admin** — não se aplica; não sugerir reescrita de front pra isso.
7. **Esquecer o DESIGN.md** — é a fonte da verdade; skill e DESIGN.md devem evoluir juntos.
8. **Contraste WCAG** — validar badges/tons claros com o linter (`npx -y @google/design.md lint DESIGN.md`) após mudar tokens; tons claros passam raspando em 4.5:1 — escurecer o texto (ex: badge-success texto `#065F5A` em bg `#DDF0EE`).
9. **`layout:` no frontmatter do DESIGN.md** — chave NÃO reconhecida pelo linter; é silenciosamente ignorada no export. Valores de layout vão na prosa ou direto nos componentes (ex: `sidebar width: 240px`).
10. **Warnings "orphaned-tokens"** são inofensivas (cores utilitárias usadas pelo CSS, não por componentes) — não bloqueiam.
11. **App Flask-Admin pode não subir por dependência ausente NÃO relacionada** (ex: `rapidfuzz` no módulo rotulo) — validar o template isoladamente (stub do master.html + render Jinja2 com dados mock) em vez de exigir o app completo. Ver `references/aplicar-flask-admin.md`.
12. **Flask sem debug CACHEIA templates** — após editar templates, o app precisa ser REINICIADO (`flask --app app2.py run`; reiniciar o processo) senão as rotas continuam servindo o HTML antigo. Sintoma clássico: curl retorna conteúdo velho logo após a edição.
13. **Emojis gerados no JS também contam** — ao restylar página com JS inline, trocar emojis que aparecem em template literals/strings (statusIcon, botões ✕, "✓ salvo"), não só os do HTML estático.

## Verification Checklist

- [ ] Cores usadas = tokens do DESIGN.md (nunca hex inventado)
- [ ] Fundo off-white `#F4F7FA`, branco só em superfícies elevadas
- [ ] IBM Plex Sans + números tabulares em toda coluna numérica
- [ ] Sidebar presente, largura máxima, sem emojis (ícones SVG)
- [ ] Semânticas com ícone/texto (nunca cor-only), sem vermelho/verde puros
- [ ] Motion sutil + `prefers-reduced-motion`
- [ ] `npx -y @google/design.md lint DESIGN.md` → 0 erros

## Support Files

- `references/design-md-lint-pitfalls.md` — pitfalls reais do linter do DESIGN.md (chaves ignoradas, contraste WCAG em tons claros, valores validados)
- `references/aplicar-flask-admin.md` — padrão de aplicação no Flask-Admin (dashboard.html + CSS scoped + smoke test sem app completo)
- `references/paginas-standalone.md` — páginas fora do admin (composicao/otimizacao): técnica "manter nomes de variáveis CSS que o JS inline usa", troca de emojis no JS, verificação por curl
- `references/impeccable-e-skills-multiarquivo.md` — avaliação da skill Impeccable + como instalar skills multi-arquivo (SKILL.md + references/ + scripts/)
