"""
Blueprint de Otimização de Cardápio (PuLP)
Expõe rota POST para gerar cardápio otimizado com parâmetros do usuário.
"""
from flask import Blueprint, jsonify, request, render_template
from sqlalchemy import text
from extensions import db
import json
import pulp
from collections import defaultdict

otimizacao_bp = Blueprint('otimizacao', __name__)


# ══════════════════════════════════════════════════════════════════
# CARREGAMENTO DE DADOS
# ══════════════════════════════════════════════════════════════════

# Mapeamento de nutrientes das restrições para colunas do banco
COLUNAS_NUTRIENTES = {
    'energia': 'energia_kcal', 'proteina': 'proteina_g', 'lipidios': 'lipidios_g',
    'carboidrato': 'carboidrato_g', 'fibra': 'fibra_alimentar_g', 'sodio': 'sodio_mg',
    'potassio': 'potassio_mg',
}

# Mapeamento de atributos sensoriais das regras de elegibilidade para colunas do banco
# (a coluna da cor é 'cor_predominante', mas as regras usam 'cor')
MAP_ATRIBUTOS = {
    'cor': 'cor_predominante',
    'consistencia': 'consistencia',
    'textura': 'textura',
    'temperatura_servimento': 'temperatura_servimento',
}

# Mapeamento para view de alimentos industrializados (base 100g)
COLUNAS_INDUSTRIALIZADOS = {
    'energia': 'energia_kcal_100g',
    'proteina': 'proteinas_g_100g',
    'lipidios': 'gorduras_totais_g_100g',
    'carboidrato': 'carboidratos_g_100g',
    'fibra': 'fibras_g_100g',
    'sodio': 'sodio_mg_100g',
    'potassio': None,  # não disponível no módulo de rótulo
}


def carregar_alimentos_industrializados():
    """Carrega alimentos industrializados da view 100g (seção 9)."""
    rows = db.session.execute(text("""
        SELECT id, nome, marca,
               energia_kcal_100g, carboidratos_g_100g, proteinas_g_100g,
               gorduras_totais_g_100g, gorduras_saturadas_g_100g,
               gorduras_trans_g_100g, fibras_g_100g, sodio_mg_100g
        FROM vw_alimentos_industrializados_100g
    """)).mappings().all()
    return [dict(r) for r in rows]


def carregar_dados_otimizacao(dieta_nome="LIVRE", incluir_industrializados=False):
    """Carrega dados do banco via SQLAlchemy (substitui sqlite3 direto)."""
    dieta = db.session.execute(
        text("SELECT id FROM dietas WHERE nome = :nome"), {'nome': dieta_nome}
    ).mappings().first()
    if not dieta:
        raise ValueError(f"Dieta '{dieta_nome}' não encontrada.")
    dieta_id = dieta['id']

    pratos = db.session.execute(text("""
        SELECT p.id, p.nome, p.tipo_prato_id, p.cor_predominante,
               p.consistencia, p.textura, p.temperatura_servimento,
               p.porcao_padrao_g,
               COALESCE(v.energia_kcal, 0) AS energia_kcal,
               COALESCE(v.carboidrato_g, 0) AS carboidrato_g,
               COALESCE(v.proteina_g, 0) AS proteina_g,
               COALESCE(v.lipidios_g, 0) AS lipidios_g,
               COALESCE(v.fibra_alimentar_g, 0) AS fibra_alimentar_g,
               COALESCE(v.sodio_mg, 0) AS sodio_mg,
               COALESCE(v.potassio_mg, 0) AS potassio_mg,
               v.massa_total_calculada, v.qtd_ingredientes
        FROM pratos p
        JOIN vw_pratos_nutricional v ON p.id = v.prato_id
        WHERE p.desativado = 0
          AND v.qtd_ingredientes > 0
          AND v.energia_kcal IS NOT NULL
    """)).mappings().all()
    pratos = [dict(row) for row in pratos]
    mapa_pratos = {p['id']: p for p in pratos}

    # Alimentos industrializados não são pratos diretamente; são carregados
    # como fonte adicional de ingredientes. A integração mínima viável
    # documenta como unificar as fontes (seção 9).
    alimentos_ind = []
    if incluir_industrializados:
        alimentos_ind = carregar_alimentos_industrializados()

    tipos_prato_rows = db.session.execute(
        text("SELECT id, nome FROM tipos_preparacoes")
    ).mappings().all()
    tipos_prato = {row['id']: row['nome'] for row in tipos_prato_rows}

    refeicoes = db.session.execute(text("""
        SELECT tr.id, tr.nome, tr.horario_padrao
        FROM tipos_refeicao tr
        JOIN dieta_refeicoes dr ON tr.id = dr.tipo_refeicao_id
        WHERE dr.dieta_id = :did
        ORDER BY tr.id
    """), {'did': dieta_id}).mappings().all()
    refeicoes = [dict(row) for row in refeicoes]
    tipos_refeicao = {r['id']: r for r in refeicoes}
    refeicoes_ordenadas = [r['id'] for r in refeicoes]

    regras_composicao = [dict(row) for row in db.session.execute(text("""
        SELECT tipo_refeicao_id, tipo_prato_id, qtd_minima, qtd_maxima
        FROM regras_composicao
    """)).mappings().all()]

    regras_por_refeicao = defaultdict(list)
    for r in regras_composicao:
        regras_por_refeicao[r['tipo_refeicao_id']].append(r)

    restricoes_nutricionais = [dict(row) for row in db.session.execute(text("""
        SELECT nutriente, valor_minimo, valor_maximo
        FROM restricoes_nutricionais_dieta
        WHERE dieta_id = :did
    """), {'did': dieta_id}).mappings().all()]

    regras_variedade = [dict(row) for row in db.session.execute(text("""
        SELECT tipo_prato_id, dias_minimos_repeticao, frequencia_maxima_semanal
        FROM regras_variedade
    """)).mappings().all()]

    regras_elegibilidade = [dict(row) for row in db.session.execute(text("""
        SELECT atributo, valores_permitidos, operador
        FROM regras_elegibilidade_dieta
        WHERE dieta_id = :did
    """), {'did': dieta_id}).mappings().all()]

    return {
        'dieta_id': dieta_id,
        'dieta_nome': dieta_nome,
        'pratos': pratos,
        'mapa_pratos': mapa_pratos,
        'tipos_prato': tipos_prato,
        'tipos_refeicao': tipos_refeicao,
        'refeicoes_ordenadas': refeicoes_ordenadas,
        'regras_composicao': regras_composicao,
        'regras_por_refeicao': regras_por_refeicao,
        'restricoes_nutricionais': restricoes_nutricionais,
        'regras_variedade': regras_variedade,
        'regras_elegibilidade': regras_elegibilidade,
        'alimentos_industrializados': alimentos_ind,
    }


# ══════════════════════════════════════════════════════════════════
# MODELAGEM MATEMÁTICA (PuLP)
# ══════════════════════════════════════════════════════════════════

def criar_modelo_otimizacao(dados, dias=5, overrides=None, objetivo='max_energia'):
    """
    Monta o modelo de programação linear inteira.

    Parâmetros extras (plano nutricional do paciente):
      overrides: dict {nutriente: (min, max)} mesclado nas restrições
                 nutricionais (ex: energia_kcal, proteina_g, carboidrato_g,
                 lipidios_g) — faixas mais restritivas que as da dieta.
      objetivo:  'max_energia' (padrão) ou 'target' — quando há meta_kcal
                 no overrides, minimiza o desvio absoluto da meta em vez de
                 maximizar energia (importante para plano de perda de peso).
    """
    overrides = overrides or {}
    meta_kcal = overrides.get('meta_kcal')
    usar_target = objetivo == 'target' and meta_kcal is not None

    nome_problema = "Cardapio_Hospitalar_Target" if usar_target else "Cardapio_Hospitalar_Maximizar_Energia"
    problema = pulp.LpProblem(nome_problema, pulp.LpMinimize if usar_target else pulp.LpMaximize)

    pratos_ids = [p['id'] for p in dados['pratos']]
    tipos_prato_ids = list(dados['tipos_prato'].keys())
    dias_range = range(1, dias + 1)

    pratos_por_tipo = {}
    for p in dados['pratos']:
        pratos_por_tipo.setdefault(p['tipo_prato_id'], []).append(p['id'])

    refeicoes_ids = dados['refeicoes_ordenadas']
    X = pulp.LpVariable.dicts(
        "X",
        (pratos_ids, refeicoes_ids, dias_range),
        cat='Binary'
    )

    if usar_target:
        # Variáveis de desvio (positivo/negativo) por dia para minimizar
        # |energia_total_dia - meta_kcal|
        desv_pos = pulp.LpVariable.dicts("DesvPos", dias_range, lowBound=0)
        desv_neg = pulp.LpVariable.dicts("DesvNeg", dias_range, lowBound=0)
        for d in dias_range:
            soma_energia_dia = pulp.lpSum(
                p['energia_kcal'] * X[p['id']][r][d]
                for p in dados['pratos']
                for r in refeicoes_ids
            )
            problema += soma_energia_dia - desv_pos[d] + desv_neg[d] == meta_kcal, \
                f"Target_Energia_Dia{d}"
        problema += pulp.lpSum(desv_pos[d] + desv_neg[d] for d in dias_range), \
            "Minimizar_Desvio_Meta"
    else:
        # Função objetivo: Maximizar Energia Total
        problema += pulp.lpSum(
            p['energia_kcal'] * X[p['id']][r][d]
            for p in dados['pratos']
            for r in refeicoes_ids
            for d in dias_range
        ), "Maximizar_Energia_Total"

    # Um prato não pode ser usado em duas refeições no mesmo dia
    for p in dados['pratos']:
        for d in dias_range:
            problema += pulp.lpSum(X[p['id']][r][d] for r in refeicoes_ids) <= 1, \
                f"Unico_Dia{p['id']}_Dia{d}"

    # Limite máximo de pratos por dia
    for d in dias_range:
        problema += pulp.lpSum(
            X[pid][r][d]
            for pid in pratos_ids
            for r in refeicoes_ids
        ) <= 18, f"MaxPratos_Dia{d}"

    # Restrições de Composição por Refeição
    for r in refeicoes_ids:
        for regra in dados['regras_por_refeicao'].get(r, []):
            t = regra['tipo_prato_id']
            qtd_min = regra['qtd_minima'] or 0
            qtd_max = regra['qtd_maxima'] or 99

            if len(pratos_por_tipo.get(t, [])) == 0:
                continue

            for d in dias_range:
                soma = pulp.lpSum(X[pid][r][d] for pid in pratos_por_tipo.get(t, []))
                if qtd_min > 0:
                    problema += soma >= qtd_min, f"Comp_Min_R{r}_T{t}_Dia{d}"
                if qtd_max < 99:
                    problema += soma <= qtd_max, f"Comp_Max_R{r}_T{t}_Dia{d}"

    # Bloquear tipos não autorizados em cada refeição
    pares_autorizados = set()
    for regra in dados['regras_composicao']:
        pares_autorizados.add((regra['tipo_refeicao_id'], regra['tipo_prato_id']))

    for r in refeicoes_ids:
        for t in tipos_prato_ids:
            if (r, t) not in pares_autorizados:
                if len(pratos_por_tipo.get(t, [])) == 0:
                    continue
                for d in dias_range:
                    soma = pulp.lpSum(X[pid][r][d] for pid in pratos_por_tipo[t])
                    problema += soma == 0, f"Bloq_R{r}_T{t}_Dia{d}"

    # Restrições Nutricionais (da dieta base)
    # Nutrientes cobertos pelos overrides do plano são SUBSTITUÍDOS (a meta
    # individual do paciente prevalece sobre a faixa genérica da dieta)
    nutrientes_override = {n for n in overrides if n != 'meta_kcal'}
    for rest in dados['restricoes_nutricionais']:
        nutriente = rest['nutriente']
        if nutriente in nutrientes_override:
            continue
        col = COLUNAS_NUTRIENTES.get(nutriente)
        if not col:
            continue
        for d in dias_range:
            soma_nutriente = pulp.lpSum(
                p[col] * X[p['id']][r][d]
                for p in dados['pratos']
                for r in refeicoes_ids
            )
            if rest['valor_minimo'] is not None:
                problema += soma_nutriente >= rest['valor_minimo'], f"Nut_Min_{nutriente}_Dia{d}"
            if rest['valor_maximo'] is not None:
                problema += soma_nutriente <= rest['valor_maximo'], f"Nut_Max_{nutriente}_Dia{d}"

    # Overrides do plano do paciente (mesclados às restrições da dieta —
    # faixas mais restritivas valem, o solver respeita a interseção)
    for nutriente, faixa in overrides.items():
        if nutriente == 'meta_kcal':
            continue
        col = COLUNAS_NUTRIENTES.get(nutriente)
        if not col:
            continue
        vmin, vmax = faixa
        for d in dias_range:
            soma_nutriente = pulp.lpSum(
                p[col] * X[p['id']][r][d]
                for p in dados['pratos']
                for r in refeicoes_ids
            )
            if vmin is not None:
                problema += soma_nutriente >= vmin, f"Override_Min_{nutriente}_Dia{d}"
            if vmax is not None:
                problema += soma_nutriente <= vmax, f"Override_Max_{nutriente}_Dia{d}"

    # Restrições de Elegibilidade
    for regra in dados['regras_elegibilidade']:
        valores = json.loads(regra['valores_permitidos'])
        attr = MAP_ATRIBUTOS.get(regra['atributo'], regra['atributo'])
        operador = regra['operador']
        for d in dias_range:
            for r in refeicoes_ids:
                pratos_bloqueados = [
                    p['id'] for p in dados['pratos']
                    if not ((operador == 'IN' and p.get(attr) in valores) or
                            (operador == 'NOT IN' and p.get(attr) not in valores))
                ]
                for pid in pratos_bloqueados:
                    problema += X[pid][r][d] == 0, f"Eleg_{attr}_R{r}_P{pid}_Dia{d}"

    return problema, X, dados


# ══════════════════════════════════════════════════════════════════
# RESOLUÇÃO E EXTRAÇÃO DE RESULTADOS
# ══════════════════════════════════════════════════════════════════

def resolver_e_extrair(problema, X, dados, dias=5):
    """Resolve o modelo PuLP e retorna dados estruturados."""

    status = problema.solve(pulp.PULP_CBC_CMD(timeLimit=180, gapRel=0.1, msg=0))

    if status not in (1, 0):
        return {
            'status': pulp.LpStatus[status],
            'cardapio': [],
            'metricas': {'erro': 'Modelo inviável. Verifique as restrições.'}
        }

    cardapio_resultado = []
    totais_nutrientes = {'energia_kcal': 0.0, 'proteina_g': 0.0, 'lipidios_g': 0.0,
                         'carboidrato_g': 0.0, 'sodio_mg': 0.0}

    for d in range(1, dias + 1):
        dia_entry = {'dia': d, 'refeicoes': []}
        for r in dados['refeicoes_ordenadas']:
            tipos_na_refeicao = defaultdict(list)
            for p in dados['pratos']:
                if pulp.value(X[p['id']][r][d]) == 1:
                    tipo_nome = dados['tipos_prato'].get(p['tipo_prato_id'], f"Tipo{p['tipo_prato_id']}")
                    porcao = p.get('porcao_padrao_g')
                    prato_info = {
                        'id': p['id'],
                        'nome': p['nome'],
                        'porcao_g': float(porcao) if porcao else None,
                        'energia_kcal': float(p.get('energia_kcal', 0)),
                        'proteina_g': float(p.get('proteina_g', 0)),
                    }
                    tipos_na_refeicao[tipo_nome].append(prato_info)
                    for n in totais_nutrientes:
                        totais_nutrientes[n] += float(p.get(n, 0) or 0)

            if tipos_na_refeicao:
                ref_entry = {
                    'refeicao_id': r,
                    'refeicao_nome': dados['tipos_refeicao'][r]['nome'],
                    'horario': dados['tipos_refeicao'][r].get('horario_padrao', ''),
                    'tipos': [
                        {'tipo': tipo_nome, 'pratos': pratos_list}
                        for tipo_nome, pratos_list in tipos_na_refeicao.items()
                    ]
                }
                dia_entry['refeicoes'].append(ref_entry)

        if dia_entry['refeicoes']:
            cardapio_resultado.append(dia_entry)

    metricas = {
        'energia_total_kcal': round(totais_nutrientes['energia_kcal'], 1),
        'media_energia_diaria_kcal': round(totais_nutrientes['energia_kcal'] / dias, 1),
        'media_proteina_diaria_g': round(totais_nutrientes['proteina_g'] / dias, 1),
        'media_lipidios_diaria_g': round(totais_nutrientes['lipidios_g'] / dias, 1),
        'media_carboidrato_diaria_g': round(totais_nutrientes['carboidrato_g'] / dias, 1),
        'media_sodio_diario_mg': round(totais_nutrientes['sodio_mg'] / dias, 1),
        'total_pratos_selecionados': sum(
            len(t['pratos'])
            for dia in cardapio_resultado
            for ref in dia['refeicoes']
            for t in ref['tipos']
        ),
    }

    return {
        'status': pulp.LpStatus[status],
        'cardapio': cardapio_resultado,
        'metricas': metricas,
    }


# ══════════════════════════════════════════════════════════════════
# ROTAS
# ══════════════════════════════════════════════════════════════════

@otimizacao_bp.route('/otimizacao')
def pagina_otimizacao():
    """Página com formulário para o usuário informar os parâmetros."""
    return render_template('otimizacao_form.html')


@otimizacao_bp.route('/api/otimizacao/executar', methods=['POST'])
def executar_otimizacao():
    """Recebe parâmetros, executa o PuLP e retorna o cardápio."""
    data = request.get_json() or {}

    dieta_nome = data.get('dieta', 'LIVRE').strip().upper()
    dias = int(data.get('dias', 5))
    funcao_objetivo = data.get('objetivo', 'max_energia').strip().lower()
    formato = data.get('formato', 'json').strip().lower()

    if dias < 1 or dias > 30:
        return jsonify({'erro': 'Dias deve estar entre 1 e 30.'}), 400

    try:
        dados = carregar_dados_otimizacao(dieta_nome)
    except ValueError as e:
        return jsonify({'erro': str(e)}), 404

    problema, X, dados = criar_modelo_otimizacao(dados, dias=dias)
    resultado = resolver_e_extrair(problema, X, dados, dias=dias)

    if formato == 'html':
        return render_template(
            'otimizacao_retrato.html',
            dieta=dieta_nome,
            dias=dias,
            resultado=resultado
        )
    elif formato == 'html_paisagem':
        refeicoes_unicas = []
        for dia in resultado['cardapio']:
            for ref in dia['refeicoes']:
                nome = ref['refeicao_nome']
                if nome not in refeicoes_unicas:
                    refeicoes_unicas.append(nome)
        return render_template(
            'otimizacao_paisagem.html',
            dieta=dieta_nome,
            dias=dias,
            resultado=resultado,
            refeicoes_unicas=refeicoes_unicas,
        )
    else:
        return jsonify({
            'dieta': dieta_nome,
            'dias': dias,
            'objetivo': funcao_objetivo,
            'resultado': resultado,
        })
