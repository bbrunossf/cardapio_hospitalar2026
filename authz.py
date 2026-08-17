"""Autorização: papéis + escopo por dono (equivalente a RLS na aplicação).

SQLite não tem RLS nativo; o isolamento é feito aqui: toda consulta de dado
de paciente é escopada por `pacientes.criado_por` quando o usuário não é
admin. Tabelas filhas (planos, cardápios, restrições) herdam o escopo via
paciente — ver docs/autenticacao.md.

Se um dia migrar para PostgreSQL, a mesma coluna vira política RLS real.
"""
from flask_login import current_user

from extensions import db
from models_paciente import Paciente


def is_admin() -> bool:
    """Admin enxerga tudo (bypass do filtro por dono)."""
    return current_user.is_authenticated and current_user.papel == "admin"


def papel_atual() -> str | None:
    return current_user.papel if current_user.is_authenticated else None


def query_pacientes():
    """Query de pacientes com escopo por dono (admin vê todos)."""
    q = db.session.query(Paciente).filter(Paciente.desativado == False)
    if is_admin():
        return q
    return q.filter(Paciente.criado_por == current_user.id)


def paciente_acessivel(paciente_id):
    """Retorna o paciente se o usuário pode acessá-lo; senão None.

    Admin: qualquer paciente ativo. Demais papéis: apenas os próprios
    (criado_por == id do usuário). Paciente desativado nunca acessível.
    """
    p = db.session.get(Paciente, paciente_id)
    if not p or p.desativado:
        return None
    if is_admin():
        return p
    if p.criado_por == current_user.id:
        return p
    return None


def plano_acessivel(plano) -> bool:
    """Valida acesso a um plano via posse do paciente dele."""
    if is_admin():
        return True
    return bool(paciente_acessivel(plano.paciente_id))
