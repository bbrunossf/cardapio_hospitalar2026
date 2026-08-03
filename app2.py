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


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Inicializa extensões com o app
    db.init_app(app)

    # Registra views do admin (ANTES de init_app!)
    setup_admin()

    # Registra blueprint da API de composição
    app.register_blueprint(composicao_bp)
    app.register_blueprint(otimizacao_bp)

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
