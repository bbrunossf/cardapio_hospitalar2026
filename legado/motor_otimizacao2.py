"""
Épico 3 - Opção 1: Motor de Otimização (Core)
Gera um cardápio de 5 dias maximizando energia (kcal)
usando Programação Linear Inteira (PuLP) e os dados do SQLite.
Adaptado para schema v5 (prato_composicao + vw_pratos_nutricional).
"""

import sqlite3
import json
import pulp
import os

# Mapeamento de atributos sensoriais das regras de elegibilidade para colunas do banco
# (a coluna da cor é 'cor_predominante', mas as regras usam 'cor')
MAP_ATRIBUTOS = {
    'cor': 'cor_predominante',
    'consistencia': 'consistencia',
    'textura': 'textura',
    'temperatura_servimento': 'temperatura_servimento',
}

# ==========================================
# 1. CONEXÃO E CARREGAMENTO DE DADOS
# ==========================================

def carregar_dados(db_path="cardapio_hospitalar.db", dieta_nome="LIVRE"):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print(f"\n[1/6] Carregando dados para a dieta: {dieta_nome}...")

    # Buscar ID da dieta
    cursor.execute("SELECT id FROM dietas WHERE nome = ?", (dieta_nome,))
    dieta = cursor.fetchone()
    if not dieta:
        raise ValueError(f"Dieta '{dieta_nome}' não encontrada no banco.")
    dieta_id = dieta['id']

    # Buscar Pratos + seus atributos nutricionais (via view)
    # Apenas pratos COM composição e com dados nutricionais válidos
    cursor.execute("""
        SELECT p.id, p.nome, p.tipo_prato_id, p.cor_predominante,
               p.consistencia, p.textura, p.temperatura_servimento,
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
    """)
    pratos = [dict(row) for row in cursor.fetchall()]
    print(f"   -> {len(pratos)} pratos carregados (com composição).")

    # Buscar Tipos de Prato (tipos_preparacoes = BC1, RC, MD, etc.)
    cursor.execute("SELECT id, nome FROM tipos_preparacoes")
    tipos_prato = {row['id']: row['nome'] for row in cursor.fetchall()}

    # Buscar Tipos de Refeição
    cursor.execute("SELECT id, nome FROM tipos_refeicao")
    tipos_refeicao = {row['id']: row['nome'] for row in cursor.fetchall()}

    # Buscar Regras de Composição
    cursor.execute("""
        SELECT rc.tipo_refeicao_id, rc.tipo_prato_id, rc.qtd_minima, rc.qtd_maxima
        FROM regras_composicao rc
        ORDER BY rc.tipo_refeicao_id, rc.tipo_prato_id
    """)
    regras_composicao = [dict(row) for row in cursor.fetchall()]

    # Buscar Restrições Nutricionais da Dieta
    cursor.execute("""
        SELECT nutriente, valor_minimo, valor_maximo
        FROM restricoes_nutricionais_dieta
        WHERE dieta_id = ?
    """, (dieta_id,))
    restricoes_nutricionais = [dict(row) for row in cursor.fetchall()]
    print(f"   -> {len(restricoes_nutricionais)} restrições nutricionais carregadas.")

    # Buscar Regras de Variedade
    cursor.execute("""
        SELECT tipo_prato_id, dias_minimos_repeticao, frequencia_maxima_semanal
        FROM regras_variedade
    """)
    regras_variedade = [dict(row) for row in cursor.fetchall()]

    # Buscar Regras de Elegibilidade (filtros por consistência, cor etc.)
    cursor.execute("""
        SELECT atributo, valores_permitidos, operador
        FROM regras_elegibilidade_dieta
        WHERE dieta_id = ?
    """, (dieta_id,))
    regras_elegibilidade = [dict(row) for row in cursor.fetchall()]

    conn.close()
    return {
        'dieta_id': dieta_id,
        'pratos': pratos,
        'tipos_prato': tipos_prato,
        'tipos_refeicao': tipos_refeicao,
        'regras_composicao': regras_composicao,
        'restricoes_nutricionais': restricoes_nutricionais,
        'regras_variedade': regras_variedade,
        'regras_elegibilidade': regras_elegibilidade,
    }


# ==========================================
# 2. MODELAGEM MATEMÁTICA (PuLP)
# ==========================================

def criar_modelo_otimizacao(dados, dias=5):
    print(f"\n[2/6] Montando modelo matemático para {dias} dias...")

    problema = pulp.LpProblem("Cardapio_Hospitalar_Maximizar_Energia", pulp.LpMaximize)

    # Conjuntos de índices
    pratos_ids = [p['id'] for p in dados['pratos']]
    tipos_prato_ids = list(dados['tipos_prato'].keys())
    dias_range = range(1, dias + 1)

    # Mapa: tipo_prato_id -> lista de IDs de pratos daquele tipo
    pratos_por_tipo = {}
    for p in dados['pratos']:
        pratos_por_tipo.setdefault(p['tipo_prato_id'], []).append(p['id'])

    # --- VARIÁVEIS DE DECISÃO (Xpd) ---
    # X[p, d] = 1 se o prato 'p' for servido no dia 'd'
    X = pulp.LpVariable.dicts("X", (pratos_ids, dias_range), cat='Binary')

    # --- FUNÇÃO OBJETIVO: Maximizar Energia Total ---
    problema += pulp.lpSum(
        p['energia_kcal'] * X[p['id']][d]
        for p in dados['pratos']
        for d in dias_range
    ), "Maximizar_Energia_Total"

    # --- RESTRIÇÕES ---

    # 3.1. Limite máximo de pratos por dia
    print("   -> Adicionando limites de pratos por dia...")
    for d in dias_range:
        problema += pulp.lpSum(X[pid][d] for pid in pratos_ids) <= 18, f"MaxPratos_Dia{d}"

    # 3.2. Restrições de Composição
    # Agrega por tipo_prato: soma os mins e maxs de todas as refeições do dia
    print("   -> Adicionando restrições de composição...")
    # Calcular demanda total por tipo_prato no dia (somando todas as refeições)
    demanda_min_por_tipo = {}
    demanda_max_por_tipo = {}
    for regra in dados['regras_composicao']:
        t = regra['tipo_prato_id']
        demanda_min_por_tipo[t] = demanda_min_por_tipo.get(t, 0) + (regra['qtd_minima'] or 0)
        demanda_max_por_tipo[t] = demanda_max_por_tipo.get(t, 0) + (regra['qtd_maxima'] or 0)

    for t, qtd_min in demanda_min_por_tipo.items():
        if qtd_min == 0:
            continue
        nome_tp = dados['tipos_prato'].get(t, f"Tipo{t}")
        qtd_disponivel = len(pratos_por_tipo.get(t, []))
        if qtd_disponivel == 0:
            print(f"   ⚠️  Tipo '{nome_tp}' precisa de {qtd_min} prato(s) mas há 0 disponíveis — pulando restrição")
            continue
        for d in dias_range:
            soma = pulp.lpSum(X[pid][d] for pid in pratos_por_tipo.get(t, []))
            problema += soma >= qtd_min, f"Comp_Min_Tipo{t}_Dia{d}"
            # Limite máximo razoável por tipo por dia (min + 2)
            problema += soma <= qtd_min + 2, f"Comp_Max_Tipo{t}_Dia{d}"

    # 3.3. Garantir número mínimo de pratos por dia
    total_min_dia = sum(demanda_min_por_tipo.values())
    for d in dias_range:
        problema += pulp.lpSum(X[pid][d] for pid in pratos_ids) >= total_min_dia, f"MinPratos_Dia{d}"

    # 3.4. Restrições Nutricionais
    print("   -> Adicionando restrições nutricionais...")
    colunas_nutrientes = {
        'energia': 'energia_kcal', 'proteina': 'proteina_g', 'lipidios': 'lipidios_g',
        'carboidrato': 'carboidrato_g', 'fibra': 'fibra_alimentar_g', 'sodio': 'sodio_mg',
        'potassio': 'potassio_mg',
    }

    for rest in dados['restricoes_nutricionais']:
        nutriente = rest['nutriente']
        col = colunas_nutrientes.get(nutriente)
        if not col:
            print(f"   Aviso: nutriente '{nutriente}' não reconhecido, ignorado.")
            continue

        for d in dias_range:
            soma_nutriente = pulp.lpSum(
                p[col] * X[p['id']][d]
                for p in dados['pratos']
            )
            if rest['valor_minimo'] is not None:
                problema += soma_nutriente >= rest['valor_minimo'], f"Nut_Min_{nutriente}_Dia{d}"
            if rest['valor_maximo'] is not None:
                problema += soma_nutriente <= rest['valor_maximo'], f"Nut_Max_{nutriente}_Dia{d}"

    # 3.5. Restrições de Elegibilidade (consistência/cor por dieta)
    for regra in dados['regras_elegibilidade']:
        valores = json.loads(regra['valores_permitidos'])
        attr = MAP_ATRIBUTOS.get(regra['atributo'], regra['atributo'])
        operador = regra['operador']

        for d in dias_range:
            pratos_bloqueados = [
                p['id'] for p in dados['pratos']
                if not ((operador == 'IN' and p.get(attr) in valores) or
                        (operador == 'NOT IN' and p.get(attr) not in valores))
            ]
            for pid in pratos_bloqueados:
                problema += X[pid][d] == 0, f"Eleg_{attr}_{pid}_Dia{d}"

    # 3.6. Restrições de Variedade (desabilitadas por enquanto — conflitam com composição)
    # for i, regra_v in enumerate(dados['regras_variedade']):
    #     ...

    return problema, X, dados


# ==========================================
# 3. RESOLUÇÃO E EXIBIÇÃO
# ==========================================

def resolver_e_exibir(problema, X, dados, dias=5):
    print(f"\n[3/6] Resolvendo o modelo com o solver CBC...")

    status = problema.solve(pulp.PULP_CBC_CMD(timeLimit=180, gapRel=0.1, msg=1))

    print(f"   -> Status: {pulp.LpStatus[status]}")

    if status not in (1, 0):  # 1 = Optimal, 0 = Undefined (mas encontrou solução)
        print("\n[ERRO] O modelo é INVIÁVEL. Verifique as restrições.")
        # Diagnóstico rápido
        print("\nDiagnóstico:")
        for nome, constraint in problema.constraints.items():
            if 'Comp_Min' in nome:
                try:
                    value = pulp.value(constraint)
                    if value and value < -0.5:
                        print(f"   ❌ {nome}: violada (folga={value:.1f})")
                except:
                    pass
        return

    print(f"\n[4/6] Extraindo solução...")

    cardapio = {d: {} for d in range(1, dias + 1)}
    totais_nutrientes = {n: 0.0 for n in ['energia_kcal', 'proteina_g', 'lipidios_g', 'carboidrato_g', 'sodio_mg']}

    for d in range(1, dias + 1):
        for p in dados['pratos']:
            if pulp.value(X[p['id']][d]) == 1:
                tipo_nome = dados['tipos_prato'].get(p['tipo_prato_id'], f"Tipo{p['tipo_prato_id']}")
                # Garantir chave única: tipo + sufixo se houver duplicata
                chave = tipo_nome
                contador = 1
                while chave in cardapio[d]:
                    contador += 1
                    chave = f"{tipo_nome}#{contador}"
                cardapio[d][chave] = p['nome']
                for n in totais_nutrientes:
                    totais_nutrientes[n] += p.get(n, 0) or 0

    print(f"\n[5/6] CARDÁPIO GERADO ({dias} Dias) - Dieta: LIVRE")
    print("=" * 60)
    for d in range(1, dias + 1):
        print(f"\n--- DIA {d} ---")
        for tipo_nome, prato_nome in cardapio[d].items():
            print(f"  [{tipo_nome}]: {prato_nome}")

    energia_total = totais_nutrientes['energia_kcal']
    print(f"\n[6/6] MÉTRICAS FINAIS")
    print(f"   -> Total de energia no período: {energia_total:.0f} kcal")
    print(f"   -> Média diária de energia: {energia_total/dias:.0f} kcal")
    print(f"   -> Média proteína/dia: {totais_nutrientes['proteina_g']/dias:.1f}g")
    print(f"   -> Média lipídios/dia: {totais_nutrientes['lipidios_g']/dias:.1f}g")
    print(f"   -> Média carboidrato/dia: {totais_nutrientes['carboidrato_g']/dias:.1f}g")
    print(f"   -> Média sódio/dia: {totais_nutrientes['sodio_mg']/dias:.0f}mg")
    print("=" * 60)


# ==========================================
# MAIN
# ==========================================

if __name__ == "__main__":
    db_path = os.path.join(os.path.dirname(__file__), "cardapio_hospitalar.db")
    dados = carregar_dados(db_path, dieta_nome="LIVRE")
    problema, X, dados = criar_modelo_otimizacao(dados, dias=5)
    resolver_e_exibir(problema, X, dados, dias=5)