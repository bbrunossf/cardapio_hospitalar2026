"""Blueprint de API para cadastro de pacientes."""
from datetime import date, datetime

from flask import Blueprint, jsonify, render_template, request
from sqlalchemy import or_

from flask_login import current_user

from authz import paciente_acessivel, query_pacientes
from extensions import db
from models_paciente import Paciente

paciente_bp = Blueprint("paciente", __name__, template_folder="../templates")


# ---------------------------------------------------------------------------
# Rotas de API REST
# ---------------------------------------------------------------------------

@paciente_bp.route("/api/pacientes", methods=["GET"])
def api_listar_pacientes():
    """Lista pacientes ativos (opcional: ?q= busca por nome)."""
    q = request.args.get("q", "").strip()

    query = query_pacientes()

    if q:
        query = query.filter(Paciente.nome.ilike(f"%{q}%"))

    pacientes = query.order_by(Paciente.nome).all()
    return jsonify([p.to_dict() for p in pacientes])


@paciente_bp.route("/api/pacientes/<int:paciente_id>", methods=["GET"])
def api_obter_paciente(paciente_id):
    """Obtém um paciente pelo ID."""
    paciente = paciente_acessivel(paciente_id)
    if not paciente:
        return jsonify({"erro": "Paciente não encontrado."}), 404
    return jsonify(paciente.to_dict())


@paciente_bp.route("/api/pacientes", methods=["POST"])
def api_criar_paciente():
    """Cria um novo paciente."""
    payload = request.get_json() or {}
    if not payload.get("nome"):
        return jsonify({"erro": "Nome é obrigatório."}), 400

    paciente = _preencher_paciente(Paciente(), payload)
    paciente.criado_por = current_user.id
    db.session.add(paciente)
    db.session.commit()
    return jsonify(paciente.to_dict()), 201


@paciente_bp.route("/api/pacientes/<int:paciente_id>", methods=["PUT"])
def api_atualizar_paciente(paciente_id):
    """Atualiza um paciente existente."""
    paciente = paciente_acessivel(paciente_id)
    if not paciente:
        return jsonify({"erro": "Paciente não encontrado."}), 404

    payload = request.get_json() or {}
    _preencher_paciente(paciente, payload)
    db.session.commit()
    return jsonify(paciente.to_dict())


@paciente_bp.route("/api/pacientes/<int:paciente_id>", methods=["DELETE"])
def api_desativar_paciente(paciente_id):
    """Desativa um paciente (soft delete)."""
    paciente = paciente_acessivel(paciente_id)
    if not paciente:
        return jsonify({"erro": "Paciente não encontrado."}), 404
    paciente.desativado = True
    db.session.commit()
    return jsonify({"sucesso": True})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _preencher_paciente(paciente: Paciente, dados: dict) -> Paciente:
    paciente.nome = dados.get("nome", paciente.nome)

    # Data de nascimento (aceita string ISO ou dict de data)
    dn = dados.get("data_nascimento")
    if dn:
        try:
            if isinstance(dn, str):
                paciente.data_nascimento = date.fromisoformat(dn)
            else:
                paciente.data_nascimento = dn
        except (ValueError, TypeError):
            pass
    elif dn is None and "data_nascimento" in dados:
        paciente.data_nascimento = None

    paciente.sexo = dados.get("sexo")
    paciente.peso_kg = dados.get("peso_kg")
    paciente.altura_cm = dados.get("altura_cm")
    paciente.cintura_cm = dados.get("cintura_cm")
    paciente.quadril_cm = dados.get("quadril_cm")
    paciente.objetivo = dados.get("objetivo", paciente.objetivo or "manter")
    paciente.nivel_atividade_fisica = dados.get("nivel_atividade_fisica", paciente.nivel_atividade_fisica)
    paciente.observacoes = dados.get("observacoes")
    return paciente


# ---------------------------------------------------------------------------
# Página web
# ---------------------------------------------------------------------------

@paciente_bp.route("/pacientes")
def pagina_pacientes():
    """Lista de pacientes cadastrados."""
    return render_template("pacientes.html")


@paciente_bp.route("/pacientes/novo")
def pagina_novo_paciente():
    """Formulário de cadastro de novo paciente."""
    return render_template("paciente_form.html", paciente=None)


@paciente_bp.route("/pacientes/<int:paciente_id>/editar")
def pagina_editar_paciente(paciente_id):
    """Formulário de edição de paciente."""
    paciente = paciente_acessivel(paciente_id)
    if not paciente:
        return render_template("pacientes.html"), 404
    return render_template("paciente_form.html", paciente=paciente)
