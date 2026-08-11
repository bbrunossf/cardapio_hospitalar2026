# Aplicar a Identidade no Flask-Admin (padrão validado em ago/2026)

Projeto: `/home/plena/novo_cardapio` (Flask `Flask(__name__)` + Flask-Admin). Aplicação real: `templates/admin/dashboard.html` + `static/css/identidade.css`.

## Estrutura

- Flask(`__name__`) → pasta static padrão = `<projeto>/static/` (criar se não existir). CSS em `static/css/identidade.css`.
- Template estende o chrome do Flask-Admin: `{% extends 'admin/master.html' %}` + `<link rel="stylesheet" href="{{ url_for('static', filename='css/identidade.css') }}">` dentro do bloco body.
- **Escopar TODO o CSS sob `.idv-dashboard`** — não interferir no Bootstrap do admin (sidebar/menu continuam do Flask-Admin).

## Classes (componentes) definidas

`idv-dashboard` (fundo `#F4F7FA`, fonte IBM Plex Sans) · `idv-header` · `idv-h1`/`idv-h3` (com SVG inline na cor primary) · `idv-sub` · `idv-stats`/`idv-stat` (grid auto-fit; icon 44px em círculo primary-soft, valor 2.25rem tabular, label muted) · `idv-alert` (âmbar `#FBF0DC` + texto `#7A5300` + ícone — nunca cor sozinha) · `idv-grid`/`idv-panel` (minmax 320px) · `idv-table` (th bg `primary-soft`, th.numeric/td.numeric right-aligned, td.muted, td.bold) · `idv-bar-row`/`idv-bar-track`/`idv-bar-fill` (`#005EB8`) · `idv-diet-*` · `idv-footer`.

- Números: classe `.num` = `font-variant-numeric: tabular-nums` (alinhamento + segurança OCR).
- Ícones: SVG inline estilo Lucide (stroke currentColor, width 2, round caps). **Zero emojis.**
- Motion: transições 150ms; media query `prefers-reduced-motion` no fim do CSS.

## Smoke test SEM o app completo (importante!)

O app pode não subir por dependência ausente não relacionada ao template (ex: `ModuleNotFoundError: No module named 'rapidfuzz'` — módulo `rotulo/duplicidade.py`). NÃO bloquear nisso; validar o template isolado:

1. Criar stub `admin/master.html` em `/tmp/idv_stub/admin/` com `<body>{% block body %}{% endblock %}</body>`.
2. Renderizar com `ChoiceLoader([FileSystemLoader('/tmp/idv_stub'), FileSystemLoader('<projeto>/templates')])` + contexto mockado (stats, top_kcal, top_prot, pratos_por_tipo, top_porcoes, consistencias, consistencias_total, dietas_sal; `url_for` stub).
3. Conferir: classes presentes, SVGs ≥6, zero emojis, link CSS, `.num` >5.
4. (Opcional) abrir no browser a versão autocontida (CSS inline) e ler estilos computados via console: fundo `rgb(244,247,250)`, barra `rgb(0,94,184)`, fonte IBM Plex Sans, `tabular-nums` — prova real de que a identidade aplicou.
