from flask import Blueprint, jsonify, request, render_template
from sqlalchemy import text
from extensions import db

composicao_bp = Blueprint('composicao', __name__)


@composicao_bp.route('/api/pratos')
def api_pratos():
    """Lista todos os pratos ativos com tipo"""
    pratos = db.session.execute(
        text("""
            SELECT p.id, p.nome, p.porcao_padrao_g, tp.nome AS tipo,
                   COUNT(pc.ingrediente_id) AS qtd_ingredientes,
                   ROUND(SUM(pc.quantidade_g), 2) AS massa_total
            FROM pratos p
            LEFT JOIN tipos_preparacoes tp ON p.tipo_prato_id = tp.id
            LEFT JOIN prato_composicao pc ON p.id = pc.prato_id AND pc.desativado = 0
            WHERE p.desativado = 0
            GROUP BY p.id
            ORDER BY p.nome
        """)
    ).mappings().all()

    return jsonify([dict(r) for r in pratos])


@composicao_bp.route('/api/pratos/<int:prato_id>/composicao')
def api_prato_composicao(prato_id):
    """Detalhes do prato + ingredientes"""
    prato = db.session.execute(
        text("""
            SELECT p.id, p.nome, p.porcao_padrao_g, tp.nome AS tipo,
                   p.consistencia, p.textura, p.temperatura_servimento
            FROM pratos p
            LEFT JOIN tipos_preparacoes tp ON p.tipo_prato_id = tp.id
            WHERE p.id = :pid AND p.desativado = 0
        """), {'pid': prato_id}
    ).mappings().first()

    if not prato:
        return jsonify({'error': 'Prato não encontrado'}), 404

    ingredientes = db.session.execute(
        text("""
            SELECT pc.ingrediente_id, i.nome AS ingrediente, pc.quantidade_g
            FROM prato_composicao pc
            JOIN ingredientes i ON i.id = pc.ingrediente_id
            WHERE pc.prato_id = :pid AND pc.desativado = 0
            ORDER BY i.nome
        """), {'pid': prato_id}
    ).mappings().all()

    massa_calculada = sum(float(r['quantidade_g'] or 0) for r in ingredientes)
    porcao = float(prato['porcao_padrao_g'] or 0)
    diferenca = round(massa_calculada - porcao, 2)
    ok = abs(diferenca) < 0.01

    return jsonify({
        'prato': dict(prato),
        'ingredientes': [dict(r) for r in ingredientes],
        'massa_calculada': massa_calculada,
        'diferenca': diferenca,
        'ok': ok
    })


@composicao_bp.route('/api/pratos/<int:prato_id>/porcao', methods=['POST'])
def api_update_porcao(prato_id):
    """Atualiza porcao_padrao_g do prato"""
    data = request.get_json()
    novo_valor = data.get('porcao_padrao_g')
    if novo_valor is None or float(novo_valor) <= 0:
        return jsonify({'error': 'Valor inválido'}), 400

    db.session.execute(
        text("UPDATE pratos SET porcao_padrao_g = :val, editado_em = CURRENT_TIMESTAMP WHERE id = :pid"),
        {'val': float(novo_valor), 'pid': prato_id}
    )
    db.session.commit()
    return jsonify({'success': True, 'porcao_padrao_g': float(novo_valor)})


@composicao_bp.route('/api/composicao/<int:prato_id>/<int:ingrediente_id>', methods=['POST'])
def api_update_composicao(prato_id, ingrediente_id):
    """Atualiza quantidade_g de um ingrediente na composição"""
    data = request.get_json()
    nova_qtd = data.get('quantidade_g')
    if nova_qtd is None or float(nova_qtd) <= 0:
        return jsonify({'error': 'Quantidade inválida'}), 400

    db.session.execute(
        text("""
            UPDATE prato_composicao
            SET quantidade_g = :qtd, editado_em = CURRENT_TIMESTAMP
            WHERE prato_id = :pid AND ingrediente_id = :iid AND desativado = 0
        """),
        {'qtd': float(nova_qtd), 'pid': prato_id, 'iid': ingrediente_id}
    )
    db.session.commit()
    return jsonify({'success': True, 'quantidade_g': float(nova_qtd)})


@composicao_bp.route('/api/ingredientes')
def api_ingredientes():
    """Lista todos os ingredientes ativos"""
    ingredientes = db.session.execute(
        text("SELECT id, nome, tipo_alimento FROM ingredientes WHERE desativado = 0 ORDER BY nome")
    ).mappings().all()
    return jsonify([dict(r) for r in ingredientes])


@composicao_bp.route('/api/composicao/<int:prato_id>/add/<int:ingrediente_id>', methods=['POST'])
def api_add_composicao(prato_id, ingrediente_id):
    """Adiciona um ingrediente ao prato"""
    data = request.get_json() or {}
    qtd = float(data.get('quantidade_g', 10))

    if qtd <= 0:
        return jsonify({'error': 'Quantidade deve ser positiva'}), 400

    # Verifica se já existe
    existente = db.session.execute(
        text("SELECT 1 FROM prato_composicao WHERE prato_id = :pid AND ingrediente_id = :iid"),
        {'pid': prato_id, 'iid': ingrediente_id}
    ).scalar()

    if existente:
        return jsonify({'error': 'Ingrediente já pertence ao prato'}), 409

    db.session.execute(
        text("""
            INSERT INTO prato_composicao (prato_id, ingrediente_id, quantidade_g)
            VALUES (:pid, :iid, :qtd)
        """),
        {'pid': prato_id, 'iid': ingrediente_id, 'qtd': qtd}
    )
    db.session.commit()
    return jsonify({'success': True, 'quantidade_g': qtd}), 201


@composicao_bp.route('/api/composicao/<int:prato_id>/<int:ingrediente_id>', methods=['DELETE'])
def api_remove_composicao(prato_id, ingrediente_id):
    """Remove um ingrediente do prato (soft delete)"""
    db.session.execute(
        text("""
            UPDATE prato_composicao
            SET desativado = 1, editado_em = CURRENT_TIMESTAMP
            WHERE prato_id = :pid AND ingrediente_id = :iid
        """),
        {'pid': prato_id, 'iid': ingrediente_id}
    )
    db.session.commit()
    return jsonify({'success': True})


@composicao_bp.route('/composicao-view')
def composicao_view():
    return render_template('composicao.html')
