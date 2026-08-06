"""
App Flask + SQLAlchemy + Flask-Admin
Interface administrativa para o banco de Cardápio Hospitalar
"""
from flask import Flask, redirect, url_for


from config import Config
from extensions import db, admin
from dashboard import DashboardView
from admin_views import setup_admin
from api.composicao import composicao_bp
from api.otimizacao import otimizacao_bp
from api.rotulo import rotulo_bp
from api.paciente import paciente_bp


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Inicializa extensões com o app
    db.init_app(app)

    # Registra views do admin (ANTES de init_app!)
    setup_admin()

    # Registra blueprints de forma idempotente (evita erro no reloader)
    for bp in [composicao_bp, otimizacao_bp, rotulo_bp, paciente_bp]:
        if bp.name not in app.blueprints:
            app.register_blueprint(bp)


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

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
