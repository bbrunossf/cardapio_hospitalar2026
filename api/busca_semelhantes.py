"""
Busca de alimentos semelhantes (busca semântica) — página independente do
"Posso Comer?".

- Query de texto livre -> embedding via API isolada de interpretação
  (POSSO_COMER_API_URL /embed, chave não fica no app)
- Busca por similaridade na coleção `ingredientes_embeddings` do chroma_db
- Resultados enriquecidos com kcal e tipo do banco relacional
"""
import httpx
from flask import Blueprint, jsonify, render_template, request
from sqlalchemy import text, bindparam
from extensions import db

from api.posso_comer import _get_chroma, _chamar_api  # reuso do chroma lazy + chamador da API

busca_semelhantes_bp = Blueprint('busca_semelhantes', __name__)

COLECAO = 'ingredientes_embeddings'


@busca_semelhantes_bp.get('/busca-semelhantes')
def pagina():
    return render_template('busca_semelhantes.html')


@busca_semelhantes_bp.post('/api/busca-semelhantes')
def consultar():
    data = request.get_json(silent=True) or {}
    query = (data.get('query') or '').strip()
    try:
        top_k = int(data.get('top_k') or 3)
    except (TypeError, ValueError):
        top_k = 3
    top_k = max(1, min(top_k, 10))

    if not query:
        return jsonify({'erro': 'informe o texto da busca'}), 400

    # 1. embedding do texto da query (API isolada — mesma do "Posso Comer?")
    try:
        emb = _chamar_api('/embed', {'texto': query}).get('embedding')
    except httpx.HTTPError:
        emb = None
    if not emb:
        return jsonify({'erro': 'não foi possível gerar o embedding da consulta'}), 502

    # 2. busca por similaridade na coleção
    try:
        col = _get_chroma().get_collection(COLECAO)
        res = col.query(
            query_embeddings=[emb],
            n_results=top_k,
            include=['documents', 'distances', 'metadatas'],
        )
    except Exception as e:
        return jsonify({'erro': f'banco vetorial indisponível: {e}'}), 502

    ids = res['ids'][0] if res and res.get('ids') else []
    if not ids:
        return jsonify({'query': query, 'top_k': 0, 'resultados': []})

    # 3. enriquecer com kcal/tipo do banco relacional (metadados não têm energia)
    kcal_map = {}
    rows = db.session.execute(
        text("SELECT id, energia_kcal, tipo_alimento FROM ingredientes WHERE id IN :ids")
        .bindparams(bindparam('ids', expanding=True)),
        {'ids': tuple(int(i) for i in ids)},
    ).mappings().all()
    for r in rows:
        kcal_map[r['id']] = r

    resultados = []
    for i, mid in enumerate(ids):
        meta = res['metadatas'][0][i] or {}
        reg = kcal_map.get(int(mid))
        resultados.append({
            'id': int(mid),
            'nome': meta.get('nome') or f'Ingrediente {mid}',
            'tipo': meta.get('tipo') or (reg['tipo_alimento'] if reg else ''),
            'kcal_100g': (float(reg['energia_kcal'])
                          if reg and reg['energia_kcal'] is not None else None),
            'distancia': round(float(res['distances'][0][i]), 4),
            'texto_semantico': meta.get('texto_original') or '',
        })

    return jsonify({'query': query, 'top_k': len(resultados), 'resultados': resultados})
