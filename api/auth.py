"""Blueprint de autenticação: /login e /logout."""
from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user

from extensions import db
from models_auth import Usuario

auth_bp = Blueprint("auth", __name__, template_folder="../templates")


def _proximo_seguro(target):
    """Só redireciona para caminhos internos (evita open redirect)."""
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return url_for("admin.index")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("admin.index"))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        senha = request.form.get("senha") or ""
        usuario = Usuario.query.filter_by(email=email).first()

        if usuario and not usuario.desativado and usuario.check_senha(senha):
            login_user(usuario)
            usuario.ultimo_login = datetime.utcnow()
            db.session.commit()
            return redirect(_proximo_seguro(request.args.get("next")))

        flash("E-mail ou senha inválidos.", "erro")

    return render_template("login.html")


@auth_bp.route("/logout", methods=["POST"])
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
