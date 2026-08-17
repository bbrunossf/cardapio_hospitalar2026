-- Personalização por paciente — tabelas de REGRAS por paciente (catálogo permanece global)
-- Espelham o schema das tabelas de regra existentes, com paciente_id + preenchimento opcional (delta).
-- Executar: sqlite3 cardapio_hospitalar.db < docs/sql/personalizacao_por_paciente.sql
-- Conferir: PRAGMA table_info(<tabela>);
-- Documentação: docs/personalizacao_por_paciente.md

-- 1. Faixas nutricionais por paciente (espelho de restricoes_nutricionais_dieta)
CREATE TABLE IF NOT EXISTS restricoes_nutricionais_paciente (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paciente_id INTEGER NOT NULL REFERENCES pacientes(id) ON DELETE CASCADE,
    nutriente VARCHAR(50) NOT NULL,        -- energia_kcal, sodio_mg, potassio_mg, fosforo_mg, fibra_alimentar_g...
    valor_minimo DECIMAL(10,2),
    valor_maximo DECIMAL(10,2),
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    editado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    desativado BOOLEAN DEFAULT 0,
    CHECK (valor_minimo IS NOT NULL OR valor_maximo IS NOT NULL)
);

-- 2. Elegibilidade por paciente (espelho de regras_elegibilidade_dieta)
CREATE TABLE IF NOT EXISTS regras_elegibilidade_paciente (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paciente_id INTEGER NOT NULL REFERENCES pacientes(id) ON DELETE CASCADE,
    atributo VARCHAR(50) NOT NULL,         -- consistencia, textura, cor_predominante, temperatura_servimento, tipo_prato
    valores_permitidos TEXT NOT NULL,      -- 'PASTOSA;LÍQUIDA' (separador ;)
    operador VARCHAR(20) NOT NULL DEFAULT 'IN',  -- IN (interseção) | NOT IN (subtração)
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    editado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    desativado BOOLEAN DEFAULT 0,
    CHECK (operador IN ('IN','NOT IN'))
);

-- 3. Variedade/aversão por paciente (espelho de regras_variedade)
CREATE TABLE IF NOT EXISTS regras_variedade_paciente (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paciente_id INTEGER NOT NULL REFERENCES pacientes(id) ON DELETE CASCADE,
    tipo_prato_id INTEGER NOT NULL REFERENCES tipos_preparacoes(id) ON DELETE CASCADE,
    dias_minimos_repeticao INTEGER,
    frequencia_maxima_semanal INTEGER,     -- 0 = nunca servir (aversão)
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    editado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    desativado BOOLEAN DEFAULT 0
);

-- 4. Exclusões por paciente (prato OU ingrediente — CHECK garante exatamente um)
CREATE TABLE IF NOT EXISTS exclusoes_paciente (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paciente_id INTEGER NOT NULL REFERENCES pacientes(id) ON DELETE CASCADE,
    prato_id INTEGER REFERENCES pratos(id) ON DELETE CASCADE,
    ingrediente_id INTEGER REFERENCES ingredientes(id) ON DELETE CASCADE,
    motivo TEXT,
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    editado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    desativado BOOLEAN DEFAULT 0,
    CHECK ((prato_id IS NOT NULL) + (ingrediente_id IS NOT NULL) = 1)
);

CREATE INDEX IF NOT EXISTS idx_rnp_paciente ON restricoes_nutricionais_paciente(paciente_id);
CREATE INDEX IF NOT EXISTS idx_rep_paciente ON regras_elegibilidade_paciente(paciente_id);
CREATE INDEX IF NOT EXISTS idx_rvp_paciente ON regras_variedade_paciente(paciente_id, tipo_prato_id);
CREATE INDEX IF NOT EXISTS idx_ep_paciente ON exclusoes_paciente(paciente_id);
