"""
Script de popularização do banco de dados - Épico 1
Gestão de Dados Mestres para Sistema de Cardápios Hospitalares

v2: FK + CASCADE + criado_em/editado_em/desativado em todas as tabelas
"""

import sqlite3
from datetime import datetime
import json

def criar_conexao(db_name="cardapio_hospitalar.db"):
    """Cria conexão com o banco de dados SQLite com FKs ativadas"""
    conn = sqlite3.connect(db_name)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def criar_tabelas(conn):
    """Cria todas as tabelas do schema com FKs, CASCADE e colunas de auditoria"""
    cursor = conn.cursor()

    # Tabela: Ingredientes
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ingredientes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome VARCHAR(100) NOT NULL,
        tipo_alimento VARCHAR(50),
        unidade_medida VARCHAR(20),
        energia_kcal DECIMAL(8,2),
        carboidrato_g DECIMAL(8,2),
        proteina_g DECIMAL(8,2),
        lipidios_g DECIMAL(8,2),
        fibra_alimentar_g DECIMAL(8,2),
        calcio_mg DECIMAL(8,2),
        ferro_mg DECIMAL(8,2),
        sodio_mg DECIMAL(8,2),
        potassio_mg DECIMAL(8,2),
        fosforo_mg DECIMAL(8,2),
        vit_c_mg DECIMAL(8,2),
        vit_a_mg DECIMAL(8,2),
        gordura_saturada_g DECIMAL(8,2),
        colesterol_mg DECIMAL(8,2),
        custo_por_100g DECIMAL(10,4),
        disponibilidade BOOLEAN DEFAULT 1,
        observacoes TEXT,
        criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
        editado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
        desativado BOOLEAN DEFAULT 0
    )
    """)

    # Tabela: Formas de Preparo
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS formas_preparo (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome VARCHAR(50),
        descricao TEXT,
        fator_correcao DECIMAL(4,2),
        fator_parte_comestivel DECIMAL(4,2),
        criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
        editado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
        desativado BOOLEAN DEFAULT 0
    )
    """)

    # Tabela: Preparações
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS preparacoes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ingrediente_id INTEGER NOT NULL REFERENCES ingredientes(id) ON DELETE CASCADE,
        forma_preparo_id INTEGER NOT NULL REFERENCES formas_preparo(id) ON DELETE CASCADE,
        nome_completo VARCHAR(150),
        energia_kcal DECIMAL(8,2),
        carboidrato_g DECIMAL(8,2),
        proteina_g DECIMAL(8,2),
        lipidios_g DECIMAL(8,2),
        fibra_alimentar_g DECIMAL(8,2),
        calcio_mg DECIMAL(8,2),
        ferro_mg DECIMAL(8,2),
        sodio_mg DECIMAL(8,2),
        potassio_mg DECIMAL(8,2),
        fosforo_mg DECIMAL(8,2),
        vit_c_mg DECIMAL(8,2),
        vit_a_mg DECIMAL(8,2),
        gordura_saturada_g DECIMAL(8,2),
        colesterol_mg DECIMAL(8,2),
        tempo_preparo_min INTEGER,
        dificuldade INTEGER,
        observacoes TEXT,
        criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
        editado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
        desativado BOOLEAN DEFAULT 0
    )
    """)

    # Tabela: Tipos de Prato
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tipos_prato (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome VARCHAR(50),
        ordem_servico INTEGER,
        criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
        editado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
        desativado BOOLEAN DEFAULT 0
    )
    """)

    # Tabela: Pratos
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pratos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome VARCHAR(100),
        tipo_prato_id INTEGER NOT NULL REFERENCES tipos_prato(id) ON DELETE CASCADE,
        cor_predominante VARCHAR(30),
        consistencia VARCHAR(30),
        textura VARCHAR(50),
        temperatura_servimento VARCHAR(30),
        porcao_padrao_g DECIMAL(8,2),
        energia_kcal DECIMAL(8,2),
        lipidios_g DECIMAL(8,2),
        proteina_g DECIMAL(8,2),
        carboidrato_g DECIMAL(8,2),
        fibra_alimentar_g DECIMAL(8,2),
        calcio_mg DECIMAL(8,2),
        ferro_mg DECIMAL(8,2),
        sodio_mg DECIMAL(8,2),
        custo_total DECIMAL(10,4),
        tempo_producao_min INTEGER,
        criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
        editado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
        desativado BOOLEAN DEFAULT 0
    )
    """)

    # Tabela: Prato-Preparações (relacionamento N:N com chave composta)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS prato_preparacoes (
        prato_id INTEGER NOT NULL REFERENCES pratos(id) ON DELETE CASCADE,
        preparacao_id INTEGER NOT NULL REFERENCES preparacoes(id) ON DELETE CASCADE,
        quantidade_g DECIMAL(8,2),
        percentual DECIMAL(5,2),
        criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
        editado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
        desativado BOOLEAN DEFAULT 0,
        PRIMARY KEY (prato_id, preparacao_id)
    )
    """)

    # Tabela: Dietas
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS dietas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome VARCHAR(50) NOT NULL UNIQUE,
        descricao TEXT,
        com_sal BOOLEAN DEFAULT 1,
        criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
        editado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
        desativado BOOLEAN DEFAULT 0
    )
    """)

    # Tabela: Variações de Preparação por Dieta
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS variacoes_preparacao (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        preparacao_id INTEGER NOT NULL REFERENCES preparacoes(id) ON DELETE CASCADE,
        dieta_id INTEGER NOT NULL REFERENCES dietas(id) ON DELETE CASCADE,
        nome_exibicao VARCHAR(150),
        sodio_mg DECIMAL(8,2),
        energia_kcal DECIMAL(8,2),
        lipidios_g DECIMAL(8,2),
        gordura_saturada_g DECIMAL(8,2),
        carboidrato_g DECIMAL(8,2),
        proteina_g DECIMAL(8,2),
        fibra_alimentar_g DECIMAL(8,2),
        observacoes TEXT,
        criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
        editado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
        desativado BOOLEAN DEFAULT 0,
        UNIQUE(preparacao_id, dieta_id)
    )
    """)

    conn.commit()
    print("✓ Tabelas criadas com sucesso!")

def inserir_formas_preparo(conn):
    """Insere formas de preparo básicas"""
    cursor = conn.cursor()

    formas_preparo = [
        ('Cru', 'Alimento consumido sem cozimento', 1.0, 0.90),
        ('Cozido', 'Alimento cozido em água', 1.30, 0.95),
        ('Assado', 'Alimento assado no forno', 1.15, 0.90),
        ('Grelhado', 'Alimento grelhado na chapa', 1.10, 0.85),
        ('Frito', 'Alimento frito em óleo', 1.20, 0.90),
        ('Refogado', 'Alimento refogado com pouco óleo', 1.15, 0.92),
        ('Sauté', 'Alimento salteado rapidamente', 1.10, 0.93),
        ('Purê', 'Alimento amassado e processado', 1.25, 0.95),
        ('Suco', 'Alimento liquidificado e coado', 1.0, 0.85),
        ('Salada', 'Alimento cru fatiado/picado', 1.0, 0.80),
    ]

    cursor.executemany("""
        INSERT INTO formas_preparo (nome, descricao, fator_correcao, fator_parte_comestivel)
        VALUES (?, ?, ?, ?)
    """, formas_preparo)

    conn.commit()
    print(f"✓ {len(formas_preparo)} formas de preparo inseridas!")

def inserir_ingredientes(conn):
    """Insere ingredientes com dados nutricionais mockados"""
    cursor = conn.cursor()

    # Dados mockados baseados em tabelas nutricionais reais (TACO, IBGE, etc.)
    ingredientes = [
        # CARNES (tipo_alimento = 'carnes e derivados')
        ('Peito de frango', 'carnes e derivados', 'g', 165, 0, 31, 3.6, 0, 15, 1.0, 74, 320, 220, 0, 50, 1.0, 73),
        ('Coxa de frango com pele', 'carnes e derivados', 'g', 230, 0, 25, 14, 0, 12, 1.2, 85, 280, 180, 0, 45, 2.5, 85),
        ('Filé de peixe (tilápia)', 'peixes e frutos do mar', 'g', 128, 0, 26, 2.7, 0, 14, 0.8, 55, 290, 200, 0, 30, 0.9, 57),
        ('Carne bovina magra (patinho)', 'carnes e derivados', 'g', 176, 0, 26, 7.5, 0, 18, 2.8, 68, 340, 210, 0, 25, 2.9, 71),
        ('Carne bovina (acém)', 'carnes e derivados', 'g', 235, 0, 24, 15, 0, 15, 2.5, 75, 320, 195, 0, 22, 5.8, 78),
        ('Lombo suíno', 'carnes e derivados', 'g', 190, 0, 27, 8.5, 0, 16, 1.5, 72, 310, 205, 0, 28, 3.1, 75),

        # PEIXES
        ('Salmão', 'peixes e frutos do mar', 'g', 208, 0, 20, 13, 0, 12, 0.5, 62, 363, 240, 0, 40, 3.8, 55),
        ('Atum em lata (água)', 'peixes e frutos do mar', 'g', 116, 0, 26, 0.8, 0, 10, 1.2, 45, 280, 190, 0, 20, 0.2, 38),

        # LEGUMINOSAS
        ('Feijão carioca (cru)', 'leguminosas e derivados', 'g', 337, 60, 20, 1.5, 15, 140, 8.2, 1200, 18, 0, 5.8, 0, 0, 0),
        ('Feijão preto (cru)', 'leguminosas e derivados', 'g', 328, 58, 21, 1.3, 16, 130, 9.5, 1150, 20, 0, 5.2, 0, 0, 0),
        ('Lentilha (crua)', 'leguminosas e derivados', 'g', 353, 60, 25, 1.1, 11, 50, 7.6, 650, 15, 0, 4.8, 0, 0, 0),
        ('Grão de bico (cru)', 'leguminosas e derivados', 'g', 364, 61, 19, 6, 17, 105, 6.2, 875, 12, 0, 11, 0, 0, 0),

        # CEREAIS
        ('Arroz branco (cru)', 'cereais e derivados', 'g', 365, 78, 7, 0.7, 1.3, 28, 2.1, 350, 8, 0, 7.8, 0, 0, 0),
        ('Arroz integral (cru)', 'cereais e derivados', 'g', 370, 77, 8, 2.9, 3.5, 33, 2.5, 420, 10, 0, 9.5, 0, 0, 0),
        ('Macarrão (cru)', 'cereais e derivados', 'g', 371, 75, 13, 1.5, 3.2, 30, 3.5, 400, 12, 0, 8.2, 0, 0, 0),
        ('Pão francês', 'cereais e derivados', 'g', 293, 57, 8, 3.5, 2.5, 150, 3.2, 580, 5, 0, 12, 0, 0, 0),
        ('Aveia em flocos', 'cereais e derivados', 'g', 389, 66, 17, 7, 10, 54, 4.7, 410, 10, 0, 11.5, 0, 0, 0),

        # LEGUMES E VERDURAS
        ('Alface', 'verduras, legumes e derivados', 'g', 15, 3, 1.4, 0.2, 1.3, 33, 0.9, 28, 196, 29, 9.2, 370, 0, 0),
        ('Couve', 'verduras, legumes e derivados', 'g', 32, 6, 2.5, 0.4, 3.6, 254, 1.8, 43, 353, 55, 65, 310, 0.1, 0),
        ('Brócolis', 'verduras, legumes e derivados', 'g', 34, 7, 2.8, 0.4, 2.6, 47, 0.7, 33, 316, 66, 89, 508, 0, 0),
        ('Cenoura', 'verduras, legumes e derivados', 'g', 41, 10, 0.9, 0.2, 2.8, 33, 0.3, 69, 320, 55, 8.3, 839, 0, 0),
        ('Abobrinha', 'verduras, legumes e derivados', 'g', 17, 3, 1.2, 0.2, 1, 16, 0.4, 2, 261, 24, 17, 100, 0, 0),
        ('Chuchu', 'verduras, legumes e derivados', 'g', 19, 4, 0.8, 0.1, 1.2, 17, 0.4, 6, 122, 12, 7, 15, 0, 0),
        ('Beterraba', 'verduras, legumes e derivados', 'g', 43, 10, 1.6, 0.2, 2.8, 16, 0.8, 78, 305, 32, 49, 20, 0, 0),
        ('Tomate', 'verduras, legumes e derivados', 'g', 18, 4, 0.9, 0.2, 1.2, 10, 0.3, 5, 237, 24, 13.7, 42, 0, 0),
        ('Cebola', 'verduras, legumes e derivados', 'g', 40, 9, 1.1, 0.1, 1.7, 23, 0.2, 4, 146, 29, 7.4, 0, 0, 0),
        ('Alho', 'verduras, legumes e derivados', 'g', 149, 33, 6.4, 0.5, 2.1, 181, 1.7, 17, 401, 153, 31.2, 0, 0, 0),

        # FRUTAS
        ('Banana', 'frutas e derivados', 'g', 89, 23, 1.1, 0.3, 2.6, 5, 0.3, 1, 358, 32, 8.7, 64, 0, 0),
        ('Maçã', 'frutas e derivados', 'g', 52, 14, 0.3, 0.2, 2.4, 6, 0.1, 1, 107, 11, 4.6, 54, 0, 0),
        ('Laranja', 'frutas e derivados', 'g', 47, 12, 0.9, 0.1, 2.4, 40, 0.1, 0, 181, 14, 53.2, 225, 0, 0),
        ('Mamão', 'frutas e derivados', 'g', 43, 11, 0.5, 0.3, 1.7, 20, 0.1, 8, 182, 18, 60.9, 47, 0, 0),
        ('Abacaxi', 'frutas e derivados', 'g', 50, 13, 0.5, 0.1, 1.4, 18, 0.3, 1, 109, 12, 47.8, 58, 0, 0),
        ('Melancia', 'frutas e derivados', 'g', 30, 8, 0.6, 0.2, 0.4, 11, 0.2, 1, 112, 10, 8.1, 569, 0, 0),
        ('Uva', 'frutas e derivados', 'g', 67, 18, 0.6, 0.4, 0.9, 10, 0.4, 2, 191, 10, 10.8, 66, 0, 0),
        ('Manga', 'frutas e derivados', 'g', 60, 15, 0.8, 0.4, 1.6, 11, 0.2, 4, 168, 14, 36.4, 54, 0, 0),

        # LATICÍNIOS
        ('Leite integral', 'leites e derivados', 'ml', 61, 5, 3.2, 3.3, 0, 113, 0.1, 43, 150, 95, 1.5, 46, 1.9, 14),
        ('Leite desnatado', 'leites e derivados', 'ml', 34, 5, 3.4, 0.2, 0, 122, 0.1, 42, 156, 98, 1.6, 50, 0.1, 5),
        ('Iogurte natural', 'leites e derivados', 'g', 61, 5, 3.5, 3.3, 0, 121, 0.1, 46, 155, 100, 0.5, 27, 2.1, 13),
        ('Queijo branco (minas)', 'leites e derivados', 'g', 230, 4, 18, 16, 0, 480, 0.5, 720, 95, 120, 0.3, 180, 9.5, 50),
        ('Queijo mussarela', 'leites e derivados', 'g', 280, 3, 24, 20, 0, 505, 0.4, 760, 76, 138, 0.2, 200, 12, 80),

        # OVOS
        ('Ovo de galinha', 'ovos e derivados', 'unidade', 155, 1.1, 13, 11, 0, 50, 1.8, 142, 138, 170, 1.5, 372, 3.3, 373),

        # GORDURAS E ÓLEOS
        ('Azeite de oliva', 'aromatizantes, gorduras e óleos', 'ml', 884, 0, 0, 100, 0, 1, 0, 2, 0, 0, 0, 14, 0, 0),
        ('Óleo de soja', 'aromatizantes, gorduras e óleos', 'ml', 884, 0, 0, 100, 0, 0, 0, 2, 0, 0, 0, 16, 0, 0),
        ('Manteiga', 'aromatizantes, gorduras e óleos', 'g', 717, 0.1, 0.9, 81, 0, 24, 0.2, 643, 15, 215, 2.2, 215, 51, 215),
        ('Margarina', 'aromatizantes, gorduras e óleos', 'g', 717, 0.2, 0.2, 80, 0, 0, 0, 900, 0, 0, 15, 0, 20, 0),

        # OUTROS
        ('Açúcar refinado', 'produtos açucarados', 'g', 387, 100, 0, 0, 0, 1, 0, 1, 2, 0, 0, 0, 0, 0),
        ('Sal de cozinha', 'aromatizantes, gorduras e óleos', 'g', 0, 0, 0, 0, 0, 0, 0, 38758, 8, 0, 0, 0, 0, 0),
        ('Batata', 'verduras, legumes e derivados', 'g', 77, 17, 2, 0.1, 2.2, 12, 0.8, 6, 421, 57, 19.7, 2, 0, 0),
        ('Mandioca', 'verduras, legumes e derivados', 'g', 160, 38, 1.4, 0.3, 1.8, 16, 0.3, 14, 271, 21, 20.6, 1, 0, 0),
    ]

    cursor.executemany("""
        INSERT INTO ingredientes
        (nome, tipo_alimento, unidade_medida, energia_kcal, carboidrato_g, proteina_g,
         lipidios_g, fibra_alimentar_g, calcio_mg, ferro_mg, sodio_mg, potassio_mg,
         fosforo_mg, vit_c_mg, vit_a_mg, gordura_saturada_g, colesterol_mg, custo_por_100g)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0.50)
    """, ingredientes)

    conn.commit()
    print(f"✓ {len(ingredientes)} ingredientes inseridos!")

def inserir_preparacoes(conn):
    """Cria preparações combinando ingredientes com formas de preparo"""
    cursor = conn.cursor()

    # Buscar ingredientes e formas de preparo do banco
    cursor.execute("""SELECT id, nome, tipo_alimento, energia_kcal, carboidrato_g, proteina_g,
         lipidios_g, fibra_alimentar_g, calcio_mg, ferro_mg, sodio_mg, potassio_mg,
         fosforo_mg, vit_c_mg, vit_a_mg, gordura_saturada_g, colesterol_mg FROM ingredientes""")
    ingredientes = {row['nome']: dict(row) for row in cursor.fetchall()}

    cursor.execute("SELECT id, nome, fator_correcao, fator_parte_comestivel FROM formas_preparo")
    formas_preparo = {row['nome']: dict(row) for row in cursor.fetchall()}

    preparacoes = [
        # CARNES PREPARADAS
        ('Peito de frango grelhado', 'Peito de frango', 'Grelhado'),
        ('Coxa de frango assada', 'Coxa de frango com pele', 'Assado'),
        ('Filé de peixe grelhado', 'Filé de peixe (tilápia)', 'Grelhado'),
        ('Salmão grelhado', 'Salmão', 'Grelhado'),
        ('Carne bovina cozida', 'Carne bovina magra (patinho)', 'Cozido'),
        ('Carne bovina assada', 'Carne bovina (acém)', 'Assado'),
        ('Lombo suíno assado', 'Lombo suíno', 'Assado'),
        ('Atum grelhado', 'Atum em lata (água)', 'Grelhado'),

        # LEGUMINOSAS PREPARADAS
        ('Feijão carioca cozido', 'Feijão carioca (cru)', 'Cozido'),
        ('Feijão preto cozido', 'Feijão preto (cru)', 'Cozido'),
        ('Lentilha cozida', 'Lentilha (crua)', 'Cozido'),
        ('Grão de bico cozido', 'Grão de bico (cru)', 'Cozido'),

        # CEREAIS PREPARADOS
        ('Arroz branco cozido', 'Arroz branco (cru)', 'Cozido'),
        ('Arroz integral cozido', 'Arroz integral (cru)', 'Cozido'),
        ('Macarrão cozido', 'Macarrão (cru)', 'Cozido'),
        ('Purê de batata', 'Batata', 'Purê'),
        ('Farofa de mandioca', 'Mandioca', 'Refogado'),

        # LEGUMES PREPARADOS
        ('Salada de alface', 'Alface', 'Salada'),
        ('Couve refogada', 'Couve', 'Refogado'),
        ('Brócolis cozido', 'Brócolis', 'Cozido'),
        ('Cenoura cozida', 'Cenoura', 'Cozido'),
        ('Abobrinha grelhada', 'Abobrinha', 'Grelhado'),
        ('Chuchu cozido', 'Chuchu', 'Cozido'),
        ('Beterraba cozida', 'Beterraba', 'Cozido'),
        ('Tomate cru', 'Tomate', 'Cru'),
        ('Cebola refogada', 'Cebola', 'Refogado'),
        ('Alho refogado', 'Alho', 'Refogado'),

        # FRUTAS PREPARADAS
        ('Banana in natura', 'Banana', 'Cru'),
        ('Maçã in natura', 'Maçã', 'Cru'),
        ('Laranja in natura', 'Laranja', 'Cru'),
        ('Mamão in natura', 'Mamão', 'Cru'),
        ('Abacaxi in natura', 'Abacaxi', 'Cru'),
        ('Melancia in natura', 'Melancia', 'Cru'),
        ('Uva in natura', 'Uva', 'Cru'),
        ('Manga in natura', 'Manga', 'Cru'),
        ('Suco de laranja', 'Laranja', 'Suco'),
        ('Suco de abacaxi', 'Abacaxi', 'Suco'),

        # LATICÍNIOS PREPARADOS
        ('Leite integral', 'Leite integral', 'Cru'),
        ('Leite desnatado', 'Leite desnatado', 'Cru'),
        ('Iogurte natural', 'Iogurte natural', 'Cru'),
        ('Queijo branco fatiado', 'Queijo branco (minas)', 'Cru'),
        ('Queijo mussarela fatiado', 'Queijo mussarela', 'Cru'),

        # OVOS PREPARADOS
        ('Ovo cozido', 'Ovo de galinha', 'Cozido'),
        ('Ovo mexido', 'Ovo de galinha', 'Sauté'),

        # PREPARAÇÕES COMPOSTAS (usarão múltiplos ingredientes)
        ('Pirão', 'Mandioca', 'Purê'),
        ('Arroz à grega', 'Arroz branco (cru)', 'Cozido'),
        ('Salada mista', 'Alface', 'Salada'),
    ]

    preparacoes_inseridas = 0
    for nome_prep, nome_ingrediente, nome_forma in preparacoes:
        if nome_ingrediente in ingredientes and nome_forma in formas_preparo:
            ing = ingredientes[nome_ingrediente]
            forma = formas_preparo[nome_forma]

            # Calcular valores nutricionais ajustados pelo fator de correção
            fator = forma['fator_correcao']

            cursor.execute("""
                INSERT INTO preparacoes
                (ingrediente_id, forma_preparo_id, nome_completo,
                 energia_kcal, carboidrato_g, proteina_g, lipidios_g,
                 fibra_alimentar_g, calcio_mg, ferro_mg, sodio_mg,
                 potassio_mg, fosforo_mg, vit_c_mg, vit_a_mg,
                 gordura_saturada_g, colesterol_mg,
                 tempo_preparo_min, dificuldade)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ing['id'], forma['id'], nome_prep,
                ing['energia_kcal'] * fator,
                ing['carboidrato_g'] * fator if ing['carboidrato_g'] else 0,
                ing['proteina_g'] * fator if ing['proteina_g'] else 0,
                ing['lipidios_g'] * fator if ing['lipidios_g'] else 0,
                ing['fibra_alimentar_g'] * fator if ing['fibra_alimentar_g'] else 0,
                ing['calcio_mg'] * fator if ing['calcio_mg'] else 0,
                ing['ferro_mg'] * fator if ing['ferro_mg'] else 0,
                ing['sodio_mg'] * fator if ing['sodio_mg'] else 0,
                ing['potassio_mg'] * fator if ing['potassio_mg'] else 0,
                ing['fosforo_mg'] * fator if ing['fosforo_mg'] else 0,
                ing['vit_c_mg'] * fator if ing['vit_c_mg'] else 0,
                ing['vit_a_mg'] * fator if ing['vit_a_mg'] else 0,
                ing['gordura_saturada_g'] * fator if ing['gordura_saturada_g'] else 0,
                ing['colesterol_mg'] * fator if ing['colesterol_mg'] else 0,
                30, 2  # valores padrão
            ))
            preparacoes_inseridas += 1

    conn.commit()
    print(f"✓ {preparacoes_inseridas} preparações inseridas!")

def inserir_tipos_prato(conn):
    """Insere os tipos de prato conforme estrutura da tese da Rafaela"""
    cursor = conn.cursor()

    # Baseado na estrutura da Rafaela:
    # BC1 - pão ou outro cereal
    # DP - laticínios
    # FT - fruta
    # RC - arroz
    # BE - feijão
    # EN - entrada
    # MD - principal
    # SD - guarnição
    # JC - suco
    # DS - sobremesa
    # BC2 - pão ou outro cereal

    tipos_prato = [
        ('BC1 - Cereal (Café)', 1),
        ('DP - Laticínios', 2),
        ('FT - Fruta', 3),
        ('RC - Arroz', 4),
        ('BE - Feijão', 5),
        ('EN - Entrada', 6),
        ('MD - Principal (Carne)', 7),
        ('SD - Guarnição', 8),
        ('JC - Suco', 9),
        ('DS - Sobremesa', 10),
        ('BC2 - Cereal (Almoço)', 11),
    ]

    cursor.executemany("""
        INSERT INTO tipos_prato (nome, ordem_servico)
        VALUES (?, ?)
    """, tipos_prato)

    conn.commit()
    print(f"✓ {len(tipos_prato)} tipos de prato inseridos!")

def inserir_pratos(conn):
    """Cria pratos combinando preparações"""
    cursor = conn.cursor()

    # Buscar tipos de prato
    cursor.execute("SELECT id, nome FROM tipos_prato")
    tipos = {row['nome']: row['id'] for row in cursor.fetchall()}

    # Buscar preparações
    cursor.execute("SELECT id, nome_completo, lipidios_g, energia_kcal, proteina_g, carboidrato_g FROM preparacoes")
    preparacoes = {row['nome_completo']: dict(row) for row in cursor.fetchall()}

    # Definição dos pratos (nome, tipo, cor, consistencia, textura, temperatura, preparacoes)
    pratos_definicoes = [
        # CAFÉ DA MANHÃ
        ('Pão francês com queijo branco', 'BC1 - Cereal (Café)', 'branco', 'sólido', 'macia', 'morno',
         [('Pão francês', 50), ('Queijo branco fatiado', 30)]),
        ('Pão francês com manteiga', 'BC1 - Cereal (Café)', 'branco', 'sólido', 'macia', 'morno',
         [('Pão francês', 50), ('Manteiga', 10)]),
        ('Aveia com leite', 'BC1 - Cereal (Café)', 'branco', 'pastoso', 'cremosa', 'quente',
         [('Aveia em flocos', 40), ('Leite integral', 200)]),

        ('Leite integral', 'DP - Laticínios', 'branco', 'líquido', 'fluida', 'frio',
         [('Leite integral', 200)]),
        ('Iogurte natural', 'DP - Laticínios', 'branco', 'pastoso', 'cremosa', 'frio',
         [('Iogurte natural', 170)]),

        # ALMOÇO - ARROZ
        ('Arroz branco cozido', 'RC - Arroz', 'branco', 'sólido', 'solta', 'quente',
         [('Arroz branco cozido', 100)]),
        ('Arroz integral cozido', 'RC - Arroz', 'marrom', 'sólido', 'solta', 'quente',
         [('Arroz integral cozido', 100)]),
        ('Arroz à grega', 'RC - Arroz', 'branco', 'sólido', 'solta', 'quente',
         [('Arroz branco cozido', 80), ('Cenoura cozida', 20)]),

        # ALMOÇO - FEIJÃO
        ('Feijão carioca cozido', 'BE - Feijão', 'marrom', 'pastoso', 'cremosa', 'quente',
         [('Feijão carioca cozido', 100)]),
        ('Feijão preto cozido', 'BE - Feijão', 'preto', 'pastoso', 'cremosa', 'quente',
         [('Feijão preto cozido', 100)]),

        # ALMOÇO - ENTRADA (SALADAS)
        ('Salada de alface', 'EN - Entrada', 'verde', 'sólido', 'crocante', 'frio',
         [('Salada de alface', 80)]),
        ('Salada mista', 'EN - Entrada', 'verde', 'sólido', 'crocante', 'frio',
         [('Salada de alface', 50), ('Tomate cru', 30), ('Cenoura cozida', 20)]),
        ('Salada de tomate', 'EN - Entrada', 'vermelho', 'sólido', 'macia', 'frio',
         [('Tomate cru', 100)]),

        # ALMOÇO - PRINCIPAL (CARNES)
        ('Peito de frango grelhado', 'MD - Principal (Carne)', 'branco', 'sólido', 'firme', 'quente',
         [('Peito de frango grelhado', 120)]),
        ('Coxa de frango assada', 'MD - Principal (Carne)', 'marrom', 'sólido', 'firme', 'quente',
         [('Coxa de frango assada', 120)]),
        ('Filé de peixe grelhado', 'MD - Principal (Carne)', 'branco', 'sólido', 'macia', 'quente',
         [('Filé de peixe grelhado', 120)]),
        ('Salmão grelhado', 'MD - Principal (Carne)', 'laranja', 'sólido', 'macia', 'quente',
         [('Salmão grelhado', 120)]),
        ('Carne bovina cozida', 'MD - Principal (Carne)', 'marrom', 'sólido', 'firme', 'quente',
         [('Carne bovina cozida', 100)]),
        ('Carne bovina assada', 'MD - Principal (Carne)', 'marrom', 'sólido', 'firme', 'quente',
         [('Carne bovina assada', 100)]),
        ('Lombo suíno assado', 'MD - Principal (Carne)', 'marrom', 'sólido', 'firme', 'quente',
         [('Lombo suíno assado', 100)]),
        ('Ovo cozido', 'MD - Principal (Carne)', 'branco', 'sólido', 'firme', 'quente',
         [('Ovo cozido', 2)]),

        # ALMOÇO - GUARNIÇÃO
        ('Couve refogada', 'SD - Guarnição', 'verde', 'sólido', 'macia', 'quente',
         [('Couve refogada', 80)]),
        ('Brócolis cozido', 'SD - Guarnição', 'verde', 'sólido', 'macia', 'quente',
         [('Brócolis cozido', 80)]),
        ('Cenoura cozida', 'SD - Guarnição', 'laranja', 'sólido', 'macia', 'quente',
         [('Cenoura cozida', 80)]),
        ('Abobrinha grelhada', 'SD - Guarnição', 'verde', 'sólido', 'macia', 'quente',
         [('Abobrinha grelhada', 80)]),
        ('Chuchu cozido', 'SD - Guarnição', 'branco', 'sólido', 'macia', 'quente',
         [('Chuchu cozido', 80)]),
        ('Beterraba cozida', 'SD - Guarnição', 'roxo', 'sólido', 'macia', 'quente',
         [('Beterraba cozida', 80)]),
        ('Purê de batata', 'SD - Guarnição', 'branco', 'pastoso', 'cremosa', 'quente',
         [('Purê de batata', 100)]),
        ('Pirão', 'SD - Guarnição', 'branco', 'pastoso', 'cremosa', 'quente',
         [('Pirão', 100)]),
        ('Farofa de mandioca', 'SD - Guarnição', 'amarelo', 'sólido', 'solta', 'quente',
         [('Farofa de mandioca', 60)]),

        # SUCOS
        ('Suco de laranja', 'JC - Suco', 'laranja', 'líquido', 'fluida', 'frio',
         [('Suco de laranja', 200)]),
        ('Suco de abacaxi', 'JC - Suco', 'amarelo', 'líquido', 'fluida', 'frio',
         [('Suco de abacaxi', 200)]),

        # FRUTAS
        ('Banana', 'FT - Fruta', 'amarelo', 'sólido', 'macia', 'temperatura ambiente',
         [('Banana in natura', 100)]),
        ('Maçã', 'FT - Fruta', 'vermelho', 'sólido', 'crocante', 'temperatura ambiente',
         [('Maçã in natura', 100)]),
        ('Mamão', 'FT - Fruta', 'laranja', 'sólido', 'macia', 'temperatura ambiente',
         [('Mamão in natura', 150)]),
        ('Melancia', 'FT - Fruta', 'vermelho', 'sólido', 'macia', 'frio',
         [('Melancia in natura', 150)]),
        ('Uva', 'FT - Fruta', 'roxo', 'sólido', 'macia', 'frio',
         [('Uva in natura', 100)]),
        ('Manga', 'FT - Fruta', 'amarelo', 'sólido', 'macia', 'temperatura ambiente',
         [('Manga in natura', 150)]),
    ]

    pratos_inseridos = 0
    for prato_info in pratos_definicoes:
        nome = prato_info[0]
        tipo_nome = prato_info[1]
        cor = prato_info[2]
        consistencia = prato_info[3]
        textura = prato_info[4]
        temperatura = prato_info[5]
        preparacoes_prato = prato_info[6]

        if tipo_nome in tipos:
            # Calcular valores nutricionais totais do prato
            total_energia = 0
            total_lipidios = 0
            total_proteina = 0
            total_carboidrato = 0
            total_fibra = 0
            total_calcio = 0
            total_ferro = 0
            total_sodio = 0
            total_custo = 0
            porcao_total = sum(qtd for _, qtd in preparacoes_prato)

            for nome_prep, qtd in preparacoes_prato:
                if nome_prep in preparacoes:
                    prep = preparacoes[nome_prep]
                    fator = qtd / 100.0  # converter para porção
                    total_energia += prep['energia_kcal'] * fator
                    total_lipidios += prep['lipidios_g'] * fator
                    total_proteina += prep['proteina_g'] * fator
                    total_carboidrato += prep['carboidrato_g'] * fator

            cursor.execute("""
                INSERT INTO pratos
                (nome, tipo_prato_id, cor_predominante, consistencia, textura,
                 temperatura_servimento, porcao_padrao_g, energia_kcal, lipidios_g,
                 proteina_g, carboidrato_g, fibra_alimentar_g, calcio_mg, ferro_mg,
                 sodio_mg, custo_total, tempo_producao_min)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                nome, tipos[tipo_nome], cor, consistencia, textura, temperatura,
                porcao_total, total_energia, total_lipidios, total_proteina,
                total_carboidrato, total_fibra, total_calcio, total_ferro,
                total_sodio, total_custo, 30
            ))

            prato_id = cursor.lastrowid

            # Inserir relacionamento prato-preparações
            for nome_prep, qtd in preparacoes_prato:
                cursor.execute("SELECT id FROM preparacoes WHERE nome_completo = ?", (nome_prep,))
                result = cursor.fetchone()
                if result:
                    prep_id = result['id']
                    percentual = (qtd / porcao_total) * 100 if porcao_total > 0 else 0
                    cursor.execute("""
                        INSERT INTO prato_preparacoes
                        (prato_id, preparacao_id, quantidade_g, percentual)
                        VALUES (?, ?, ?, ?)
                    """, (prato_id, prep_id, qtd, percentual))

            pratos_inseridos += 1

    conn.commit()
    print(f"✓ {pratos_inseridos} pratos inseridos!")

def inserir_dietas(conn):
    """Insere as 11 dietas do hospital, cada uma com variante com/sem sal"""
    cursor = conn.cursor()

    dietas = [
        # (nome, descricao, com_sal)
        ('Padrão c/ sal', 'Dieta padrão do hospital — preparo tradicional com sal', 1),
        ('Padrão s/ sal', 'Dieta padrão — preparo sem adição de sal', 0),
        ('Branda c/ sal', 'Dieta branda — alimentos cozidos e de fácil mastigação, com sal', 1),
        ('Branda s/ sal', 'Dieta branda — alimentos cozidos e de fácil mastigação, sem sal', 0),
        ('Pastosa c/ sal', 'Dieta pastosa — purês e alimentos triturados, com sal', 1),
        ('Pastosa s/ sal', 'Dieta pastosa — purês e alimentos triturados, sem sal', 0),
        ('Líquida c/ sal', 'Dieta líquida — sopas, caldos e sucos, com sal', 1),
        ('Líquida s/ sal', 'Dieta líquida — sopas, caldos e sucos, sem sal', 0),
        ('Hipossódica c/ sal leve', 'Dieta hipossódica — restrição moderada de sódio', 1),
        ('Hipossódica s/ sal', 'Dieta hipossódica — restrição severa, sem sal', 0),
        ('Diabético c/ sal', 'Dieta para diabetes — controle de carboidratos, com sal', 1),
        ('Diabético s/ sal', 'Dieta para diabetes — controle de carboidratos, sem sal', 0),
        ('Hipercalórica c/ sal', 'Dieta hipercalórica — alta densidade energética, com sal', 1),
        ('Hipercalórica s/ sal', 'Dieta hipercalórica — alta densidade energética, sem sal', 0),
        ('Hipocalórica c/ sal', 'Dieta hipocalórica — restrição calórica, com sal', 1),
        ('Hipocalórica s/ sal', 'Dieta hipocalórica — restrição calórica, sem sal', 0),
        ('Hiperproteica c/ sal', 'Dieta hiperproteica — alto teor proteico, com sal', 1),
        ('Hiperproteica s/ sal', 'Dieta hiperproteica — alto teor proteico, sem sal', 0),
        ('DASH c/ sal', 'Dieta DASH — controle pressão arterial, sódio moderado', 1),
        ('DASH s/ sal', 'Dieta DASH — controle pressão arterial, sem sal', 0),
        ('Nefropata c/ sal controlado', 'Dieta para nefropatia — restrição de K, P e Na, com sal mínimo', 1),
        ('Nefropata s/ sal', 'Dieta para nefropatia — restrição de K, P e Na, sem sal', 0),
    ]

    cursor.executemany("""
        INSERT INTO dietas (nome, descricao, com_sal)
        VALUES (?, ?, ?)
    """, dietas)

    conn.commit()
    print(f"✓ {len(dietas)} dietas inseridas!")
    return {row['nome']: row['id'] for row in cursor.execute("SELECT id, nome FROM dietas")}


def gerar_variacoes_preparacao(conn, dietas_ids):
    """Gera automaticamente as variações 'sem sal' para cada preparação"""
    cursor = conn.cursor()

    # Buscar todas as preparações
    cursor.execute("""
        SELECT id, nome_completo, sodio_mg, energia_kcal, lipidios_g,
               gordura_saturada_g, carboidrato_g, proteina_g, fibra_alimentar_g
        FROM preparacoes
    """)
    preparacoes = cursor.fetchall()

    # Separar dietas com sal e sem sal
    dietas_com_sal = {nome: did for nome, did in dietas_ids.items() if 's/ sal' not in nome}
    dietas_sem_sal = {nome: did for nome, did in dietas_ids.items() if 's/ sal' in nome}

    variacoes_total = 0

    for prep in preparacoes:
        prep_id = prep['id']
        nome_base = prep['nome_completo']

        # Para dietas COM sal: usa os valores originais da preparação
        for nome_dieta, dieta_id in dietas_com_sal.items():
            # Só gera variação se o nome for diferente (ex: "Hipossódica c/ sal leve" tem preparo diferente)
            # Para dieta padrão com sal, a preparação original já serve
            cursor.execute("""
                INSERT OR IGNORE INTO variacoes_preparacao
                (preparacao_id, dieta_id, nome_exibicao, sodio_mg, energia_kcal,
                 lipidios_g, gordura_saturada_g, carboidrato_g, proteina_g, fibra_alimentar_g,
                 observacoes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                prep_id, dieta_id, nome_base,
                prep['sodio_mg'], prep['energia_kcal'],
                prep['lipidios_g'], prep['gordura_saturada_g'],
                prep['carboidrato_g'], prep['proteina_g'], prep['fibra_alimentar_g'],
                'Preparo tradicional com sal'
            ))
            variacoes_total += 1

        # Para dietas SEM sal: sódio zerado, demais nutrientes mantidos
        for nome_dieta, dieta_id in dietas_sem_sal.items():
            nome_sem_sal = f"{nome_base} (s/sal)"
            cursor.execute("""
                INSERT OR IGNORE INTO variacoes_preparacao
                (preparacao_id, dieta_id, nome_exibicao, sodio_mg, energia_kcal,
                 lipidios_g, gordura_saturada_g, carboidrato_g, proteina_g, fibra_alimentar_g,
                 observacoes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                prep_id, dieta_id, nome_sem_sal,
                0, prep['energia_kcal'],
                prep['lipidios_g'], prep['gordura_saturada_g'],
                prep['carboidrato_g'], prep['proteina_g'], prep['fibra_alimentar_g'],
                'Preparo sem adição de sal — sódio apenas do alimento in natura'
            ))
            variacoes_total += 1

    conn.commit()
    print(f"✓ {variacoes_total} variações de preparação geradas!")
    return variacoes_total


def verificar_dados(conn):
    """Verifica e exibe resumo dos dados inseridos"""
    cursor = conn.cursor()

    print("\n" + "="*60)
    print("RESUMO DOS DADOS INSERIDOS")
    print("="*60)

    tabelas = {
        'ingredientes': 'Ingredientes',
        'formas_preparo': 'Formas de Preparo',
        'preparacoes': 'Preparações',
        'tipos_prato': 'Tipos de Prato',
        'pratos': 'Pratos',
        'prato_preparacoes': 'Relações Prato-Preparação',
        'dietas': 'Dietas',
        'variacoes_preparacao': 'Variações de Preparação'
    }

    for tabela, descricao in tabelas.items():
        cursor.execute(f"SELECT COUNT(*) FROM {tabela}")
        count = cursor.fetchone()[0]
        print(f"✓ {descricao}: {count} registros")

    # Verificar distribuição de gorduras nos pratos
    print("\n" + "-"*60)
    print("DISTRIBUIÇÃO DE LIPÍDIOS NOS PRATOS (foco da otimização)")
    print("-"*60)

    cursor.execute("""
        SELECT
            MIN(lipidios_g) as min_lipidios,
            MAX(lipidios_g) as max_lipidios,
            AVG(lipidios_g) as media_lipidios,
            COUNT(*) as total_pratos
        FROM pratos
    """)
    stats = cursor.fetchone()
    print(f"Mínimo: {stats['min_lipidios']:.2f}g")
    print(f"Máximo: {stats['max_lipidios']:.2f}g")
    print(f"Média: {stats['media_lipidios']:.2f}g")
    print(f"Total de pratos: {stats['total_pratos']}")

    # Pratos com menor e maior gordura
    print("\nPratos com MENOS gordura (top 5):")
    cursor.execute("""
        SELECT nome, lipidios_g, tipo_prato_id
        FROM pratos
        ORDER BY lipidios_g ASC
        LIMIT 5
    """)
    for row in cursor.fetchall():
        print(f"  - {row['nome']}: {row['lipidios_g']:.2f}g")

    print("\nPratos com MAIS gordura (top 5):")
    cursor.execute("""
        SELECT nome, lipidios_g, tipo_prato_id
        FROM pratos
        ORDER BY lipidios_g DESC
        LIMIT 5
    """)
    for row in cursor.fetchall():
        print(f"  - {row['nome']}: {row['lipidios_g']:.2f}g")

    print("="*60)

def main():
    """Função principal"""
    print("="*60)
    print("POPULAR BANCO DE DADOS - CARDÁPIO HOSPITALAR")
    print("Épico 1: Gestão de Dados Mestres")
    print("="*60)

    # Criar conexão
    conn = criar_conexao()
    print("\n✓ Conexão com banco de dados estabelecida (FKs ativadas)")

    try:
        # Criar tabelas
        print("\n[1/8] Criando tabelas...")
        criar_tabelas(conn)

        # Inserir formas de preparo
        print("\n[2/8] Inserindo formas de preparo...")
        inserir_formas_preparo(conn)

        # Inserir ingredientes
        print("\n[3/8] Inserindo ingredientes...")
        inserir_ingredientes(conn)

        # Inserir preparações
        print("\n[4/8] Inserindo preparações...")
        inserir_preparacoes(conn)

        # Inserir tipos de prato
        print("\n[5/8] Inserindo tipos de prato...")
        inserir_tipos_prato(conn)

        # Inserir pratos
        print("\n[6/8] Inserindo pratos...")
        inserir_pratos(conn)

        # Inserir dietas
        print("\n[7/8] Inserindo dietas...")
        dietas_ids = inserir_dietas(conn)

        # Gerar variações de preparação para cada dieta
        print("\n[8/8] Gerando variações de preparação por dieta...")
        gerar_variacoes_preparacao(conn, dietas_ids)

        # Verificar dados
        verificar_dados(conn)

        print("\n✓ Banco de dados populado com sucesso!")
        print("✓ Pronto para o Épico 2: Configuração de Dietas e Refeições")

    except Exception as e:
        print(f"\n✗ Erro ao popular banco de dados: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    main()
