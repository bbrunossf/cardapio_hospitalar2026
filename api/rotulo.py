"""Blueprint de API para cadastro de alimentos por rótulo nutricional."""
from flask import Blueprint, jsonify, request, render_template
from sqlalchemy import or_

from extensions import db
from models_rotulo import AlimentoIndustrializado
from rotulo import (
    cadastrar_por_codigo,
    cadastrar_por_imagem,
    confirmar_cadastro,
)

rotulo_bp = Blueprint("rotulo", __name__, template_folder="../templates")


@rotulo_bp.route("/api/alimentos/consulta-ean")
def api_consulta_ean():
    """Busca produto por EAN na base externa + duplicatas locais."""
    ean = request.args.get("ean", "").strip()
    if not ean:
        return jsonify({"erro": "EAN é obrigatório."}), 400

    resultado = cadastrar_por_codigo(ean)
    return jsonify(resultado)


@rotulo_bp.route("/api/alimentos/extrair-rotulo", methods=["POST"])
def api_extrair_rotulo():
    """Recebe imagem do rótulo e retorna dados extraídos + duplicatas + avisos."""
    if "imagem" not in request.files:
        return jsonify({"erro": "Nenhuma imagem enviada."}), 400

    imagem = request.files["imagem"]
    if imagem.filename == "":
        return jsonify({"erro": "Arquivo de imagem vazio."}), 400

    imagem_bytes = imagem.read()
    if not imagem_bytes:
        return jsonify({"erro": "Imagem vazia."}), 400

    # A imagem é usada apenas para extração e descartada (não armazenada)
    resultado = cadastrar_por_imagem(imagem_bytes)
    return jsonify(resultado)


@rotulo_bp.route("/api/alimentos", methods=["POST"])
def api_confirmar_alimento():
    """Confirma cadastro ou atualização de alimento."""
    payload = request.get_json() or {}
    if not payload.get("dados"):
        return jsonify({"erro": "Dados do alimento são obrigatórios."}), 400

    resultado = confirmar_cadastro(payload)
    status = 201 if resultado.get("sucesso") else 422
    return jsonify(resultado), status


@rotulo_bp.route("/api/alimentos/busca")
def api_busca_alimentos():
    """Busca local de alimentos industrializados para tela de revisão."""
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"erro": "Termo de busca é obrigatório."}), 400

    alimentos = (
        db.session.query(AlimentoIndustrializado)
        .filter(AlimentoIndustrializado.desativado == False)
        .filter(
            or_(
                AlimentoIndustrializado.nome.ilike(f"%{q}%"),
                AlimentoIndustrializado.marca.ilike(f"%{q}%"),
                AlimentoIndustrializado.codigo_barras.ilike(f"%{q}%"),
            )
        )
        .order_by(AlimentoIndustrializado.nome)
        .limit(50)
        .all()
    )

    return jsonify([
        {
            "id": a.id,
            "nome": a.nome,
            "marca": a.marca,
            "codigo_barras": a.codigo_barras,
            "fonte": a.fonte,
        }
        for a in alimentos
    ])


@rotulo_bp.route("/rotulo")
def pagina_rotulo():
    """Página web de cadastro por rótulo."""
    return render_template("rotulo.html")
