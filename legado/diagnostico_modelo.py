"""
Script de Diagnóstico para Modelo Inviável
Identifica qual restrição está quebrando o solver.
"""
import sqlite3
import json
import pulp

def diagnosticar(db_name="cardapio_hospitalar.db"):
    conn = sqlite3.connect(db_name)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print("="*60)
    print("DIAGNÓSTICO DO MODELO DE OTIMIZAÇÃO")
    print("="*60)

    # 1. Verificar quantidade de pratos por tipo
    print("\n[1] Quantidade de pratos disponíveis por tipo:")
    cursor.execute("""
        SELECT t.nome, COUNT(p.id) as total
        FROM tipos_prato t
        LEFT JOIN pratos p ON t.id = p.tipo_prato_id
        GROUP BY t.id
    """)
    for row in cursor.fetchall():
        print(f"   {row['nome']}: {row['total']} pratos")
        if row['total'] < 5:
            print(f"   ️  ATENÇÃO: Menos de 5 pratos! Pode violar regra de variedade em 5 dias.")

    # 2. Calcular média nutricional de um "Almoço Padrão"
    print("\n[2] Estimativa nutricional de 1 Almoço padrão (1 de cada tipo obrigatório):")
    cursor.execute("""
        SELECT 
            AVG(p.energia_kcal) as media_energia,
            AVG(p.lipidios_g) as media_lipidios,
            AVG(p.proteina_g) as media_proteina
        FROM pratos p
        WHERE p.tipo_prato_id IN (
            SELECT id FROM tipos_prato WHERE nome IN ('RC - Arroz', 'BE - Feijão', 'MD - Principal (Carne)', 'SD - Guarnição', 'EN - Entrada', 'JC - Suco')
        )
    """)
    almoco = cursor.fetchone()
    print(f"   Energia média por prato: {almoco['media_energia']:.0f} kcal")
    print(f"   -> 6 pratos no almoço = ~{almoco['media_energia']*6:.0f} kcal")
    print(f"   -> Meta diária da dieta LIVRE: 1800 a 2200 kcal")
    if almoco['media_energia']*6 < 1000:
        print("   ⚠️  ATENÇÃO: O almoço sozinho não bate nem metade da meta diária! As porções podem estar pequenas.")

    # 3. Testar o modelo SEM restrições nutricionais (apenas composição)
    print("\n[3] Testando modelo APENAS com regras de composição (sem metas de nutrientes)...")
    
    # Carregar dados básicos
    cursor.execute("SELECT id, nome, tipo_prato_id, lipidios_g FROM pratos")
    pratos = [dict(row) for row in cursor.fetchall()]
    
    cursor.execute("SELECT id, nome FROM tipos_prato")
    tipos_prato = {row['id']: row['nome'] for row in cursor.fetchall()}
    
    cursor.execute("SELECT tipo_refeicao_id, tipo_prato_id, qtd_minima, qtd_maxima FROM regras_composicao")
    regras = [dict(row) for row in cursor.fetchall()]

    # Montar modelo simples
    prob = pulp.LpProblem("Teste_Composicao", pulp.LpMinimize)
    pratos_ids = [p['id'] for p in pratos]
    tipos_ids = list(tipos_prato.keys())
    
    X = pulp.LpVariable.dicts("X", (pratos_ids, tipos_ids, range(1, 6)), cat='Binary')
    
    # Função objetivo fake (minimizar 0)
    prob += 0
    
    # Apenas restrições de composição para o DIA 1, tipo refeição ALMOÇO (id=3)
    for regra in regras:
        if regra['tipo_refeicao_id'] == 3: # ALMOÇO
            soma = pulp.lpSum(X[p['id']][regra['tipo_prato_id']][1] for p in pratos if p['tipo_prato_id'] == regra['tipo_prato_id'])
            prob += soma >= regra['qtd_minima']
            prob += soma <= regra['qtd_maxima']

    status = prob.solve(pulp.PULP_CBC_CMD(msg=0))
    if status == 1:
        print("   ✅ SUCESSO! As regras de composição são viáveis.")
    else:
        print("   ❌ FALHA! As regras de composição sozinhas já são inviáveis. Falta pratos no banco.")

    conn.close()
    print("\n" + "="*60)
    print("FIM DO DIAGNÓSTICO")
    print("="*60)

if __name__ == "__main__":
    diagnosticar()