-- Registro Alimentar 48h — DDL (19/08/2026)
-- Executar: sqlite3 cardapio_hospitalar.db < docs/sql/registro_alimentar_48h.sql
-- Conferir: PRAGMA table_info(registro_alimentar_itens);
--
-- Convenções do banco: id INTEGER PRIMARY KEY AUTOINCREMENT,
-- criado_em/editado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
-- desativado BOOLEAN DEFAULT 0, DECIMAL(8,2) p/ quantidades.

-- 1. Cabeçalho do registro alimentar (um registro = relato de 48h de um paciente)
CREATE TABLE IF NOT EXISTS registros_alimentares (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paciente_id INTEGER NOT NULL REFERENCES pacientes(id) ON DELETE CASCADE,
    data_inicio DATE NOT NULL,               -- início do período de 48h relatado
    data_fim DATE NOT NULL,                  -- data_inicio + 1 dia
    texto_original TEXT NOT NULL,            -- relato cru (colado pelo nutricionista)
    status TEXT NOT NULL DEFAULT 'rascunho'
        CHECK (status IN ('rascunho', 'processado', 'revisado')),
    criado_por INTEGER REFERENCES usuarios(id),
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    editado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    desativado BOOLEAN DEFAULT 0
);

-- 2. Itens estruturados do registro (um por alimento/refeição relatado)
CREATE TABLE IF NOT EXISTS registro_alimentar_itens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    registro_id INTEGER NOT NULL
        REFERENCES registros_alimentares(id) ON DELETE CASCADE,
    dia INTEGER NOT NULL CHECK (dia IN (1, 2)),
    refeicao TEXT NOT NULL CHECK (refeicao IN (
        'cafe_da_manha', 'colacao', 'almoco', 'lanche',
        'jantar', 'ceia', 'outro')),
    ordem INTEGER NOT NULL DEFAULT 0,        -- ordem em que aparece no relato
    descricao TEXT NOT NULL,                 -- texto do paciente (ex.: "2 fatias de pão integral")
    quantidade_texto TEXT,                   -- "2 fatias", "1 copo", "200 g" (como relatado)
    quantidade_g DECIMAL(8,2),               -- convertido p/ gramas; NULL = revisar
    origem TEXT NOT NULL DEFAULT 'estimado'
        CHECK (origem IN ('prato', 'industrializado', 'ingrediente', 'estimado')),
    prato_id INTEGER REFERENCES pratos(id),
    industrializado_id INTEGER REFERENCES alimentos_industrializados(id),
    ingrediente_id INTEGER REFERENCES ingredientes(id),
    estimado BOOLEAN NOT NULL DEFAULT 0,     -- 1 ⇒ badge ESTIMADO na UI
    -- Nutrientes calculados na hora do processamento (auditoria)
    energia_kcal DECIMAL(8,2),
    carboidratos_g DECIMAL(8,2),
    proteinas_g DECIMAL(8,2),
    gorduras_totais_g DECIMAL(8,2),
    fibras_g DECIMAL(8,2),
    sodio_mg DECIMAL(8,2),
    calcio_mg DECIMAL(8,2),
    ferro_mg DECIMAL(8,2),
    potassio_mg DECIMAL(8,2),
    fosforo_mg DECIMAL(8,2),
    vit_c_mg DECIMAL(8,2),
    observacao TEXT,                         -- ex.: "porção assumida: 1 fatia = 25 g (medidas_caseiras)"
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    editado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    desativado BOOLEAN DEFAULT 0,
    -- FK exclusiva: exatamente uma preenchida, conforme a origem
    CHECK (
        (origem = 'prato'           AND prato_id IS NOT NULL
                                    AND industrializado_id IS NULL
                                    AND ingrediente_id IS NULL)
        OR
        (origem = 'industrializado' AND industrializado_id IS NOT NULL
                                    AND prato_id IS NULL
                                    AND ingrediente_id IS NULL)
        OR
        (origem = 'ingrediente'     AND ingrediente_id IS NOT NULL
                                    AND prato_id IS NULL
                                    AND industrializado_id IS NULL)
        OR
        (origem = 'estimado'        AND prato_id IS NULL
                                    AND industrializado_id IS NULL
                                    AND ingrediente_id IS NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_reg_alim_itens_registro
    ON registro_alimentar_itens(registro_id);
CREATE INDEX IF NOT EXISTS idx_reg_alim_paciente
    ON registros_alimentares(paciente_id);

-- 3. Conversão de medidas caseiras → gramas
--    Match: alimento específico primeiro (alimento_padrao preenchido),
--    senão genérico (alimento_padrao NULL). fonte = origem do valor.
CREATE TABLE IF NOT EXISTS medidas_caseiras (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    unidade TEXT NOT NULL,                   -- fatia, copo, xicara, colher_sopa, concha...
    alimento_padrao TEXT,                    -- NULL = genérico; ex.: 'pão de forma'
    gramas DECIMAL(8,2) NOT NULL,            -- conversão média
    fonte TEXT DEFAULT 'taco',               -- taco | rotulagem | estimativa
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    editado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    desativado BOOLEAN DEFAULT 0,
    UNIQUE (unidade, alimento_padrao)
);

-- Exemplos iniciais (valores a conferir pelo Bruno na revisão)
-- INSERT INTO medidas_caseiras (unidade, alimento_padrao, gramas, fonte) VALUES
--     ('fatia', 'pão de forma', 25, 'rotulagem'),
--     ('fatia', NULL, 20, 'estimativa'),
--     ('copo', 'copo americano', 200, 'taco'),
--     ('xicara', NULL, 240, 'taco'),
--     ('colher_sopa', NULL, 15, 'taco'),
--     ('concha', NULL, 100, 'estimativa');
