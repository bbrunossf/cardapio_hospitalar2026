"""
App Flask + SQLAlchemy + Flask-Admin + autenticação (Flask-Login)
Interface administrativa para o banco de Cardápio Hospitalar
"""
import click
from flask import Flask, abort, jsonify, redirect, request, url_for
from flask_login import current_user

from config import Config
from extensions import db, admin, login_manager
from dashboard import DashboardView
from admin_views import setup_admin
from models_auth import Usuario
from api.auth import auth_bp
from api.composicao import composicao_bp
from api.otimizacao import otimizacao_bp
from api.rotulo import rotulo_bp
from api.paciente import paciente_bp
from api.plano import plano_bp
from api.posso_comer import posso_comer_bp
from api.busca_semelhantes import busca_semelhantes_bp
from api.regras_paciente import regras_bp
from api.registro_alimentar import registro_bp
from usage_monitor import register_usage


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Inicializa extensões com o app
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Faça login para continuar."

    # Registra views do admin (ANTES de init_app!)
    setup_admin()

    # Registra blueprints de forma idempotente (evita erro no reloader)
    for bp in [auth_bp, composicao_bp, otimizacao_bp, rotulo_bp,
               paciente_bp, plano_bp, posso_comer_bp, busca_semelhantes_bp,
               regras_bp, registro_bp]:
        if bp.name not in app.blueprints:
            app.register_blueprint(bp)

    # Monitor de uso por rota (server-side, SQLite separado via USAGE_DB_PATH)
    register_usage(app)

    @login_manager.user_loader
    def carregar_usuario(user_id):
        return db.session.get(Usuario, int(user_id))

    # ─── Proteção global: exige login em tudo, menos exceções ───────────────
    # /api/* responde 401 JSON (fetch não quebra); demais redirecionam p/ login.
    # O papel/escopo é checado depois, em cada view/rota (ver authz.py).
    @app.before_request
    def exigir_login():
        if request.endpoint is None:
            return
        if request.endpoint in (
            "auth.login", "auth.logout", "static",
            "usage_monitor.usage_panel",  # painel tem guard próprio (token)
        ):
            return
        if current_user.is_authenticated:
            # leitura = somente leitura em qualquer lugar (nem POST nos forms)
            if current_user.papel == "leitura" and request.method != "GET":
                if request.path.startswith("/api/"):
                    return jsonify({"erro": "Usuário somente leitura."}), 403
                return abort(403)
            return
        if request.path.startswith("/api/"):
            return jsonify({"erro": "Não autenticado."}), 401
        return redirect(url_for("auth.login", next=request.path))

    print("Blueprints registrados:")
    for bp in app.blueprints:
        print(" -", bp)

    print("\nViews do Flask-Admin:")
    for view in admin._views:
        print(type(view).__name__, "->", getattr(view, "endpoint", None))

    # Inicializa admin passando a DashboardView customizada
    admin.init_app(app, index_view=DashboardView())

    # Rota raiz
    @app.route('/')
    def root():
        return redirect(url_for('admin.index'))

    # Injeta o objeto admin em todos os templates (para a navbar standalone
    # renderizar o mesmo menu do Flask-Admin fora das rotas /admin)
    @app.context_processor
    def inject_admin():
        return {"admin": admin}

    # ─── CLI: criar usuário (senha via prompt, hash scrypt) ─────────────────
    @app.cli.command("criar-usuario")
    @click.option("--email", required=True, prompt="E-mail")
    @click.option("--nome", required=True, prompt="Nome")
    @click.option("--papel", type=click.Choice(["admin", "nutricionista", "leitura"]),
                  default="nutricionista", show_default=True, prompt="Papel")
    @click.option("--senha", required=True, prompt="Senha",
                  hide_input=True, confirmation_prompt=True)
    def criar_usuario(email, nome, papel, senha):
        """Cria um usuário do sistema (senha nunca fica em claro)."""
        email = (email or "").strip().lower()
        with app.app_context():
            if db.session.query(Usuario).filter_by(email=email).first():
                raise click.ClickException(f"E-mail já cadastrado: {email}")
            u = Usuario(nome=(nome or "").strip(), email=email, papel=papel)
            u.set_senha(senha)
            db.session.add(u)
            db.session.commit()
            click.echo(f"Usuário criado: {email} ({papel})")

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
