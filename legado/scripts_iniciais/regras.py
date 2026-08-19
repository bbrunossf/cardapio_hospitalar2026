"""
Script para Épico 2: Configuração de Refeições e Regras de Composição
"""
import sqlite3

def configurar_refeicoes(db_name="cardapio_hospitalar.db"):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    # 1. Criar tabela de Tipos de Refeição
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tipos_refeicao (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome VARCHAR(50) NOT NULL UNIQUE,
        horario_padrao TIME,
        descricao TEXT
    )
    """)

    # 2. Criar tabela de Regras de Composição (O "Macro")
    # Esta tabela diz ao solver quantos pratos de cada TIPO a refeição deve ter.
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS regras_composicao (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tipo_refeicao_id INTEGER REFERENCES tipos_refeicao(id),
        tipo_prato_id INTEGER REFERENCES tipos_prato(id),
        qtd_minima INTEGER DEFAULT 0,
        qtd_maxima INTEGER DEFAULT 1,
        obrigatorio BOOLEAN DEFAULT 1,
        UNIQUE(tipo_refeicao_id, tipo_prato_id)
    )
    """)
    
    conn.commit()
    print("✓ Tabelas de Refeições e Regras criadas!")

    # 3. Inserir os Tipos de Refeição
    refeicoes = [
        ('CAFÉ DA MANHÃ', '07:00:00', 'Primeira refeição do dia'),
        ('COLAÇÃO', '09:30:00', 'Lanche da manhã'),
        ('ALMOÇO', '11:30:00', 'Refeição principal do meio-dia'),
        ('CAFÉ DA TARDE', '15:00:00', 'Lanche da tarde'),
        ('JANTAR', '18:30:00', 'Refeição principal da noite'),
        ('ALMOÇO/JANTAR', '12:00:00', 'Refeição completa (usada em turnos)'),
        ('CEIA', '20:00:00', 'Refeição leve noturna'),
        ('CEIA 22:30', '22:30:00', 'Ceia tardia (leite e pão)'),
        ('CEIA 03:00', '03:00:00', 'Ceia noturna (madrugada)'),
    ]
    
    cursor.executemany("""
        INSERT OR IGNORE INTO tipos_refeicao (nome, horario_padrao, descricao)
        VALUES (?, ?, ?)
    """, refeicoes)
    conn.commit()
    print(f"✓ {len(refeicoes)} tipos de refeição inseridos!")

    # 4. Inserir as Regras de Composição
    # Buscando os IDs dos tipos de prato e refeição
    cursor.execute("SELECT id, nome FROM tipos_refeicao")
    id_refeicao = {row['nome']: row['id'] for row in cursor.fetchall()}
    
    cursor.execute("SELECT id, nome FROM tipos_prato")
    id_prato = {row['nome']: row['id'] for row in cursor.fetchall()}

    # Definição das regras (Refeição, Tipo Prato, Min, Max, Obrigatório)
    regras = [
        # CAFÉ DA MANHÃ
        ('CAFÉ DA MANHÃ', 'BC1 - Cereal (Café)', 1, 1, True),
        ('CAFÉ DA MANHÃ', 'DP - Laticínios', 1, 1, True),
        ('CAFÉ DA MANHÃ', 'FT - Fruta', 0, 1, False),
        
        # COLAÇÃO
        ('COLAÇÃO', 'FT - Fruta', 1, 1, True),
        ('COLAÇÃO', 'DP - Laticínios', 0, 1, False),
        
        # ALMOÇO (Estrutura completa da Rafaela)
        ('ALMOÇO', 'RC - Arroz', 1, 1, True),
        ('ALMOÇO', 'BE - Feijão', 1, 1, True),
        ('ALMOÇO', 'EN - Entrada', 1, 1, True),
        ('ALMOÇO', 'MD - Principal (Carne)', 1, 1, True),
        ('ALMOÇO', 'SD - Guarnição', 1, 1, True),
        ('ALMOÇO', 'JC - Suco', 1, 1, True),
        ('ALMOÇO', 'DS - Sobremesa', 0, 1, False), # Apenas 1x na semana, controlado por outra restrição
        
        # CAFÉ DA TARDE
        ('CAFÉ DA TARDE', 'BC2 - Cereal (Almoço)', 1, 1, True),
        ('CAFÉ DA TARDE', 'DP - Laticínios', 1, 1, True),
        ('CAFÉ DA TARDE', 'FT - Fruta', 0, 1, False),
        
        # JANTAR (Levemente mais leve que o almoço, entrada opcional)
        ('JANTAR', 'RC - Arroz', 1, 1, True),
        ('JANTAR', 'BE - Feijão', 1, 1, True),
        ('JANTAR', 'EN - Entrada', 0, 1, False),
        ('JANTAR', 'MD - Principal (Carne)', 1, 1, True),
        ('JANTAR', 'SD - Guarnição', 1, 1, True),
        ('JANTAR', 'JC - Suco', 1, 1, True),
        
        # ALMOÇO/JANTAR (Mesma estrutura do almoço)
        ('ALMOÇO/JANTAR', 'RC - Arroz', 1, 1, True),
        ('ALMOÇO/JANTAR', 'BE - Feijão', 1, 1, True),
        ('ALMOÇO/JANTAR', 'EN - Entrada', 1, 1, True),
        ('ALMOÇO/JANTAR', 'MD - Principal (Carne)', 1, 1, True),
        ('ALMOÇO/JANTAR', 'SD - Guarnição', 1, 1, True),
        ('ALMOÇO/JANTAR', 'JC - Suco', 1, 1, True),
        
        # CEIA
        ('CEIA', 'BC1 - Cereal (Café)', 1, 1, True),
        ('CEIA', 'DP - Laticínios', 1, 1, True),
        
        # CEIAS NOTURNAS (Bem leves)
        ('CEIA 22:30', 'DP - Laticínios', 1, 1, True),
        ('CEIA 22:30', 'BC1 - Cereal (Café)', 0, 1, False),
        
        ('CEIA 03:00', 'DP - Laticínios', 1, 1, True),
        ('CEIA 03:00', 'BC1 - Cereal (Café)', 0, 1, False),
    ]

    regras_inseridas = 0
    for ref_nome, prato_nome, min_qtd, max_qtd, obrigatorio in regras:
        if ref_nome in id_refeicao and prato_nome in id_prato:
            cursor.execute("""
                INSERT OR IGNORE INTO regras_composicao 
                (tipo_refeicao_id, tipo_prato_id, qtd_minima, qtd_maxima, obrigatorio)
                VALUES (?, ?, ?, ?, ?)
            """, (id_refeicao[ref_nome], id_prato[prato_nome], min_qtd, max_qtd, obrigatorio))
            regras_inseridas += 1

    conn.commit()
    print(f"✓ {regras_inseridas} regras de composição inseridas!")
    
    # Verificação rápida
    print("\n--- Resumo das Regras ---")
    cursor.execute("""
        SELECT r.nome, p.nome, rc.qtd_minima, rc.qtd_maxima, rc.obrigatorio
        FROM regras_composicao rc
        JOIN tipos_refeicao r ON rc.tipo_refeicao_id = r.id
        JOIN tipos_prato p ON rc.tipo_prato_id = p.id
        ORDER BY r.id, p.ordem_servico
    """)
    for row in cursor.fetchall():
        status = "Obrigatório" if row['obrigatorio'] else "Opcional"
        print(f"[{row['nome']}] -> {row['nome']}: {row['qtd_minima']} a {row['qtd_maxima']} ({status})")

    conn.close()

if __name__ == "__main__":
    configurar_refeicoes()