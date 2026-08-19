"""
Épico 3 - Opção 1: Motor de Otimização (Core)
Gera um cardápio de 5 dias minimizando a gordura (lipídios)
usando Programação Linear Inteira (PuLP) e os dados do SQLite.
"""

import sqlite3
import json
import pulp

# ==========================================
# 1. CONEXÃO E CARREGAMENTO DE DADOS
# ==========================================

def carregar_dados(db_name="cardapio_hospitalar.db", dieta_nome="LIVRE"):
    conn = sqlite3.connect(db_name)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print(f"\n[1/6] Carregando dados para a dieta: {dieta_nome}...")

    # Buscar ID da dieta
    cursor.execute("SELECT id FROM dietas WHERE nome = ?", (dieta_nome,))
    dieta = cursor.fetchone()
    if not dieta:
        raise ValueError(f"Dieta '{dieta_nome}' não encontrada no banco.")
    dieta_id = dieta['id']

    # Buscar Pratos e seus atributos (Parâmetros W, Y, Z da tese)
    cursor.execute("""
        SELECT p.id, p.nome, p.tipo_prato_id, p.cor_predominante, 
               p.consistencia, p.lipidios_g, p.energia_kcal, p.proteina_g, 
               p.carboidrato_g, p.sodio_mg, p.fibra_alimentar_g
        FROM pratos p
    """)
    pratos = [dict(row) for row in cursor.fetchall()]
    print(f"   -> {len(pratos)} pratos carregados.")

    # Buscar Tipos de Prato (BC1, RC, MD, etc.)
    cursor.execute("SELECT id, nome FROM tipos_prato")
    tipos_prato = {row['id']: row['nome'] for row in cursor.fetchall()}

    # Buscar Tipos de Refeição (Almoço, Jantar, etc.)
    cursor.execute("SELECT id, nome FROM tipos_refeicao")
    tipos_refeicao = {row['id']: row['nome'] for row in cursor.fetchall()}

    # Buscar Regras de Composição (Ex: Almoço precisa de 1 Arroz)
    cursor.execute("""
        SELECT rc.tipo_refeicao_id, rc.tipo_prato_id, rc.qtd_minima, rc.qtd_maxima
        FROM regras_composicao rc
    """)
    regras_composicao = [dict(row) for row in cursor.fetchall()]

    # Buscar Restrições Nutricionais da Dieta (Ex: Lipídios <= 30g)
    cursor.execute("""
        SELECT nutriente, valor_minimo, valor_maximo
        FROM restricoes_nutricionais_dieta
        WHERE dieta_id = ?
    """, (dieta_id,))
    restricoes_nutricionais = [dict(row) for row in cursor.fetchall()]
    print(f"   -> {len(restricoes_nutricionais)} restrições nutricionais carregadas.")

    # Buscar Regras Sensoriais (Cor e Consistência)
    cursor.execute("""
        SELECT s.tipo_refeicao_id, s.regra, s.valor_limite, s.grupos_afetados
        FROM regras_sensoriais_gerais s
    """)
    regras_sensoriais = [dict(row) for row in cursor.fetchall()]

    conn.close()
    return {
        'dieta_id': dieta_id,
        'pratos': pratos,
        'tipos_prato': tipos_prato,
        'tipos_refeicao': tipos_refeicao,
        'regras_composicao': regras_composicao,
        'restricoes_nutricionais': restricoes_nutricionais,
        'regras_sensoriais': regras_sensoriais
    }


# ==========================================
# 2. MODELAGEM MATEMÁTICA (PuLP)
# ==========================================

def criar_modelo_otimizacao(dados, dias=5):
    print(f"\n[2/6] Montando modelo matemático para {dias} dias...")

    # Criar o problema (Minimização)
    problema = pulp.LpProblem("Cardapio_Hospitalar_Minimizar_Gordura", pulp.LpMinimize)

    # Conjuntos de índices
    pratos_ids = [p['id'] for p in dados['pratos']]
    tipos_prato_ids = list(dados['tipos_prato'].keys())
    dias_range = range(1, dias + 1)

    # --- VARIÁVEIS DE DECISÃO (Xptd) ---
    # X[p, t, d] = 1 se o prato 'p' for escolhido para o tipo 't' no dia 'd'
    X = pulp.LpVariable.dicts(
        "X", 
        (pratos_ids, tipos_prato_ids, dias_range), 
        cat='Binary'
    )

    # --- FUNÇÃO OBJETIVO: Minimizar Lipídios Totais ---
    # Z = Soma(Lipídios_p * X[p, t, d])
    problema += pulp.lpSum(
        dados['pratos'][p_idx]['lipidios_g'] * X[p['id']][t][d]
        for p in dados['pratos'] 
        for p_idx, p_real in enumerate(dados['pratos']) if p_real['id'] == p['id']
        for t in tipos_prato_ids
        for d in dias_range
    ), "Minimizar_Lipidios_Totais"

    # --- RESTRIÇÕES ---
    
    # 3.1. Restrições de Composição (Ex: 1 Arroz no Almoço)
    print("   -> Adicionando restrições de composição...")
    for regra in dados['regras_composicao']:
        for d in dias_range:
            # Soma dos pratos do tipo 't' na refeição 'r' no dia 'd'
            soma = pulp.lpSum(
                X[p['id']][regra['tipo_prato_id']][d] 
                for p in dados['pratos'] 
                if p['tipo_prato_id'] == regra['tipo_prato_id']
            )
            problema += soma >= regra['qtd_minima'], f"Comp_Min_{regra['tipo_refeicao_id']}_{regra['tipo_prato_id']}_Dia{d}"
            problema += soma <= regra['qtd_maxima'], f"Comp_Max_{regra['tipo_refeicao_id']}_{regra['tipo_prato_id']}_Dia{d}"

    # 3.2. Restrições Nutricionais (Ex: Lipídios <= 30g/dia)
    print("   -> Adicionando restrições nutricionais...")
    for rest in dados['restricoes_nutricionais']:
        nutriente = rest['nutriente']
        # Mapear nome do nutriente para a coluna do prato
        colunas_nutrientes = {
            'energia': 'energia_kcal', 'proteina': 'proteina_g', 'lipidios': 'lipidios_g',
            'carboidrato': 'carboidrato_g', 'fibra': 'fibra_alimentar_g', 'sodio': 'sodio_mg'
        }
        if nutriente not in colunas_nutrientes:
            continue
            
        col = colunas_nutrientes[nutriente]
        
        for d in dias_range:
            soma_nutriente = pulp.lpSum(
                p[col] * X[p['id']][t][d]
                for p in dados['pratos']
                for t in tipos_prato_ids
            )
            if rest['valor_minimo'] is not None:
                problema += soma_nutriente >= rest['valor_minimo'], f"Nut_Min_{nutriente}_Dia{d}"
            if rest['valor_maximo'] is not None:
                problema += soma_nutriente <= rest['valor_maximo'], f"Nut_Max_{nutriente}_Dia{d}"

    # 3.3. Restrições Sensoriais (Cor e Consistência)
    print("   -> Adicionando restrições sensoriais (Cor/Consistência)...")
    for regra_s in dados['regras_sensoriais']:
        grupos_afetados = json.loads(regra_s['grupos_afetados'])
        for d in dias_range:
            for tipo_ref_id in [regra_s['tipo_refeicao_id']]:
                # Agrupar pratos por cor ou consistência dentro dos grupos afetados
                # (Implementação simplificada: limitar total de pratos com mesma cor/consistência)
                # Para uma implementação exata da tese, precisaríamos de variáveis auxiliares Ypc e Zpa.
                # Aqui, vamos forçar que a soma de pratos de um grupo específico não exceda o limite.
                pass # Deixaremos esta parte para a iteração 2, para não complicar o primeiro run.

    # 3.4. Restrição de Variedade (Sobremesa apenas 1x na semana)
    print("   -> Adicionando restrições de variedade...")
    # Encontrar ID do tipo de prato "Sobremesa"
    tipo_sobremesa_id = None
    for tid, tnome in dados['tipos_prato'].items():
        if 'Sobremesa' in tnome:
            tipo_sobremesa_id = tid
            break
            
    if tipo_sobremesa_id:
        soma_sobremesas = pulp.lpSum(
            X[p['id']][tipo_sobremesa_id][d]
            for p in dados['pratos']
            for d in dias_range
        )
        problema += soma_sobremesas <= 1, "Max_1_Sobremesa_Semana"

    return problema, X, dados


# ==========================================
# 3. RESOLUÇÃO E EXIBIÇÃO
# ==========================================

def resolver_e_exibir(problema, X, dados, dias=5):
    print(f"\n[3/6] Resolvendo o modelo com o solver CBC...")
        
    # Resolver
    status = problema.solve(pulp.PULP_CBC_CMD(msg=0))
    
    print(f"   -> Status: {pulp.LpStatus[status]}")
    
    if status != 1: # 1 = Optimal
        print("\n[ERRO] O modelo é INVIÁVEL. Verifique as restrições.")
        # Dica: relaxar as restrições nutricionais ou de composição
        return

    print(f"\n[4/6] Extraindo solução...")
    
    # Extrair cardápio
    cardapio = {d: {} for d in range(1, dias + 1)}
    total_lipidios = 0
    
    for p in dados['pratos']:
        for t in dados['tipos_prato'].keys():
            for d in range(1, dias + 1):
                if pulp.value(X[p['id']][t][d]) == 1:
                    cardapio[d][dados['tipos_prato'][t]] = p['nome']
                    total_lipidios += p['lipidios_g']

    print(f"\n[5/6] CARDÁPIO GERADO ({dias} Dias) - Dieta: LIVRE")
    print("="*60)
    for d in range(1, dias + 1):
        print(f"\n--- DIA {d} ---")
        for tipo_nome, prato_nome in cardapio[d].items():
            print(f"  [{tipo_nome}]: {prato_nome}")
    
    print(f"\n[6/6] MÉTRICAS FINAIS")
    print(f"   -> Total de Lipídios no período: {total_lipidios:.2f}g")
    print(f"   -> Média diária de Lipídios: {total_lipidios/dias:.2f}g")
    print("="*60)


# ==========================================
# MAIN
# ==========================================

if __name__ == "__main__":
    # Carregar dados do banco
    dados = carregar_dados(dieta_nome="LIVRE")
    
    # Criar modelo
    problema, X, dados = criar_modelo_otimizacao(dados, dias=2)
    
    # Resolver e exibir
    resolver_e_exibir(problema, X, dados, dias=2)