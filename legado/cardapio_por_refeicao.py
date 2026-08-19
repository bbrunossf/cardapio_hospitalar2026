"""
Cardápio por Refeição
Gera um cardápio de 5 dias maximizando energia (kcal)
e exibe o resultado organizado por:
  Dia → Refeição → Tipo de Prato → Prato
Adaptado para schema v5 (prato_composicao + vw_pratos_nutricional).
"""
import sqlite3
import json
import pulp
import os
from collections import defaultdict


# ==========================================
# 1. CONEXÃO E CARREGAMENTO DE DADOS
# ==========================================

def carregar_dados(db_path="cardapio_hospitalar.db", dieta_nome="LIVRE"):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print(f"\n[1/7] Carregando dados para a dieta: {dieta_nome}...")

    # Buscar ID da dieta
    cursor.execute("SELECT id FROM dietas WHERE nome = ?", (dieta_nome,))
    dieta = cursor.fetchone()
    if not dieta:
        raise ValueError(f"Dieta '{dieta_nome}' não encontrada no banco.")
    dieta_id = dieta['id']

    # Buscar Pratos + atributos nutricionais (via view)
    cursor.execute("""
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
    """)
    pratos = [dict(row) for row in cursor.fetchall()]

    # Mapa de pratos
    mapa_pratos = {p['id']: p for p in pratos}

    # Buscar Tipos de Prato
    cursor.execute("SELECT id, nome FROM tipos_preparacoes")
    tipos_prato = {row['id']: row['nome'] for row in cursor.fetchall()}

    # Buscar Tipos de Refeição (apenas as servidas nesta dieta)
    cursor.execute("""
        SELECT tr.id, tr.nome, tr.horario_padrao
        FROM tipos_refeicao tr
        JOIN dieta_refeicoes dr ON tr.id = dr.tipo_refeicao_id
        WHERE dr.dieta_id = ?
        ORDER BY tr.id
    """, (dieta_id,))
    refeicoes = [dict(row) for row in cursor.fetchall()]
    tipos_refeicao = {r['id']: r for r in refeicoes}
    refeicoes_ordenadas = [r['id'] for r in refeicoes]

    print(f"   -> {len(pratos)} pratos, {len(refeicoes)} refeições carregados (filtradas pela dieta '{dieta_nome}').")

    # Buscar Regras de Composição
    cursor.execute("""
        SELECT rc.tipo_refeicao_id, rc.tipo_prato_id, rc.qtd_minima, rc.qtd_maxima
        FROM regras_composicao rc
        ORDER BY rc.tipo_refeicao_id, rc.tipo_prato_id
    """)
    regras_composicao = [dict(row) for row in cursor.fetchall()]

    # Agrupar regras por refeição
    regras_por_refeicao = defaultdict(list)
    for r in regras_composicao:
        regras_por_refeicao[r['tipo_refeicao_id']].append(r)

    # Buscar Restrições Nutricionais da Dieta
    cursor.execute("""
        SELECT nutriente, valor_minimo, valor_maximo
        FROM restricoes_nutricionais_dieta
        WHERE dieta_id = ?
    """, (dieta_id,))
    restricoes_nutricionais = [dict(row) for row in cursor.fetchall()]

    # Buscar Regras de Variedade
    cursor.execute("""
        SELECT tipo_prato_id, dias_minimos_repeticao, frequencia_maxima_semanal
        FROM regras_variedade
    """)
    regras_variedade = [dict(row) for row in cursor.fetchall()]

    # Buscar Regras de Elegibilidade
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
        'mapa_pratos': mapa_pratos,
        'tipos_prato': tipos_prato,
        'tipos_refeicao': tipos_refeicao,
        'refeicoes_ordenadas': refeicoes_ordenadas,
        'regras_composicao': regras_composicao,
        'regras_por_refeicao': regras_por_refeicao,
        'restricoes_nutricionais': restricoes_nutricionais,
        'regras_variedade': regras_variedade,
        'regras_elegibilidade': regras_elegibilidade,
    }


# ==========================================
# 2. MODELAGEM MATEMÁTICA (PuLP)
# ==========================================

def criar_modelo_otimizacao(dados, dias=5):
    print(f"\n[2/7] Montando modelo matemático para {dias} dias...")

    problema = pulp.LpProblem("Cardapio_Hospitalar_Maximizar_Energia", pulp.LpMaximize)

    pratos_ids = [p['id'] for p in dados['pratos']]
    tipos_prato_ids = list(dados['tipos_prato'].keys())
    dias_range = range(1, dias + 1)

    # Mapa: tipo_prato_id -> lista de IDs de pratos daquele tipo
    pratos_por_tipo = {}
    for p in dados['pratos']:
        pratos_por_tipo.setdefault(p['tipo_prato_id'], []).append(p['id'])

    # --- VARIÁVEIS DE DECISÃO ---
    # X[p, r, d] = 1 se o prato 'p' for servido na refeição 'r' no dia 'd'
    refeicoes_ids = dados['refeicoes_ordenadas']
    X = pulp.LpVariable.dicts(
        "X",
        (pratos_ids, refeicoes_ids, dias_range),
        cat='Binary'
    )

    # --- FUNÇÃO OBJETIVO: Maximizar Energia Total ---
    problema += pulp.lpSum(
        p['energia_kcal'] * X[p['id']][r][d]
        for p in dados['pratos']
        for r in refeicoes_ids
        for d in dias_range
    ), "Maximizar_Energia_Total"

    # --- RESTRIÇÕES ---

    # 3.1. Um prato não pode ser usado em duas refeições no mesmo dia
    print("   -> Garantindo unicidade de pratos por dia...")
    for p in dados['pratos']:
        for d in dias_range:
            problema += pulp.lpSum(X[p['id']][r][d] for r in refeicoes_ids) <= 1, \
                f"Unico_Dia{p['id']}_Dia{d}"

    # 3.2. Limite máximo de pratos por dia
    print("   -> Adicionando limites de pratos por dia...")
    for d in dias_range:
        problema += pulp.lpSum(
            X[pid][r][d]
            for pid in pratos_ids
            for r in refeicoes_ids
        ) <= 18, f"MaxPratos_Dia{d}"

    # 3.3. Restrições de Composição por REFEIÇÃO
    print("   -> Adicionando regras de composição por refeição...")
    for r in refeicoes_ids:
        for regra in dados['regras_por_refeicao'].get(r, []):
            t = regra['tipo_prato_id']
            qtd_min = regra['qtd_minima'] or 0
            qtd_max = regra['qtd_maxima'] or 99
            nome_ref = dados['tipos_refeicao'][r]['nome']
            nome_tp = dados['tipos_prato'].get(t, f"Tipo{t}")

            if len(pratos_por_tipo.get(t, [])) == 0:
                if qtd_min > 0:
                    print(f"   ⚠️  {nome_ref} precisa de {qtd_min}x '{nome_tp}' mas há 0 pratos — pulando")
                continue

            for d in dias_range:
                soma = pulp.lpSum(
                    X[pid][r][d]
                    for pid in pratos_por_tipo.get(t, [])
                )
                if qtd_min > 0:
                    problema += soma >= qtd_min, f"Comp_Min_R{r}_T{t}_Dia{d}"
                if qtd_max < 99:
                    problema += soma <= qtd_max, f"Comp_Max_R{r}_T{t}_Dia{d}"

    # 3.4. Bloquear tipos não autorizados em cada refeição
    print("   -> Bloqueando tipos não autorizados por refeição...")
    # Montar conjunto de pares (refeição, tipo) autorizados
    pares_autorizados = set()
    for regra in dados['regras_composicao']:
        pares_autorizados.add((regra['tipo_refeicao_id'], regra['tipo_prato_id']))

    # Para cada par NÃO autorizado, forçar soma = 0
    restricoes_adicionadas = 0
    for r in refeicoes_ids:
        nome_ref = dados['tipos_refeicao'][r]['nome']
        for t in tipos_prato_ids:
            if (r, t) not in pares_autorizados:
                if len(pratos_por_tipo.get(t, [])) == 0:
                    continue
                for d in dias_range:
                    soma = pulp.lpSum(X[pid][r][d] for pid in pratos_por_tipo[t])
                    problema += soma == 0, f"Bloq_R{r}_T{t}_Dia{d}"
                    restricoes_adicionadas += 1

    print(f"   -> {restricoes_adicionadas} restrições de bloqueio adicionadas.")

    # 3.5. Restrições Nutricionais
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
                p[col] * X[p['id']][r][d]
                for p in dados['pratos']
                for r in refeicoes_ids
            )
            if rest['valor_minimo'] is not None:
                problema += soma_nutriente >= rest['valor_minimo'], f"Nut_Min_{nutriente}_Dia{d}"
            if rest['valor_maximo'] is not None:
                problema += soma_nutriente <= rest['valor_maximo'], f"Nut_Max_{nutriente}_Dia{d}"

    # 3.5. Restrições de Elegibilidade
    for regra in dados['regras_elegibilidade']:
        valores = json.loads(regra['valores_permitidos'])
        attr = regra['atributo']
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


# ==========================================
# 3. RESOLUÇÃO E EXIBIÇÃO POR REFEIÇÃO
# ==========================================

def resolver_e_exibir(problema, X, dados, dias=5):
    print(f"\n[3/7] Resolvendo o modelo com o solver CBC...")

    status = problema.solve(pulp.PULP_CBC_CMD(timeLimit=180, gapRel=0.1, msg=1))

    print(f"   -> Status: {pulp.LpStatus[status]}")

    if status not in (1, 0):
        print("\n[ERRO] O modelo é INVIÁVEL. Verifique as restrições.")
        for nome, constraint in problema.constraints.items():
            if 'Comp_Min' in nome:
                try:
                    value = pulp.value(constraint)
                    if value and value < -0.5:
                        print(f"   ❌ {nome}: violada")
                except:
                    pass
        return

    print(f"\n[4/7] Extraindo solução...")

    # Coletar resultados: cardapio[d][r][tipo_nome] = [prato_nome, ...]
    cardapio = {}
    for d in range(1, dias + 1):
        cardapio[d] = {}
        for r in dados['refeicoes_ordenadas']:
            cardapio[d][r] = defaultdict(list)

    totais_nutrientes = {n: 0.0 for n in ['energia_kcal', 'proteina_g', 'lipidios_g', 'carboidrato_g', 'sodio_mg']}

    for p in dados['pratos']:
        for r in dados['refeicoes_ordenadas']:
            for d in range(1, dias + 1):
                if pulp.value(X[p['id']][r][d]) == 1:
                    tipo_nome = dados['tipos_prato'].get(p['tipo_prato_id'], f"Tipo{p['tipo_prato_id']}")
                    porcao = p.get('porcao_padrao_g')
                    label_porcao = f" ({float(porcao):.0f}g)" if porcao else ""
                    cardapio[d][r][tipo_nome].append(f"{p['nome']}{label_porcao}")
                    for n in totais_nutrientes:
                        totais_nutrientes[n] += p.get(n, 0) or 0

    # ─── EXIBIÇÃO ─────────────────────────────────────────────────
    print(f"\n[5/7] CARDÁPIO GERADO ({dias} Dias) - Dieta: LIVRE")
    print("=" * 70)

    for d in range(1, dias + 1):
        print(f"\n{'─' * 35}  DIA {d}  {'─' * 35}")
        tem_pratos = False

        for r in dados['refeicoes_ordenadas']:
            ref_nome = dados['tipos_refeicao'][r]['nome']
            horario = dados['tipos_refeicao'][r].get('horario_padrao', '')

            # Verificar se esta refeição tem algo no cardápio
            pratos_na_ref = cardapio[d][r]
            if not any(pratos_na_ref.values()):
                continue

            tem_pratos = True
            print(f"\n  🕐 {ref_nome} ({horario})")
            print(f"  {'─' * 50}")

            for tipo_nome, pratos_list in pratos_na_ref.items():
                for nome_prato in pratos_list:
                    print(f"    [{tipo_nome}] {nome_prato}")

        if not tem_pratos:
            print("  (sem pratos selecionados)")

    # ─── MÉTRICAS ─────────────────────────────────────────────────
    energia_total = totais_nutrientes['energia_kcal']
    print(f"\n{'=' * 70}")
    print(f"[6/7] MÉTRICAS FINAIS")
    print(f"   -> Total de energia no período: {energia_total:.0f} kcal")
    print(f"   -> Média diária de energia: {energia_total / dias:.0f} kcal")
    print(f"   -> Média proteína/dia: {totais_nutrientes['proteina_g'] / dias:.1f}g")
    print(f"   -> Média lipídios/dia: {totais_nutrientes['lipidios_g'] / dias:.1f}g")
    print(f"   -> Média carboidrato/dia: {totais_nutrientes['carboidrato_g'] / dias:.1f}g")
    print(f"   -> Média sódio/dia: {totais_nutrientes['sodio_mg'] / dias:.0f}mg")

    # Resumo por refeição
    print(f"\n[7/7] RESUMO DE PRATOS POR REFEIÇÃO (média por dia)")
    for r in dados['refeicoes_ordenadas']:
        ref_nome = dados['tipos_refeicao'][r]['nome']
        total_pratos = sum(
            len(cardapio[d][r][t])
            for d in range(1, dias + 1)
            for t in cardapio[d][r]
        )
        media = total_pratos / dias
        if media > 0:
            print(f"   {ref_nome}: ~{media:.0f} pratos/dia")

    print("=" * 70)


# ==========================================
# MAIN
# ==========================================

if __name__ == "__main__":
    db_path = os.path.join(os.path.dirname(__file__), "cardapio_hospitalar.db")
    dados = carregar_dados(db_path, dieta_nome="LIVRE")
    problema, X, dados = criar_modelo_otimizacao(dados, dias=5)
    resolver_e_exibir(problema, X, dados, dias=5)
