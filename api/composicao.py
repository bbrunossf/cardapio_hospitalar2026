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
    """Ficha técnica do prato: detalhes + ingredientes + passos + nutrientes"""
    prato = db.session.execute(
        text("""
            SELECT p.id, p.nome, p.porcao_padrao_g, tp.nome AS tipo,
                   p.consistencia, p.textura, p.temperatura_servimento,
                   p.tempo_producao_min
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

    passos = db.session.execute(
        text("""
            SELECT id, ordem, descricao
            FROM passos_preparo
            WHERE prato_id = :pid AND desativado = 0
            ORDER BY ordem, id
        """), {'pid': prato_id}
    ).mappings().all()

    nutrientes_row = db.session.execute(
        text("""
            SELECT energia_kcal, proteina_g, carboidrato_g, lipidios_g,
                   fibra_alimentar_g, sodio_mg, potassio_mg
            FROM vw_pratos_nutricional
            WHERE prato_id = :pid
        """), {'pid': prato_id}
    ).mappings().first()

    nutrientes = {
        k: float(v) if v is not None else 0.0
        for k, v in (dict(nutrientes_row) if nutrientes_row else {}).items()
    }

    massa_calculada = sum(float(r['quantidade_g'] or 0) for r in ingredientes)
    porcao = float(prato['porcao_padrao_g'] or 0)
    diferenca = round(massa_calculada - porcao, 2)
    ok = abs(diferenca) < 0.01

    return jsonify({
        'prato': dict(prato),
        'ingredientes': [dict(r) for r in ingredientes],
        'modo_preparo': [dict(r) for r in passos],
        'nutrientes': nutrientes,
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


# ══════════════════════════════════════════════════════════════════
# MODO DE PREPARO (passos) — Ficha Técnica
# ══════════════════════════════════════════════════════════════════

@composicao_bp.route('/api/pratos/<int:prato_id>/modo-preparo', methods=['POST'])
def api_add_passo_preparo(prato_id):
    """Adiciona um passo ao modo de preparo (ordem = última + 1)"""
    prato = db.session.execute(
        text("SELECT 1 FROM pratos WHERE id = :pid AND desativado = 0"),
        {'pid': prato_id}
    ).scalar()
    if not prato:
        return jsonify({'error': 'Prato não encontrado'}), 404

    data = request.get_json() or {}
    descricao = (data.get('descricao') or '').strip()
    if not descricao:
        return jsonify({'error': 'Descrição do passo não pode ser vazia'}), 400

    ultima_ordem = db.session.execute(
        text("""
            SELECT COALESCE(MAX(ordem), 0) FROM passos_preparo
            WHERE prato_id = :pid AND desativado = 0
        """),
        {'pid': prato_id}
    ).scalar() or 0

    res = db.session.execute(
        text("""
            INSERT INTO passos_preparo (prato_id, ordem, descricao)
            VALUES (:pid, :ordem, :descricao)
        """),
        {'pid': prato_id, 'ordem': ultima_ordem + 1, 'descricao': descricao}
    )
    db.session.commit()
    return jsonify({
        'success': True,
        'passo': {'id': res.lastrowid, 'ordem': ultima_ordem + 1, 'descricao': descricao}
    }), 201


@composicao_bp.route('/api/modo-preparo/<int:passo_id>', methods=['PATCH'])
def api_update_passo_preparo(passo_id):
    """Edita descricao e/ou ordem de um passo"""
    passo = db.session.execute(
        text("SELECT id FROM passos_preparo WHERE id = :pid AND desativado = 0"),
        {'pid': passo_id}
    ).scalar()
    if not passo:
        return jsonify({'error': 'Passo não encontrado'}), 404

    data = request.get_json() or {}
    updates = []
    params = {'pid': passo_id}

    if 'descricao' in data:
        descricao = (data.get('descricao') or '').strip()
        if not descricao:
            return jsonify({'error': 'Descrição do passo não pode ser vazia'}), 400
        updates.append("descricao = :descricao")
        params['descricao'] = descricao

    if 'ordem' in data:
        try:
            ordem = int(data.get('ordem'))
        except (TypeError, ValueError):
            return jsonify({'error': 'Ordem deve ser um inteiro >= 1'}), 400
        if ordem < 1:
            return jsonify({'error': 'Ordem deve ser um inteiro >= 1'}), 400
        updates.append("ordem = :ordem")
        params['ordem'] = ordem

    if not updates:
        return jsonify({'error': 'Nenhum campo para atualizar'}), 400

    db.session.execute(
        text(f"UPDATE passos_preparo SET {', '.join(updates)}, editado_em = CURRENT_TIMESTAMP WHERE id = :pid"),
        params
    )
    db.session.commit()
    return jsonify({'success': True})


@composicao_bp.route('/api/modo-preparo/<int:passo_id>', methods=['DELETE'])
def api_remove_passo_preparo(passo_id):
    """Remove um passo do modo de preparo (soft delete)"""
    res = db.session.execute(
        text("""
            UPDATE passos_preparo
            SET desativado = 1, editado_em = CURRENT_TIMESTAMP
            WHERE id = :pid AND desativado = 0
        """),
        {'pid': passo_id}
    )
    db.session.commit()
    if res.rowcount == 0:
        return jsonify({'error': 'Passo não encontrado'}), 404
    return jsonify({'success': True})


@composicao_bp.route('/api/pratos/<int:prato_id>/preparo', methods=['PATCH'])
def api_update_preparo(prato_id):
    """Atualiza tempo_producao_min do prato (ficha técnica)"""
    prato = db.session.execute(
        text("SELECT 1 FROM pratos WHERE id = :pid AND desativado = 0"),
        {'pid': prato_id}
    ).scalar()
    if not prato:
        return jsonify({'error': 'Prato não encontrado'}), 404

    data = request.get_json() or {}
    if 'tempo_producao_min' not in data:
        return jsonify({'error': 'Campo tempo_producao_min é obrigatório'}), 400

    valor = data.get('tempo_producao_min')
    if valor is None:
        db.session.execute(
            text("UPDATE pratos SET tempo_producao_min = NULL, editado_em = CURRENT_TIMESTAMP WHERE id = :pid"),
            {'pid': prato_id}
        )
        db.session.commit()
        return jsonify({'success': True, 'tempo_producao_min': None})

    try:
        minutos = int(valor)
    except (TypeError, ValueError):
        return jsonify({'error': 'Tempo de produção deve ser um inteiro >= 0'}), 400
    if minutos < 0:
        return jsonify({'error': 'Tempo de produção deve ser um inteiro >= 0'}), 400

    db.session.execute(
        text("UPDATE pratos SET tempo_producao_min = :min, editado_em = CURRENT_TIMESTAMP WHERE id = :pid"),
        {'min': minutos, 'pid': prato_id}
    )
    db.session.commit()
    return jsonify({'success': True, 'tempo_producao_min': minutos})


@composicao_bp.route('/composicao-view')
def composicao_view():
    return render_template('composicao.html')
