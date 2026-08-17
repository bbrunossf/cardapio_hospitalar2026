"""CRUD das regras de personalização por paciente (Fase 1).

Todas as rotas validam a posse do paciente (authz.paciente_acessivel) ANTES de
qualquer leitura/escrita — uma única gate cobre as 4 tabelas do delta.

Tipos: faixa (restricoes_nutricionais_paciente), elegibilidade
(regras_elegibilidade_paciente), variedade (regras_variedade_paciente),
exclusao (exclusoes_paciente). DELETE = soft delete (desativado=1).

Docs: docs/personalizacao_por_paciente.md
"""
import json

from flask import Blueprint, jsonify, request

from authz import paciente_acessivel
from extensions import db
from models_personalizacao import (
    ExclusaoPaciente,
    RegraElegibilidadePaciente,
    RegraVariedadePaciente,
    RestricaoNutricionalPaciente,
)

regras_bp = Blueprint("regras_paciente", __name__)

TIPOS = {
    "faixa": RestricaoNutricionalPaciente,
    "elegibilidade": RegraElegibilidadePaciente,
    "variedade": RegraVariedadePaciente,
    "exclusao": ExclusaoPaciente,
}


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _valores_elegibilidade(v):
    """Normaliza para JSON array (aceita lista ou string separada por ';')."""
    if isinstance(v, list):
        return json.dumps([str(x).strip() for x in v if str(x).strip()], ensure_ascii=False)
    if isinstance(v, str):
        s = v.strip()
        if s.startswith("["):
            return s  # já é JSON
        itens = [x.strip() for x in s.split(";") if x.strip()]
        return json.dumps(itens, ensure_ascii=False)
    return None


def _preencher(regra, payload, parcial=False):
    """Valida e preenche a regra conforme o tipo. Retorna None ou msg de erro.

    parcial=True (PATCH): só atualiza campos presentes no payload; campos
    ausentes mantêm o valor atual.
    """
    if isinstance(regra, RestricaoNutricionalPaciente):
        if "nutriente" in payload:
            nutriente = (payload.get("nutriente") or "").strip().lower()
            if not nutriente:
                return "nutriente é obrigatório."
            regra.nutriente = nutriente
        elif not parcial:
            return "nutriente é obrigatório."
        if "valor_minimo" in payload:
            regra.valor_minimo = _num(payload.get("valor_minimo"))
        if "valor_maximo" in payload:
            regra.valor_maximo = _num(payload.get("valor_maximo"))
        if regra.valor_minimo is None and regra.valor_maximo is None:
            return "informe valor_minimo ou valor_maximo (pelo menos um)."
        return None

    if isinstance(regra, RegraElegibilidadePaciente):
        if "atributo" in payload:
            atributo = (payload.get("atributo") or "").strip().lower()
            if not atributo:
                return "atributo é obrigatório."
            regra.atributo = atributo
        elif not parcial:
            return "atributo é obrigatório."
        if "valores_permitidos" in payload:
            valores = _valores_elegibilidade(payload.get("valores_permitidos"))
            if not valores:
                return "valores_permitidos é obrigatório (lista ou 'A;B')."
            regra.valores_permitidos = valores
        if "operador" in payload:
            operador = (payload.get("operador") or "IN").strip().upper()
            if operador not in ("IN", "NOT IN"):
                return "operador deve ser IN ou NOT IN."
            regra.operador = operador
        elif not parcial:
            regra.operador = "IN"
        return None

    if isinstance(regra, RegraVariedadePaciente):
        if "tipo_prato_id" in payload:
            tipo_prato_id = _int(payload.get("tipo_prato_id"))
            if not tipo_prato_id:
                return "tipo_prato_id é obrigatório."
            regra.tipo_prato_id = tipo_prato_id
        elif not parcial:
            return "tipo_prato_id é obrigatório."
        if "dias_minimos_repeticao" in payload:
            regra.dias_minimos_repeticao = _int(payload.get("dias_minimos_repeticao"))
        if "frequencia_maxima_semanal" in payload:
            regra.frequencia_maxima_semanal = _int(payload.get("frequencia_maxima_semanal"))
        return None

    if isinstance(regra, ExclusaoPaciente):
        tem_lado = "prato_id" in payload or "ingrediente_id" in payload
        if tem_lado and "prato_id" in payload and "ingrediente_id" in payload:
            return "informe exatamente um: prato_id OU ingrediente_id."
        if "prato_id" in payload:
            regra.prato_id = _int(payload.get("prato_id"))
            regra.ingrediente_id = None  # troca de lado limpa o outro
        if "ingrediente_id" in payload:
            regra.ingrediente_id = _int(payload.get("ingrediente_id"))
            regra.prato_id = None
        if tem_lado and (not regra.prato_id) == (not regra.ingrediente_id):
            return "informe exatamente um: prato_id OU ingrediente_id."
        if not parcial and not tem_lado:
            return "informe prato_id ou ingrediente_id."
        if "motivo" in payload:
            regra.motivo = (payload.get("motivo") or "").strip() or None
        return None

    return "tipo de regra desconhecido."


# ─── GET: todas as regras do paciente ────────────────────────────────────
@regras_bp.route("/api/pacientes/<int:paciente_id>/regras", methods=["GET"])
def listar_regras(paciente_id):
    if not paciente_acessivel(paciente_id):
        return jsonify({"erro": "Paciente não encontrado."}), 404

    faixas = (RestricaoNutricionalPaciente.query
              .filter_by(paciente_id=paciente_id, desativado=False)
              .order_by(RestricaoNutricionalPaciente.nutriente).all())
    elegibilidade = (RegraElegibilidadePaciente.query
                     .filter_by(paciente_id=paciente_id, desativado=False)
                     .order_by(RegraElegibilidadePaciente.atributo).all())
    variedade = (RegraVariedadePaciente.query
                 .filter_by(paciente_id=paciente_id, desativado=False)
                 .order_by(RegraVariedadePaciente.tipo_prato_id).all())
    exclusoes = (ExclusaoPaciente.query
                 .filter_by(paciente_id=paciente_id, desativado=False)
                 .order_by(ExclusaoPaciente.id).all())

    return jsonify({
        "faixas": [r.to_dict() for r in faixas],
        "elegibilidade": [r.to_dict() for r in elegibilidade],
        "variedade": [r.to_dict() for r in variedade],
        "exclusoes": [r.to_dict() for r in exclusoes],
    })


# ─── POST: criar regra ───────────────────────────────────────────────────
@regras_bp.route("/api/pacientes/<int:paciente_id>/regras/<tipo>", methods=["POST"])
def criar_regra(paciente_id, tipo):
    if not paciente_acessivel(paciente_id):
        return jsonify({"erro": "Paciente não encontrado."}), 404

    Model = TIPOS.get(tipo)
    if not Model:
        return jsonify({"erro": f"tipo deve ser um de: {sorted(TIPOS)}."}), 400

    payload = request.get_json(silent=True) or {}
    regra = Model(paciente_id=paciente_id)
    erro = _preencher(regra, payload)
    if erro:
        return jsonify({"erro": erro}), 400

    db.session.add(regra)
    db.session.commit()
    return jsonify(regra.to_dict()), 201


# ─── PATCH: atualizar regra (campos enviados apenas) ─────────────────────
@regras_bp.route("/api/pacientes/<int:paciente_id>/regras/<tipo>/<int:regra_id>",
                 methods=["PATCH"])
def atualizar_regra(paciente_id, tipo, regra_id):
    if not paciente_acessivel(paciente_id):
        return jsonify({"erro": "Paciente não encontrado."}), 404

    Model = TIPOS.get(tipo)
    if not Model:
        return jsonify({"erro": f"tipo deve ser um de: {sorted(TIPOS)}."}), 400

    regra = Model.query.filter_by(id=regra_id, paciente_id=paciente_id,
                                  desativado=False).first()
    if not regra:
        return jsonify({"erro": "Regra não encontrada."}), 404

    payload = request.get_json(silent=True) or {}
    erro = _preencher(regra, payload, parcial=True)
    if erro:
        return jsonify({"erro": erro}), 400

    db.session.commit()
    return jsonify(regra.to_dict())


# ─── DELETE: soft delete (desativado=1) ──────────────────────────────────
@regras_bp.route("/api/pacientes/<int:paciente_id>/regras/<tipo>/<int:regra_id>",
                 methods=["DELETE"])
def remover_regra(paciente_id, tipo, regra_id):
    if not paciente_acessivel(paciente_id):
        return jsonify({"erro": "Paciente não encontrado."}), 404

    Model = TIPOS.get(tipo)
    if not Model:
        return jsonify({"erro": f"tipo deve ser um de: {sorted(TIPOS)}."}), 400

    regra = Model.query.filter_by(id=regra_id, paciente_id=paciente_id).first()
    if not regra:
        return jsonify({"erro": "Regra não encontrada."}), 404

    regra.desativado = True
    db.session.commit()
    return jsonify({"sucesso": True})
