"""
Monitor de uso por rota para apps Flask — análogo Flask do remix-usage-monitor.

Cada requisição ao app é registrada via before_request em um SQLite (stdlib
`sqlite3`, zero dependências). O "módulo" é identificado por request.endpoint
(ex: 'admin.index', 'prato.edit_view', 'composicao.index') — estável, no mesmo
espírito do route.id no Remix.

Por que server-side e não beacon JS (como no Remix)?
  No Remix o beacon existia porque navegações SPA não batem no servidor.
  Num app Flask server-rendered, TODA navegação é um page load — o servidor
  já vê cada acesso. before_request registra com 1 INSERT, sem JS, sem
  round-trip extra, e captura também quem navega sem JavaScript.

- Painel: GET /api/usage  (HTML, paleta Blues) com filtro de período e matriz módulo × dia
- JSON:   GET /api/usage?format=json
- Guard:  token via env USAGE_ADMIN_TOKEN (header X-Usage-Token ou ?token=)
- DB:     env USAGE_DB_PATH (default: usage.db ao lado deste módulo)
- TZ:     env USAGE_TZ (ex: America/Sao_Paulo); default: fuso local do servidor
- Prune:  python usage_monitor.py prune <dias>   (remove eventos antigos)

Instalação (3 passos):
1. Copiar este arquivo para a raiz do projeto Flask.
2. No create_app():
       from usage_monitor import register_usage
       register_usage(app)          # registra before_request + rota /api/usage
3. .env: USAGE_ADMIN_TOKEN=<segredo>            (obrigatório p/ abrir o painel)
         USAGE_DB_PATH=/caminho/fora/usage.db   (opcional; fora da árvore se
                                                 o deploy usar rsync --delete)
"""

import hmac
import html
import os
import sqlite3
from datetime import datetime, date, timedelta

from flask import Blueprint, request, jsonify, Response

__all__ = ["register_usage", "UsageStore"]

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "usage.db")

# Paths que não geram evento (assets e o próprio painel)
EXCLUDE_PATHS = ("/static", "/admin/static", "/favicon.ico", "/api/usage")

# Máximo de módulos na matriz do painel (evita tabela gigante)
MATRIX_MAX_ROWS = 60


def _now():
    """Data/hora do evento. Usa USAGE_TZ se definido, senão fuso local do servidor."""
    tz = os.environ.get("USAGE_TZ", "")
    if tz:
        try:
            from zoneinfo import ZoneInfo
            return datetime.now(ZoneInfo(tz))
        except Exception:
            pass
    return datetime.now()


# ─── Store ────────────────────────────────────────────────────────────────

class UsageStore:
    """SQLite store (stdlib) — schema espelhado do remix-usage-monitor."""

    def __init__(self, db_path):
        self.db_path = db_path
        parent = os.path.dirname(os.path.abspath(db_path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._init()

    def _connect(self):
        return sqlite3.connect(self.db_path, timeout=5)

    def _init(self):
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS usage_events (
                    id       INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts       TEXT    NOT NULL,
                    day      TEXT    NOT NULL,
                    endpoint TEXT    NOT NULL,
                    path     TEXT    NOT NULL,
                    method   TEXT    NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_usage_day ON usage_events(day)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_usage_endpoint ON usage_events(endpoint)")

    def record(self, endpoint, path, method):
        now = _now()
        try:
            with self._connect() as conn:
                conn.execute(
                    "INSERT INTO usage_events (ts, day, endpoint, path, method)"
                    " VALUES (?,?,?,?,?)",
                    (now.isoformat(timespec="seconds"), now.strftime("%Y-%m-%d"),
                     endpoint, path, method),
                )
        except sqlite3.Error:
            pass  # nunca derruba a requisição por causa do monitor

    def query(self, de=None, ate=None):
        """Agrega por rota, por dia e matriz rota × dia no período [de, ate].
        Default: últimos 14 dias (inclusive hoje)."""
        if de is None:
            de = (date.today() - timedelta(days=13)).isoformat()
        if ate is None:
            ate = date.today().isoformat()
        with self._connect() as conn:
            by_route = conn.execute(
                "SELECT endpoint, COUNT(*) AS total, COUNT(DISTINCT day) AS dias"
                " FROM usage_events WHERE day BETWEEN ? AND ?"
                " GROUP BY endpoint ORDER BY total DESC, endpoint",
                (de, ate)).fetchall()
            by_day = conn.execute(
                "SELECT day, COUNT(*) AS total FROM usage_events"
                " WHERE day BETWEEN ? AND ? GROUP BY day ORDER BY day",
                (de, ate)).fetchall()
            matrix = conn.execute(
                "SELECT endpoint, day, COUNT(*) AS total FROM usage_events"
                " WHERE day BETWEEN ? AND ? GROUP BY endpoint, day",
                (de, ate)).fetchall()
        return {
            "de": de,
            "ate": ate,
            "by_route": [{"endpoint": r[0], "total": r[1], "dias": r[2]} for r in by_route],
            "by_day": [{"day": d[0], "total": d[1]} for d in by_day],
            "matrix": [{"endpoint": m[0], "day": m[1], "total": m[2]} for m in matrix],
        }

    def prune(self, dias):
        """Remove eventos com day < hoje - dias. Retorna nº de linhas removidas."""
        cutoff = (date.today() - timedelta(days=dias)).isoformat()
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM usage_events WHERE day < ?", (cutoff,))
            return cur.rowcount


# ─── Registro no app ─────────────────────────────────────────────────────

def _is_static(endpoint, path):
    """True para requisições que não devem gerar evento."""
    if endpoint is None:
        return True  # 404 / rotas sem endpoint não contam
    if endpoint == "static" or endpoint.endswith(".static"):
        return True  # static do Flask e do Flask-Admin
    if path.startswith(EXCLUDE_PATHS):
        return True
    return False


def register_usage(app, db_path=None, admin_token=None):
    """Registra o before_request + rota /api/usage. Retorna a UsageStore."""
    db_path = db_path or os.environ.get("USAGE_DB_PATH") or DEFAULT_DB_PATH
    token = admin_token if admin_token is not None else os.environ.get("USAGE_ADMIN_TOKEN", "")
    store = UsageStore(db_path)

    app.extensions["usage_monitor_store"] = store
    app.extensions["usage_monitor_token"] = token

    @app.before_request
    def _usage_record():
        path = request.path
        endpoint = request.endpoint
        if _is_static(endpoint, path):
            return None
        store.record(endpoint, path, request.method)
        return None

    bp = Blueprint("usage_monitor", __name__)

    def _authorized():
        token = app.extensions["usage_monitor_token"]
        if not token:
            return "unconfigured"
        provided = request.headers.get("X-Usage-Token") or request.args.get("token")
        if not provided:
            return False
        return hmac.compare_digest(provided, token)

    @bp.route("/api/usage", methods=["GET"])
    def usage_panel():
        auth = _authorized()
        if auth == "unconfigured":
            return Response(
                "Painel de uso não configurado: defina USAGE_ADMIN_TOKEN no .env.",
                status=503)
        if auth is not True:
            return Response("Não autorizado. Use header X-Usage-Token ou ?token=.",
                            status=401)
        de = request.args.get("de") or None
        ate = request.args.get("ate") or None
        data = store.query(de, ate)
        if request.args.get("format") == "json":
            return jsonify(data)
        return Response(_render_panel(data), mimetype="text/html; charset=utf-8")

    app.register_blueprint(bp)
    return store


# ─── Painel HTML (paleta Blues, monocromático — daltônico-friendly) ──────

def _pretty(endpoint):
    """Endpoint → nome amigável em pt-BR."""
    if endpoint == "admin.index":
        return "Dashboard (admin)"
    model, _, action = endpoint.partition(".")
    action = action.replace("_", " ")
    labels = {
        "index": "início", "index view": "lista", "edit view": "editar",
        "create view": "novo", "delete view": "excluir", "details view": "detalhes",
    }
    label = labels.get(action, action)
    name = model.replace("_", " ").title()
    if name == "Admin":
        return label.title() if label else endpoint
    return f"{name} — {label}" if label else name


def _render_panel(data):
    de, ate = data["de"], data["ate"]
    by_route, by_day, matrix = data["by_route"], data["by_day"], data["matrix"]
    total = sum(d["total"] for d in by_day)
    days = [d["day"] for d in by_day]
    max_day = max((m["total"] for m in matrix), default=0)

    cell = {}
    for m in matrix:
        cell.setdefault(m["endpoint"], {})[m["day"]] = m["total"]

    rows = []
    for r in by_route[:MATRIX_MAX_ROWS]:
        ep = html.escape(_pretty(r["endpoint"]))
        raw = html.escape(r["endpoint"])
        tds = []
        for d in days:
            c = cell.get(r["endpoint"], {}).get(d, 0)
            if c and max_day:
                alpha = 0.14 + 0.76 * min(1.0, c / max_day)
                tds.append(f'<td class="num" style="background:rgba(30,90,168,{alpha:.2f});color:#fff">{c}</td>')
            else:
                tds.append('<td class="num"></td>')
        rows.append(
            f'<tr><td title="{raw}">{ep}</td>'
            f'<td class="num"><b>{r["total"]}</b></td>'
            f'<td class="num">{r["dias"]}</td>{"".join(tds)}</tr>')

    day_rows = "".join(
        f'<tr><td>{d["day"]}</td><td class="num">{d["total"]}</td></tr>'
        for d in by_day)

    qs = [f"de={de}", f"ate={ate}", "format=json"]
    tok = request.args.get("token")
    if tok:
        qs.append(f"token={tok}")
    json_href = "/api/usage?" + "&".join(qs)

    head_days = "".join(f"<th>{d[5:]}</th>" for d in days)  # MM-DD

    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Uso por módulo</title>
<style>
:root {{ --bg:#eef3f8; --card:#fff; --ink:#0d3b66; --muted:#5b7a9d;
        --accent:#1e5aa8; --line:#c9ddf0; --soft:#e8f0f8; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
       background:var(--bg); color:var(--ink); }}
header {{ background:linear-gradient(135deg,#0d3b66,#1e5aa8); color:#fff;
         padding:22px 28px; }}
header h1 {{ margin:0 0 4px; font-size:1.35rem; }}
header p {{ margin:0; opacity:.85; font-size:.9rem; }}
.wrap {{ max-width:1150px; margin:0 auto; padding:20px 28px 60px; }}
.cards {{ display:flex; gap:14px; flex-wrap:wrap; margin:18px 0; }}
.card {{ background:var(--card); border:1px solid var(--line); border-radius:10px;
        padding:14px 20px; min-width:150px; box-shadow:0 1px 3px rgba(13,59,102,.08); }}
.card b {{ display:block; font-size:1.6rem; color:var(--accent); }}
.card span {{ color:var(--muted); font-size:.8rem; }}
form.filtro {{ background:var(--card); border:1px solid var(--line); border-radius:10px;
              padding:12px 16px; display:flex; gap:10px; align-items:center; flex-wrap:wrap; }}
form.filtro label {{ color:var(--muted); font-size:.85rem; }}
form.filtro input[type=date] {{ border:1px solid var(--line); border-radius:6px;
                               padding:6px 8px; font:inherit; }}
button {{ background:var(--accent); color:#fff; border:0; border-radius:6px;
         padding:7px 16px; cursor:pointer; font:inherit; }}
a.btn {{ background:var(--soft); color:var(--accent); border:1px solid var(--line);
        border-radius:6px; padding:6px 12px; text-decoration:none; font-size:.85rem; }}
section {{ margin-top:22px; }}
h2 {{ font-size:.95rem; color:var(--muted); text-transform:uppercase;
      letter-spacing:.05em; margin-bottom:8px; }}
table {{ width:100%; border-collapse:collapse; background:var(--card);
        border:1px solid var(--line); border-radius:10px; font-size:.84rem; }}
th, td {{ padding:7px 10px; border-bottom:1px solid var(--soft); text-align:left;
         white-space:nowrap; }}
th {{ background:var(--soft); color:var(--ink); font-weight:600; }}
td.num {{ text-align:right; font-variant-numeric:tabular-nums; }}
tr:hover td {{ background:#f4f8fc; }}
.scroll {{ overflow-x:auto; border:1px solid var(--line); border-radius:10px; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(240px,1fr)); gap:14px; }}
</style></head><body>
<header>
  <h1>📊 Uso por módulo</h1>
  <p>acessos anônimos por rota · período {de} → {ate} · <a class="btn" href="{json_href}">JSON</a></p>
</header>
<div class="wrap">
  <div class="cards">
    <div class="card"><b>{total}</b><span>acessos no período</span></div>
    <div class="card"><b>{len(days)}</b><span>dias com acesso</span></div>
    <div class="card"><b>{len(by_route)}</b><span>módulos acessados</span></div>
  </div>
  <form class="filtro" method="get">
    <label>De <input type="date" name="de" value="{de}"></label>
    <label>Até <input type="date" name="ate" value="{ate}"></label>
    <button>Filtrar</button>
    <span style="flex:1"></span>
    <a class="btn" href="/api/usage">últimos 14 dias</a>
  </form>
  <section>
    <h2>Módulos × dias (matriz)</h2>
    <div class="scroll">
      <table>
        <tr><th>Módulo</th><th class="num">Total</th><th class="num">Dias</th>{head_days}</tr>
        {''.join(rows)}
      </table>
    </div>
  </section>
  <section>
    <h2>Totais por dia</h2>
    <div class="scroll" style="max-width:420px">
      <table>{day_rows}</table>
    </div>
  </section>
</div>
</body></html>"""


# ─── CLI (prune / resumo) ────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    store = UsageStore(os.environ.get("USAGE_DB_PATH") or DEFAULT_DB_PATH)
    if len(sys.argv) > 1 and sys.argv[1] == "prune":
        dias = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        print(f"Removidos {store.prune(dias)} eventos com mais de {dias} dias.")
    else:
        data = store.query()
        print(f"Eventos no DB: {sum(d['total'] for d in data['by_day'])} "
              f"(últimos 14 dias), {len(data['by_route'])} módulos.")
