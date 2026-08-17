"""Modelo SQLAlchemy para autenticação (tabela `usuarios`).

DDL: docs/sql/autenticacao.sql — Bruno executa manualmente.
"""
from flask_login import UserMixin
from sqlalchemy import func
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db


class Usuario(db.Model, UserMixin):
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nome = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True)
    senha_hash = db.Column(db.String(255), nullable=False)
    papel = db.Column(db.String(20), nullable=False, default="nutricionista")
    desativado = db.Column(db.Boolean, default=False)
    ultimo_login = db.Column(db.DateTime)
    criado_em = db.Column(db.DateTime, server_default=func.now())
    editado_em = db.Column(db.DateTime, server_default=func.now(), onupdate=func.now())

    PAPEIS = ("admin", "nutricionista", "leitura")

    @property
    def is_admin(self) -> bool:
        return self.papel == "admin"

    def set_senha(self, senha: str) -> None:
        """Grava o hash (scrypt do Werkzeug). Nunca guardar senha em claro."""
        self.senha_hash = generate_password_hash(senha)

    def check_senha(self, senha: str) -> bool:
        return check_password_hash(self.senha_hash, senha)

    def __str__(self) -> str:
        return self.nome or self.email
