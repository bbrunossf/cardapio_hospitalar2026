"""
Módulo "Posso Comer?" — consequências de ingerir um alimento fora do cardápio
estabelecido do paciente (plano: docs/posso_comer.md).

- Interpretação de texto/foto e estimativa de nutrientes: API separada
  (/home/plena/api_posso_comer, GPT-4o-mini) — configurável via
  POSSO_COMER_API_URL (default http://127.0.0.1:5010)
- Todo o resto é determinístico/local: busca no banco, cálculo da porção,
  comparativo com o dia, semáforo, mensagem e alternativas
- Semáforo (autorizado verde/amarelo/vermelho): acréscimo % sobre o total do dia
  ≤ +10% verde · +10% a +25% amarelo · > +25% vermelho (pior entre kcal e sódio)
"""
import os
import re
import unicodedata
from datetime import date

import httpx
from flask import Blueprint, jsonify, render_template, request
from sqlalchemy import text
from extensions import db

posso_comer_bp = Blueprint('posso_comer', __name__)

API_URL = os.getenv('POSSO_COMER_API_URL', 'http://127.0.0.1:5010')
API_TIMEOUT = 20

LIMITE_VERDE = 10.0
LIMITE_AMARELO = 25.0


# ---------------------------------------------------------------- utilidades
def _norm(s):
    """Minúsculas, sem acentos, sem pontuação -> lista de tokens."""
    s = unicodedata.normalize('NFD', s or '').encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9 ]', ' ', s.lower()).split()


def _chamar_api(path, payload):
    resp = httpx.post(f"{API_URL}{path}", json=payload, timeout=API_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _num(v, default=None):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------- contexto do dia
def _contexto_dia(paciente_id):
    """Retorna (fonte, kcal_dia, sodio_mg_dia). fonte: 'cardapio'|'plano'|'nenhum'."""
    cardapio = db.session.execute(text("""
        SELECT cs.id, cs.data_inicio, cs.dias
        FROM cardapios_salvos cs
        WHERE cs.paciente_id = :pid
        ORDER BY cs.id DESC LIMIT 1
    """), {'pid': paciente_id}).mappings().first()

    if cardapio:
        dia = 1
        if cardapio['data_inicio']:
            try:
                diff = (date.today() - date.fromisoformat(cardapio['data_inicio'])).days + 1
                dia = max(1, min(diff, cardapio['dias'] or 7))
            except ValueError:
                dia = 1
        cd = db.session.execute(text("""
            SELECT id, energia_kcal_total FROM cardapio_dias
            WHERE cardapio_id = :cid AND dia_numero = :dia
        """), {'cid': cardapio['id'], 'dia': dia}).mappings().first()
        if cd:
            kcal = _num(cd['energia_kcal_total'])
            sodio = db.session.execute(text("""
                SELECT ROUND(SUM(v.sodio_mg * cr.porcao_g / NULLIF(p.porcao_padrao_g, 0)), 2) AS sodio
                FROM cardapio_refeicoes cr
                JOIN pratos p ON p.id = cr.prato_id
                JOIN vw_pratos_nutricional v ON v.prato_id = cr.prato_id
                WHERE cr.cardapio_dia_id = :did
            """), {'did': cd['id']}).mappings().first()['sodio']
            if kcal:
                return 'cardapio', kcal, _num(sodio, 0.0)

    plano = db.session.execute(text("""
        SELECT meta_kcal FROM planos_nutricionais
        WHERE paciente_id = :pid AND status = 'ativo'
        ORDER BY id DESC LIMIT 1
    """), {'pid': paciente_id}).mappings().first()
    if plano and _num(plano['meta_kcal']):
        return 'plano', _num(plano['meta_kcal']), None

    return 'nenhum', None, None


def _contexto_publico(paciente_id):
    fonte, kcal, sodio = _contexto_dia(paciente_id)
    return {'fonte': fonte, 'kcal_dia': kcal, 'sodio_mg_dia': sodio}


# ---------------------------------------------------------------- busca no banco
def _buscar_alimento(nome):
    """Candidatos [{tipo, id, nome, kcal_100g, sodio_mg_100g}].

    Regra estrita: TODOS os tokens do nome (len >= 3) devem estar presentes no
    nome cadastrado — evita falso positivo ("bolo de chocolate" não casa com
    "Pudim de chocolate"). Sem match exato -> fluxo de descrição/estimativa.
    """
    tokens = [t for t in _norm(nome) if len(t) >= 3]
    if not tokens:
        return []

    candidatos = []
    # ingredientes (nutrientes por 100g)
    for r in db.session.execute(text("""
        SELECT id, nome, energia_kcal, sodio_mg FROM ingredientes WHERE desativado = 0
    """)).mappings().all():
        rt = set(_norm(r['nome']))
        if all(t in rt for t in tokens):
            candidatos.append({
                'tipo': 'ingrediente', 'id': r['id'], 'nome': r['nome'],
                'kcal_100g': _num(r['energia_kcal'], 0), 'sodio_mg_100g': _num(r['sodio_mg'], 0),
            })
    # pratos (via view, nutrientes por porção padrão -> kcal/100g)
    for r in db.session.execute(text("""
        SELECT p.id, p.nome, p.porcao_padrao_g, v.energia_kcal, v.sodio_mg
        FROM pratos p
        JOIN vw_pratos_nutricional v ON v.prato_id = p.id
        WHERE p.desativado = 0 AND v.energia_kcal IS NOT NULL
    """)).mappings().all():
        rt = set(_norm(r['nome']))
        porcao = _num(r['porcao_padrao_g'], 100) or 100
        if all(t in rt for t in tokens):
            candidatos.append({
                'tipo': 'prato', 'id': r['id'], 'nome': r['nome'],
                'kcal_100g': round(_num(r['energia_kcal'], 0) * 100 / porcao, 2),
                'sodio_mg_100g': round(_num(r['sodio_mg'], 0) * 100 / porcao, 2),
            })

    candidatos.sort(key=lambda c: c['nome'])
    return candidatos[:8]


def _alimento_da_porcao(candidato, porcao_g):
    """Calcula kcal/sódio da porção a partir do candidato (determinístico)."""
    porcao_g = max(1.0, _num(porcao_g, 100.0))
    fator = porcao_g / 100.0
    if candidato['tipo'] == 'prato':
        # kcal_100g já convertido; fator linear sobre 100g
        pass
    return {
        'tipo': candidato['tipo'], 'id': candidato['id'], 'nome': candidato['nome'],
        'kcal_porcao': round(candidato['kcal_100g'] * fator, 1),
        'sodio_mg_porcao': round(candidato['sodio_mg_100g'] * fator, 1),
        'porcao_g': porcao_g, 'estimado': False,
    }


# ---------------------------------------------------------------- resposta
def _mensagem(alimento, pcts, semafaro):
    partes = []
    if 'kcal_pct' in pcts:
        partes.append(f"{alimento['kcal_porcao']:.0f} kcal (+{pcts['kcal_pct']:.0f}%)")
    if 'sodio_pct' in pcts:
        partes.append(f"{alimento['sodio_mg_porcao']:.0f} mg de sódio (+{pcts['sodio_pct']:.0f}%)")
    txt = "Este alimento acrescenta " + ", ".join(partes) + " ao dia."
    if semafaro == 'verde':
        txt += " Impacto pequeno — liberado."
    elif semafaro == 'amarelo':
        txt += " Fica perto do limite — consuma com moderação."
    else:
        txt += " Compromete o dia — evite ou reduza a porção."
    if alimento.get('estimado'):
        txt += " Valores estimados (alimento não cadastrado)."
    return txt


def _alternativas(kcal_100g_alimento):
    if not kcal_100g_alimento:
        return []
    limite_max = kcal_100g_alimento * 0.9
    limite_min = kcal_100g_alimento * 0.3
    rows = db.session.execute(text("""
        SELECT nome, energia_kcal FROM ingredientes
        WHERE desativado = 0 AND energia_kcal BETWEEN :lo AND :hi
        ORDER BY energia_kcal DESC LIMIT 3
    """), {'lo': limite_min, 'hi': limite_max}).mappings().all()
    return [{'nome': r['nome'], 'kcal_100g': round(_num(r['energia_kcal'], 0), 1)} for r in rows]


def _montar_resposta(paciente_id, alimento):
    fonte, kcal_dia, sodio_dia = _contexto_dia(paciente_id)
    contexto = {'fonte': fonte, 'kcal_dia': kcal_dia, 'sodio_mg_dia': sodio_dia}

    pcts = {}
    if kcal_dia:
        pcts['kcal_pct'] = round(alimento['kcal_porcao'] / kcal_dia * 100, 1)
    if sodio_dia:
        pcts['sodio_pct'] = round(alimento['sodio_mg_porcao'] / sodio_dia * 100, 1)

    impacto = {'semafaro': None, 'pct_pior': None, 'kcal_pct': None, 'sodio_pct': None,
               'mensagem': '', 'alternativas': []}
    if fonte != 'nenhum' and pcts:
        pior = max(pcts.values())
        impacto['pct_pior'] = pior
        impacto['kcal_pct'] = pcts.get('kcal_pct')
        impacto['sodio_pct'] = pcts.get('sodio_pct')
        impacto['semafaro'] = ('verde' if pior <= LIMITE_VERDE
                               else 'amarelo' if pior <= LIMITE_AMARELO else 'vermelho')
        impacto['mensagem'] = _mensagem(alimento, pcts, impacto['semafaro'])
        if impacto['semafaro'] == 'vermelho':
            kcal_100g = alimento['kcal_porcao'] / alimento['porcao_g'] * 100 if alimento['porcao_g'] else None
            impacto['alternativas'] = _alternativas(kcal_100g)

    return {'encontrado': True, 'alimento': alimento, 'contexto': contexto, 'impacto': impacto}


# ---------------------------------------------------------------- rotas
@posso_comer_bp.route('/posso-comer')
def pagina_posso_comer():
    return render_template('posso_comer.html')


@posso_comer_bp.route('/api/posso-comer/contexto/<int:paciente_id>')
def api_contexto(paciente_id):
    return jsonify(_contexto_publico(paciente_id))


@posso_comer_bp.route('/api/posso-comer/consultar', methods=['POST'])
def api_consultar():
    data = request.get_json(silent=True) or {}
    paciente_id = data.get('paciente_id')
    if not paciente_id:
        return jsonify({'erro': 'paciente_id obrigatório'}), 400

    # --- modo 3: candidato escolhido na lista ambígua
    if data.get('candidato_tipo') and data.get('candidato_id'):
        c = None
        if data['candidato_tipo'] == 'ingrediente':
            r = db.session.execute(text(
                "SELECT id, nome, energia_kcal, sodio_mg FROM ingredientes WHERE id = :i AND desativado = 0"
            ), {'i': data['candidato_id']}).mappings().first()
            if r:
                c = {'tipo': 'ingrediente', 'id': r['id'], 'nome': r['nome'],
                     'kcal_100g': _num(r['energia_kcal'], 0), 'sodio_mg_100g': _num(r['sodio_mg'], 0)}
        else:
            r = db.session.execute(text("""
                SELECT p.id, p.nome, p.porcao_padrao_g, v.energia_kcal, v.sodio_mg
                FROM pratos p JOIN vw_pratos_nutricional v ON v.prato_id = p.id
                WHERE p.id = :i AND p.desativado = 0
            """), {'i': data['candidato_id']}).mappings().first()
            if r:
                porcao = _num(r['porcao_padrao_g'], 100) or 100
                c = {'tipo': 'prato', 'id': r['id'], 'nome': r['nome'],
                     'kcal_100g': round(_num(r['energia_kcal'], 0) * 100 / porcao, 2),
                     'sodio_mg_100g': round(_num(r['sodio_mg'], 0) * 100 / porcao, 2)}
        if not c:
            return jsonify({'erro': 'candidato não encontrado'}), 404
        alimento = _alimento_da_porcao(c, data.get('porcao_g') or 100.0)
        return jsonify(_montar_resposta(paciente_id, alimento))

    # --- modo 2: estimar (alimento fora do banco)
    if data.get('modo') == 'estimar':
        descricao = (data.get('descricao') or '').strip()
        if not descricao:
            return jsonify({'erro': 'informe a descrição do alimento'}), 400
        try:
            est = _chamar_api('/estimar', {
                'descricao': descricao,
                'porcao_g': data.get('porcao_g') or 100.0,
            })
        except httpx.HTTPError as e:
            return jsonify({'erro': f'API de interpretação indisponível: {e}'}), 502
        alimento = {
            'tipo': 'estimado', 'id': None, 'nome': descricao[:60],
            'kcal_porcao': _num(est.get('kcal_porcao'), 0),
            'sodio_mg_porcao': _num(est.get('sodio_mg_porcao'), 0),
            'porcao_g': _num(est.get('porcao_g'), 100.0), 'estimado': True,
        }
        return jsonify(_montar_resposta(paciente_id, alimento))

    # --- modo 1: interpretar texto ou imagem
    texto = (data.get('texto') or '').strip()
    imagem_b64 = data.get('imagem_base64') or ''
    mime = data.get('mime') or ''
    if not texto and not imagem_b64:
        return jsonify({'erro': 'informe "texto" (nome do alimento) ou "imagem_base64"'}), 400

    try:
        interp = _chamar_api('/interpretar',
                             {'texto': texto} if texto
                             else {'imagem_base64': imagem_b64, 'mime': mime})
    except httpx.HTTPError as e:
        return jsonify({'erro': f'API de interpretação indisponível: {e}'}), 502

    nome = (interp.get('nome_sugerido') or '').strip() or texto
    candidatos = _buscar_alimento(nome)

    if not candidatos:
        return jsonify({
            'encontrado': False,
            'nome_sugerido': nome,
            'descricao': interp.get('descricao', ''),
            'precisa_descricao': True,
            'contexto': _contexto_publico(paciente_id),
        })

    if len(candidatos) == 1:
        alimento = _alimento_da_porcao(candidatos[0], data.get('porcao_g') or 100.0)
        return jsonify(_montar_resposta(paciente_id, alimento))

    # ambíguo: devolve a lista para o usuário escolher
    return jsonify({
        'encontrado': False,
        'ambiguo': True,
        'nome_sugerido': nome,
        'candidatos': [{'tipo': c['tipo'], 'id': c['id'], 'nome': c['nome'],
                        'kcal_100g': c['kcal_100g'], 'sodio_mg_100g': c['sodio_mg_100g']}
                       for c in candidatos],
        'contexto': _contexto_publico(paciente_id),
    })
