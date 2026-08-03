"""
Script de Diagnóstico para Modelo Inviável
Identifica qual restrição está quebrando o solver.
Adaptado para schema v5 (prato_composicao + vw_pratos_nutricional).
"""
import sqlite3
import pulp


def diagnosticar(db_name="cardapio_hospitalar.db"):
    conn = sqlite3.connect(db_name)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print("=" * 60)
    print("DIAGNÓSTICO DO MODELO DE OTIMIZAÇÃO")
    print("=" * 60)

    # ─── 0. QUALIDADE DOS DADOS ──────────────────────────────────
    print("\n[0] Qualidade dos dados de composição:")
    cursor.execute("""
        SELECT
            COUNT(*) AS total_pratos,
            SUM(CASE WHEN pc.prato_id IS NOT NULL THEN 1 ELSE 0 END) AS com_composicao,
            SUM(CASE WHEN pc.prato_id IS NULL THEN 1 ELSE 0 END) AS sem_composicao
        FROM pratos p
        LEFT JOIN (SELECT DISTINCT prato_id FROM prato_composicao WHERE desativado = 0) pc
            ON p.id = pc.prato_id
        WHERE p.desativado = 0
    """)
    row = cursor.fetchone()
    print(f"   Total pratos ativos: {row['total_pratos']}")
    print(f"   Com composição:      {row['com_composicao']}")
    print(f"   Sem composição:      {row['sem_composicao']}")
    if row['sem_composicao'] > 0:
        print(f"   ⚠️  ATENÇÃO: {row['sem_composicao']} pratos sem ingredientes! O solver não consegue usá-los.")

    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM prato_composicao
        WHERE desativado = 0
    """)
    print(f"   Total vínculos ingrediente-prato: {cursor.fetchone()['total']}")

    # ─── 1. QUANTIDADE DE PRATOS POR TIPO ────────────────────────
    print("\n[1] Quantidade de pratos disponíveis por tipo (com composição):")
    cursor.execute("""
        SELECT t.nome,
               COUNT(p.id) AS total_cadastrados,
               SUM(CASE WHEN pc.prato_id IS NOT NULL THEN 1 ELSE 0 END) AS com_composicao
        FROM tipos_preparacoes t
        LEFT JOIN pratos p ON t.id = p.tipo_prato_id AND p.desativado = 0
        LEFT JOIN (SELECT DISTINCT prato_id FROM prato_composicao WHERE desativado = 0) pc
            ON p.id = pc.prato_id
        GROUP BY t.id
        ORDER BY t.ordem_servico
    """)
    for row in cursor.fetchall():
        print(f"   {row['nome']}: {row['com_composicao']} utilizáveis (de {row['total_cadastrados']} cadastrados)")
        if row['com_composicao'] < 5:
            print(f"      ⚠️  Menos de 5 pratos utilizáveis! Pode violar regra de variedade.")

    # ─── 2. ESTIMATIVA NUTRICIONAL (VIA VIEW) ────────────────────
    print("\n[2] Estimativa nutricional de 1 Almoço padrão (via vw_pratos_nutricional):")
    cursor.execute("""
        SELECT
            ROUND(AVG(v.energia_kcal), 1) AS media_energia,
            ROUND(AVG(v.lipidios_g), 1) AS media_lipidios,
            ROUND(AVG(v.proteina_g), 1) AS media_proteina
        FROM vw_pratos_nutricional v
        WHERE v.tipo_prato_id IN (
            SELECT id FROM tipos_preparacoes
            WHERE nome IN ('RC - Arroz', 'BE - Feijão', 'MD - Principal (Carne)',
                           'SD - Guarnição', 'EN - Entrada', 'JC - Suco')
        )
        AND v.qtd_ingredientes > 0
    """)
    almoco = cursor.fetchone()
    if almoco and almoco['media_energia']:
        kcal_6 = almoco['media_energia'] * 6
        print(f"   Energia média por prato: {almoco['media_energia']:.0f} kcal")
        print(f"   -> 6 pratos no almoço = ~{kcal_6:.0f} kcal")
        print(f"   -> Meta diária da dieta LIVRE: 1800 a 2200 kcal")
        print(f"   -> Lipídios médios: {almoco['media_lipidios']:.1f}g | Proteína: {almoco['media_proteina']:.1f}g")
        if kcal_6 < 1000:
            print("   ⚠️  ATENÇÃO: O almoço sozinho não bate nem metade da meta diária!")
    else:
        print("   ❌ Não foi possível calcular — view vazia ou sem dados.")

    # ─── 3. TESTAR MODELO PUMP SEM RESTRIÇÕES NUTRICIONAIS ──────
    print("\n[3] Testando modelo APENAS com regras de composição (sem metas de nutrientes)...")

    # Carregar dados — apenas pratos COM composição
    cursor.execute("""
        SELECT DISTINCT p.id, p.nome, p.tipo_prato_id
        FROM pratos p
        JOIN prato_composicao pc ON p.id = pc.prato_id AND pc.desativado = 0
        WHERE p.desativado = 0
    """)
    pratos = [dict(row) for row in cursor.fetchall()]
    print(f"   Pratos utilizáveis no modelo: {len(pratos)}")

    cursor.execute("SELECT id, nome FROM tipos_preparacoes")
    tipos_prato = {row['id']: row['nome'] for row in cursor.fetchall()}

    cursor.execute("""
        SELECT rc.tipo_refeicao_id, rc.tipo_prato_id, rc.qtd_minima, rc.qtd_maxima
        FROM regras_composicao rc
        JOIN tipos_refeicao tr ON rc.tipo_refeicao_id = tr.id
        ORDER BY rc.tipo_refeicao_id, rc.tipo_prato_id
    """)
    regras = [dict(row) for row in cursor.fetchall()]

    # Agrupar regras por refeição para teste
    refeicoes = {}
    for r in regras:
        refeicoes.setdefault(r['tipo_refeicao_id'], []).append(r)

    if not refeicoes:
        print("   ❌ Nenhuma regra de composição encontrada no banco!")
        conn.close()
        return

    # Testar uma refeição por vez
    dias_teste = 3  # testar com 3 dias de cardápio
    todas_ok = True

    for ref_id, regras_ref in refeicoes.items():
        cursor.execute("SELECT nome FROM tipos_refeicao WHERE id = ?", (ref_id,))
        nome_ref = cursor.fetchone()
        nome_ref = nome_ref['nome'] if nome_ref else f"Refeição {ref_id}"

        prob = pulp.LpProblem(f"Teste_{nome_ref}", pulp.LpMinimize)
        pratos_ids = [p['id'] for p in pratos]
        tipos_ids = list(tipos_prato.keys())

        X = pulp.LpVariable.dicts("X", (pratos_ids, tipos_ids, range(1, dias_teste + 1)), cat='Binary')
        prob += 0  # objetivo fake

        for regra in regras_ref:
            tprato_id = regra['tipo_prato_id']
            # Para cada dia
            for dia in range(1, dias_teste + 1):
                soma = pulp.lpSum(
                    X[p['id']][tprato_id][dia]
                    for p in pratos
                    if p['tipo_prato_id'] == tprato_id
                )
                prob += soma >= regra['qtd_minima'], f"min_{regra['tipo_refeicao_id']}_{tprato_id}_d{dia}"
                prob += soma <= regra['qtd_maxima'], f"max_{regra['tipo_refeicao_id']}_{tprato_id}_d{dia}"

        status = prob.solve(pulp.PULP_CBC_CMD(msg=0))
        if status == 1:
            print(f"   ✅ {nome_ref}: viável para {dias_teste} dias")
        else:
            print(f"   ❌ {nome_ref}: INVIÁVEL! (status={status})")
            todas_ok = False
            # Diagnóstico: quais tipos estão com poucos pratos?
            for regra in regras_ref:
                qtd = sum(1 for p in pratos if p['tipo_prato_id'] == regra['tipo_prato_id'])
                nome_tp = tipos_prato.get(regra['tipo_prato_id'], f"tipo {regra['tipo_prato_id']}")
                if qtd < regra['qtd_maxima']:
                    print(f"      -> '{nome_tp}': tem {qtd} pratos, mas precisa de até {regra['qtd_maxima']} por refeição")
                if qtd < regra['qtd_minima']:
                    print(f"      -> '{nome_tp}': tem {qtd} pratos, mas precisa de NO MÍNIMO {regra['qtd_minima']}")

    if todas_ok:
        print("\n   ✅ Todos os modelos de composição são VIÁVEIS!")
    else:
        print("\n   ⚠️  Alguns modelos são inviáveis. Reveja as regras ou cadastre mais pratos.")

    conn.close()
    print("\n" + "=" * 60)
    print("FIM DO DIAGNÓSTICO")
    print("=" * 60)


if __name__ == "__main__":
    import os
    db_path = os.path.join(os.path.dirname(__file__), "cardapio_hospitalar.db")
    diagnosticar(db_path)
