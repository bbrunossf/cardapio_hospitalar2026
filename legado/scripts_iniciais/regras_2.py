"""
Script para popular as tabelas de regras:
- regras_elegibilidade_dieta
- restricoes_nutricionais_dieta
- regras_sensoriais_gerais
- regras_variedade

Baseado na tese da Rafaela e nas 20 dietas hospitalares
"""

import sqlite3
import json

def criar_tabelas_regras(conn):
    """Cria as tabelas de regras se não existirem"""
    cursor = conn.cursor()
    
    # Tabela: Regras de Elegibilidade por Dieta
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS regras_elegibilidade_dieta (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        dieta_id INTEGER REFERENCES dietas(id),
        atributo VARCHAR(50), -- 'consistencia', 'cor', 'textura', 'temperatura_servimento'
        valores_permitidos TEXT, -- JSON array: '["líquido", "pastoso"]'
        operador VARCHAR(20) DEFAULT 'IN', -- 'IN', 'NOT IN'
        UNIQUE(dieta_id, atributo, operador)
    )
    """)
    
    # Tabela: Restrições Nutricionais por Dieta
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS restricoes_nutricionais_dieta (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        dieta_id INTEGER REFERENCES dietas(id),
        nutriente VARCHAR(50), -- 'energia', 'proteina', 'lipidios', 'carboidrato', 'fibra', 'calcio', 'ferro', 'sodio', 'potassio', 'vit_c', 'vit_a', 'gordura_saturada'
        valor_minimo DECIMAL(10,2),
        valor_maximo DECIMAL(10,2),
        periodo VARCHAR(20) DEFAULT 'diario', -- 'diario', 'por_refeicao'
        UNIQUE(dieta_id, nutriente, periodo)
    )
    """)
    
    # Tabela: Regras Sensoriais Gerais (aplicam-se a todas as dietas)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS regras_sensoriais_gerais (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tipo_refeicao_id INTEGER REFERENCES tipos_refeicao(id),
        regra VARCHAR(50), -- 'max_cores_iguais', 'consistencia_unica'
        valor_limite INTEGER,
        grupos_afetados TEXT, -- JSON array: '["MD", "EN", "SD", "JC"]'
        UNIQUE(tipo_refeicao_id, regra)
    )
    """)
    
    # Tabela: Regras de Variedade
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS regras_variedade (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tipo_prato_id INTEGER REFERENCES tipos_prato(id),
        dias_minimos_repeticao INTEGER, -- mínimo de dias entre repetições
        frequencia_maxima_semanal INTEGER, -- máximo de vezes por semana
        UNIQUE(tipo_prato_id)
    )
    """)
    
    conn.commit()
    print("✓ Tabelas de regras criadas/verificadas!")


def popular_regras_elegibilidade_dieta(conn):
    """Popula as regras de elegibilidade para cada dieta"""
    cursor = conn.cursor()
    
    # Buscar todas as dietas
    cursor.execute("SELECT id, nome FROM dietas ORDER BY id")
    dietas = {row['nome']: row['id'] for row in cursor.fetchall()}
    
    regras = []
    
    # DIETA LÍQUIDA: só aceita consistência líquido ou pastoso
    if 'LÍQUIDA' in dietas:
        regras.append((dietas['LÍQUIDA'], 'consistencia', '["líquido"]', 'IN'))
    
    # DIETA LÍQUIDA PASTOSA: aceita líquido ou pastoso
    if 'LÍQUIDA PASTOSA' in dietas:
        regras.append((dietas['LÍQUIDA PASTOSA'], 'consistencia', '["líquido", "pastoso"]', 'IN'))
    
    # DIETA PASTOSA: aceita pastoso ou semissólido
    if 'PASTOSA' in dietas:
        regras.append((dietas['PASTOSA'], 'consistencia', '["pastoso", "semissólido"]', 'IN'))
    
    # DIETA SEM GORDURA: evita pratos com cor marrom (fritos/assados) e alta gordura
    if 'SEM GORDURA' in dietas:
        regras.append((dietas['SEM GORDURA'], 'cor', '["marrom"]', 'NOT IN'))
        regras.append((dietas['SEM GORDURA'], 'textura', '["frita"]', 'NOT IN'))
    
    # DIETA BRANDA: evita consistência muito dura ou crocante
    if 'BRANDA' in dietas:
        regras.append((dietas['BRANDA'], 'textura', '["crocante", "dura"]', 'NOT IN'))
    
    # DIETA RENAL (todas as variantes): baixa em sódio e potássio
    dietas_renais = ['RENAL NÃO DIALÍTICO', 'RENAL NÃO DIALÍTICO DIABÉTICO', 
                     'RENAL DIALÍTICO', 'RENAL DIALÍTICO DIABÉTICO']
    for dieta_nome in dietas_renais:
        if dieta_nome in dietas:
            # Renais geralmente evitam alimentos muito processados
            regras.append((dietas[dieta_nome], 'textura', '["frita"]', 'NOT IN'))
    
    # DIETA DIABÉTICA (todas as variantes): evita produtos açucarados
    dietas_diabeticas = ['DIABÉTICA', 'MATERNIDADE DIABÉTICO', 
                         'RENAL NÃO DIALÍTICO DIABÉTICO', 'RENAL DIALÍTICO DIABÉTICO']
    for dieta_nome in dietas_diabeticas:
        if dieta_nome in dietas:
            # Evita sobremesas muito doces (controle via consistência/textura)
            pass  # Controle feito via restricoes_nutricionais_dieta (carboidratos)
    
    # DIETA LAXANTE: rica em fibras, evita alimentos constipantes
    if 'LAXANTE' in dietas:
        # Evita consistência muito pastosa ou líquida (precisa de fibra)
        pass  # Controle feito via restricoes_nutricionais_dieta (fibra mínima)
    
    # DIETA CONSTIPANTE: baixa em fibras
    if 'CONSTIPANTE' in dietas:
        # Evita alimentos muito fibrosos
        pass  # Controle feito via restricoes_nutricionais_dieta (fibra máxima)
    
    # DIETA POUCO SAL / ASSÓDICA / MATERNIDADE HIPOSSÓDICA: baixo sódio
    dietas_hipossodicas = ['POUCO SAL', 'ASSÓDICA', 'MATERNIDADE HIPOSSÓDICA']
    for dieta_nome in dietas_hipossodicas:
        if dieta_nome in dietas:
            # Evita alimentos muito processados ou salgados
            pass  # Controle feito via restricoes_nutricionais_dieta (sódio máximo)
    
    # Inserir regras
    cursor.executemany("""
        INSERT OR IGNORE INTO regras_elegibilidade_dieta 
        (dieta_id, atributo, valores_permitidos, operador)
        VALUES (?, ?, ?, ?)
    """, regras)
    
    conn.commit()
    print(f"✓ {len(regras)} regras de elegibilidade inseridas!")
    
    # Mostrar exemplo
    print("\n--- Exemplo: Regras para dieta LÍQUIDA ---")
    cursor.execute("""
        SELECT d.nome AS dieta, r.atributo, r.valores_permitidos, r.operador
        FROM regras_elegibilidade_dieta r
        JOIN dietas d ON r.dieta_id = d.id
        WHERE d.nome = 'LÍQUIDA'
    """)
    for row in cursor.fetchall():
        print(f"  {row['dieta']}: {row['atributo']} {row['operador']} {row['valores_permitidos']}")


def popular_restricoes_nutricionais_dieta(conn):
    """Popula as restrições nutricionais para cada dieta"""
    cursor = conn.cursor()
    
    # Buscar todas as dietas
    cursor.execute("SELECT id, nome FROM dietas ORDER BY id")
    dietas = {row['nome']: row['id'] for row in cursor.fetchall()}
    
    restricoes = []
    
    # Valores de referência base (adulto saudável, ~2000 kcal)
    # Estes valores podem ser ajustados conforme necessidade clínica
    
    # DIETA LIVRE (referência padrão)
    if 'LIVRE' in dietas:
        restricoes.extend([
            (dietas['LIVRE'], 'energia', 1800, 2200, 'diario'),
            (dietas['LIVRE'], 'proteina', 50, 100, 'diario'),
            (dietas['LIVRE'], 'lipidios', 50, 80, 'diario'),
            (dietas['LIVRE'], 'carboidrato', 200, 300, 'diario'),
            (dietas['LIVRE'], 'fibra', 25, 35, 'diario'),
            (dietas['LIVRE'], 'calcio', 800, 1200, 'diario'),
            (dietas['LIVRE'], 'ferro', 10, 18, 'diario'),
            (dietas['LIVRE'], 'sodio', 1500, 2300, 'diario'),
            (dietas['LIVRE'], 'potassio', 2000, 3500, 'diario'),
            (dietas['LIVRE'], 'vit_c', 60, 100, 'diario'),
            (dietas['LIVRE'], 'vit_a', 600, 900, 'diario'),
            (dietas['LIVRE'], 'gordura_saturada', 0, 20, 'diario'),
        ])
    
    # DIETA SEM GORDURA: lipídios muito baixos
    if 'SEM GORDURA' in dietas:
        restricoes.extend([
            (dietas['SEM GORDURA'], 'energia', 1500, 1800, 'diario'),
            (dietas['SEM GORDURA'], 'proteina', 50, 80, 'diario'),
            (dietas['SEM GORDURA'], 'lipidios', 20, 30, 'diario'),  # Muito baixo!
            (dietas['SEM GORDURA'], 'carboidrato', 200, 280, 'diario'),
            (dietas['SEM GORDURA'], 'fibra', 20, 30, 'diario'),
            (dietas['SEM GORDURA'], 'gordura_saturada', 0, 7, 'diario'),
        ])
    
    # DIETA DIABÉTICA: controle de carboidratos
    if 'DIABÉTICA' in dietas:
        restricoes.extend([
            (dietas['DIABÉTICA'], 'energia', 1600, 2000, 'diario'),
            (dietas['DIABÉTICA'], 'proteina', 50, 90, 'diario'),
            (dietas['DIABÉTICA'], 'lipidios', 50, 70, 'diario'),
            (dietas['DIABÉTICA'], 'carboidrato', 150, 200, 'diario'),  # Controlado
            (dietas['DIABÉTICA'], 'fibra', 25, 35, 'diario'),
            (dietas['DIABÉTICA'], 'sodio', 1500, 2300, 'diario'),
        ])
    
    # DIETA RENAL NÃO DIALÍTICO: baixo sódio, baixo potássio, baixo fósforo
    if 'RENAL NÃO DIALÍTICO' in dietas:
        restricoes.extend([
            (dietas['RENAL NÃO DIALÍTICO'], 'energia', 1800, 2200, 'diario'),
            (dietas['RENAL NÃO DIALÍTICO'], 'proteina', 40, 60, 'diario'),  # Restrito
            (dietas['RENAL NÃO DIALÍTICO'], 'lipidios', 50, 70, 'diario'),
            (dietas['RENAL NÃO DIALÍTICO'], 'carboidrato', 200, 280, 'diario'),
            (dietas['RENAL NÃO DIALÍTICO'], 'sodio', 1000, 1500, 'diario'),  # Baixo
            (dietas['RENAL NÃO DIALÍTICO'], 'potassio', 1500, 2000, 'diario'),  # Baixo
            (dietas['RENAL NÃO DIALÍTICO'], 'fosforo', 600, 800, 'diario'),  # Baixo
        ])
    
    # DIETA RENAL DIALÍTICO: maior proteína (perda na diálise)
    if 'RENAL DIALÍTICO' in dietas:
        restricoes.extend([
            (dietas['RENAL DIALÍTICO'], 'energia', 1800, 2200, 'diario'),
            (dietas['RENAL DIALÍTICO'], 'proteina', 70, 100, 'diario'),  # Maior
            (dietas['RENAL DIALÍTICO'], 'lipidios', 50, 70, 'diario'),
            (dietas['RENAL DIALÍTICO'], 'carboidrato', 200, 280, 'diario'),
            (dietas['RENAL DIALÍTICO'], 'sodio', 1000, 1500, 'diario'),
            (dietas['RENAL DIALÍTICO'], 'potassio', 1500, 2000, 'diario'),
        ])
    
    # DIETA LAXANTE: alta em fibras
    if 'LAXANTE' in dietas:
        restricoes.extend([
            (dietas['LAXANTE'], 'energia', 1800, 2200, 'diario'),
            (dietas['LAXANTE'], 'proteina', 50, 90, 'diario'),
            (dietas['LAXANTE'], 'lipidios', 50, 80, 'diario'),
            (dietas['LAXANTE'], 'carboidrato', 200, 300, 'diario'),
            (dietas['LAXANTE'], 'fibra', 35, 50, 'diario'),  # Alta!
            (dietas['LAXANTE'], 'sodio', 1500, 2300, 'diario'),
        ])
    
    # DIETA CONSTIPANTE: baixa em fibras
    if 'CONSTIPANTE' in dietas:
        restricoes.extend([
            (dietas['CONSTIPANTE'], 'energia', 1800, 2200, 'diario'),
            (dietas['CONSTIPANTE'], 'proteina', 50, 90, 'diario'),
            (dietas['CONSTIPANTE'], 'lipidios', 50, 80, 'diario'),
            (dietas['CONSTIPANTE'], 'carboidrato', 200, 300, 'diario'),
            (dietas['CONSTIPANTE'], 'fibra', 10, 15, 'diario'),  # Baixa!
            (dietas['CONSTIPANTE'], 'sodio', 1500, 2300, 'diario'),
        ])
    
    # DIETA POUCO SAL / ASSÓDICA: muito baixo sódio
    if 'POUCO SAL' in dietas:
        restricoes.extend([
            (dietas['POUCO SAL'], 'sodio', 500, 1000, 'diario'),  # Muito baixo
        ])
    
    if 'ASSÓDICA' in dietas:
        restricoes.extend([
            (dietas['ASSÓDICA'], 'sodio', 200, 500, 'diario'),  # Extremamente baixo
        ])
    
    # DIETA MATERNIDADE: maior energia e nutrientes
    if 'MATERNIDADE' in dietas:
        restricoes.extend([
            (dietas['MATERNIDADE'], 'energia', 2200, 2600, 'diario'),  # Maior
            (dietas['MATERNIDADE'], 'proteina', 70, 100, 'diario'),
            (dietas['MATERNIDADE'], 'calcio', 1000, 1300, 'diario'),  # Maior
            (dietas['MATERNIDADE'], 'ferro', 15, 27, 'diario'),  # Maior
        ])
    
    # DIETA PEDIATRIA: valores ajustados para crianças
    if 'PEDIATRIA' in dietas:
        restricoes.extend([
            (dietas['PEDIATRIA'], 'energia', 1200, 1600, 'diario'),  # Menor
            (dietas['PEDIATRIA'], 'proteina', 30, 50, 'diario'),
            (dietas['PEDIATRIA'], 'lipidios', 40, 60, 'diario'),
            (dietas['PEDIATRIA'], 'carboidrato', 150, 200, 'diario'),
            (dietas['PEDIATRIA'], 'calcio', 700, 1000, 'diario'),
        ])
    
    # Inserir restrições
    cursor.executemany("""
        INSERT OR IGNORE INTO restricoes_nutricionais_dieta 
        (dieta_id, nutriente, valor_minimo, valor_maximo, periodo)
        VALUES (?, ?, ?, ?, ?)
    """, restricoes)
    
    conn.commit()
    print(f"✓ {len(restricoes)} restrições nutricionais inseridas!")
    
    # Mostrar exemplo
    print("\n--- Exemplo: Restrições para dieta SEM GORDURA ---")
    cursor.execute("""
        SELECT d.nome AS dieta, r.nutriente, r.valor_minimo, r.valor_maximo
        FROM restricoes_nutricionais_dieta r
        JOIN dietas d ON r.dieta_id = d.id
        WHERE d.nome = 'SEM GORDURA'
        ORDER BY r.nutriente
    """)
    for row in cursor.fetchall():
        print(f"  {row['dieta']}: {row['nutriente']} = {row['valor_minimo']}-{row['valor_maximo']}g/dia")


def popular_regras_sensoriais_gerais(conn):
    """Popula as regras sensoriais gerais (baseadas na tese da Rafaela)"""
    cursor = conn.cursor()
    
    # Buscar tipos de refeição
    cursor.execute("SELECT id, nome FROM tipos_refeicao ORDER BY id")
    refeicoes = {row['nome']: row['id'] for row in cursor.fetchall()}
    
    regras = []
    
    # Regra de COR: no máximo 2 cores iguais para MD, EN, SD, JC
    # (conforme tese da Rafaela)
    grupos_cor = json.dumps(["MD", "EN", "SD", "JC"])
    
    if 'ALMOÇO' in refeicoes:
        regras.append((refeicoes['ALMOÇO'], 'max_cores_iguais', 2, grupos_cor))
    
    if 'JANTAR' in refeicoes:
        regras.append((refeicoes['JANTAR'], 'max_cores_iguais', 2, grupos_cor))
    
    if 'ALMOÇO/JANTAR' in refeicoes:
        regras.append((refeicoes['ALMOÇO/JANTAR'], 'max_cores_iguais', 2, grupos_cor))
    
    # Regra de CONSISTÊNCIA: uma e somente uma consistência para BE, MD, EN, SD
    # (conforme tese da Rafaela)
    grupos_consistencia = json.dumps(["BE", "MD", "EN", "SD"])
    
    if 'ALMOÇO' in refeicoes:
        regras.append((refeicoes['ALMOÇO'], 'consistencia_unica', 1, grupos_consistencia))
    
    if 'JANTAR' in refeicoes:
        regras.append((refeicoes['JANTAR'], 'consistencia_unica', 1, grupos_consistencia))
    
    if 'ALMOÇO/JANTAR' in refeicoes:
        regras.append((refeicoes['ALMOÇO/JANTAR'], 'consistencia_unica', 1, grupos_consistencia))
    
    # Inserir regras
    cursor.executemany("""
        INSERT OR IGNORE INTO regras_sensoriais_gerais 
        (tipo_refeicao_id, regra, valor_limite, grupos_afetados)
        VALUES (?, ?, ?, ?)
    """, regras)
    
    conn.commit()
    print(f"✓ {len(regras)} regras sensoriais gerais inseridas!")
    
    # Mostrar exemplo
    print("\n--- Exemplo: Regras sensoriais para ALMOÇO ---")
    cursor.execute("""
        SELECT r.nome AS refeicao, s.regra, s.valor_limite, s.grupos_afetados
        FROM regras_sensoriais_gerais s
        JOIN tipos_refeicao r ON s.tipo_refeicao_id = r.id
        WHERE r.nome = 'ALMOÇO'
    """)
    for row in cursor.fetchall():
        print(f"  {row['refeicao']}: {row['regra']} = {row['valor_limite']} (grupos: {row['grupos_afetados']})")


def popular_regras_variedade(conn):
    """Popula as regras de variedade e repetição"""
    cursor = conn.cursor()
    
    # Buscar tipos de prato
    cursor.execute("SELECT id, nome FROM tipos_prato ORDER BY id")
    tipos_prato = {row['nome']: row['id'] for row in cursor.fetchall()}
    
    regras = []
    
    # Regra geral: não repetir o mesmo prato em 3 dias consecutivos
    # (para todos os tipos de prato)
    for tipo_nome, tipo_id in tipos_prato.items():
        regras.append((tipo_id, 3, 7))  # 3 dias mínimos, 7 vezes máximo por semana
    
    # Sobremesa (DS): apenas 1x na semana (conforme tese da Rafaela)
    if 'DS - Sobremesa' in tipos_prato:
        regras.append((tipos_prato['DS - Sobremesa'], 7, 1))  # 7 dias mínimos, 1x por semana
    
    # Inserir regras
    cursor.executemany("""
        INSERT OR IGNORE INTO regras_variedade 
        (tipo_prato_id, dias_minimos_repeticao, frequencia_maxima_semanal)
        VALUES (?, ?, ?)
    """, regras)
    
    conn.commit()
    print(f"✓ {len(regras)} regras de variedade inseridas!")
    
    # Mostrar exemplo
    print("\n--- Exemplo: Regras de variedade ---")
    cursor.execute("""
        SELECT t.nome AS tipo_prato, v.dias_minimos_repeticao, v.frequencia_maxima_semanal
        FROM regras_variedade v
        JOIN tipos_prato t ON v.tipo_prato_id = t.id
        ORDER BY t.nome
        LIMIT 5
    """)
    for row in cursor.fetchall():
        print(f"  {row['tipo_prato']}: mínimo {row['dias_minimos_repeticao']} dias entre repetições, máximo {row['frequencia_maxima_semanal']}x/semana")


def verificar_todas_regras(conn):
    """Verifica e exibe resumo de todas as regras inseridas"""
    cursor = conn.cursor()
    
    print("\n" + "="*70)
    print("RESUMO DAS REGRAS INSERIDAS")
    print("="*70)
    
    tabelas = {
        'regras_elegibilidade_dieta': 'Regras de Elegibilidade por Dieta',
        'restricoes_nutricionais_dieta': 'Restrições Nutricionais por Dieta',
        'regras_sensoriais_gerais': 'Regras Sensoriais Gerais',
        'regras_variedade': 'Regras de Variedade'
    }
    
    for tabela, descricao in tabelas.items():
        cursor.execute(f"SELECT COUNT(*) FROM {tabela}")
        count = cursor.fetchone()[0]
        print(f"✓ {descricao}: {count} registros")
    
    print("="*70)


def main():
    """Função principal"""
    print("="*70)
    print("POPULAR TABELAS DE REGRAS - CARDÁPIO HOSPITALAR")
    print("Baseado na tese da Rafaela e 20 dietas hospitalares")
    print("="*70)
    
    # Criar conexão
    conn = sqlite3.connect("cardapio_hospitalar.db")
    conn.row_factory = sqlite3.Row
    print("\n✓ Conexão com banco de dados estabelecida")
    
    try:
        # Criar tabelas
        print("\n[1/5] Criando tabelas de regras...")
        criar_tabelas_regras(conn)
        
        # Popular regras de elegibilidade
        print("\n[2/5] Populando regras de elegibilidade por dieta...")
        popular_regras_elegibilidade_dieta(conn)
        
        # Popular restrições nutricionais
        print("\n[3/5] Populando restrições nutricionais por dieta...")
        popular_restricoes_nutricionais_dieta(conn)
        
        # Popular regras sensoriais gerais
        print("\n[4/5] Populando regras sensoriais gerais...")
        popular_regras_sensoriais_gerais(conn)
        
        # Popular regras de variedade
        print("\n[5/5] Populando regras de variedade...")
        popular_regras_variedade(conn)
        
        # Verificar dados
        verificar_todas_regras(conn)
        
        print("\n✓ Tabelas de regras populadas com sucesso!")
        print("✓ Pronto para o Épico 3: Modelagem Matemática com PuLP")
        
    except Exception as e:
        print(f"\n✗ Erro ao popular tabelas de regras: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()