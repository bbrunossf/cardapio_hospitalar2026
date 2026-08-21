-- Preferências alimentares do paciente — hábitos → privilégio na otimização
-- Doc: docs/preferencias_alimentares_paciente.md
-- Executar: sqlite3 cardapio_hospitalar.db < docs/sql/preferencias_alimentares.sql
-- Conferir: PRAGMA table_info(<tabela>);
-- ⚠️ NÃO executar sem aprovação do Bruno (regra 1 do projeto)

-- 1. Catálogo de grupos alimentares (curadoria transversal a tipos_preparacoes)
CREATE TABLE IF NOT EXISTS grupos_alimentares (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome VARCHAR(100) NOT NULL UNIQUE,      -- ex.: 'Pães e cereais', 'Laticínios', 'Frutas'
    descricao TEXT,
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    editado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    desativado BOOLEAN DEFAULT 0
);

-- 2. Vínculo prato ↔ grupo (N:N; um prato pode estar em vários grupos)
CREATE TABLE IF NOT EXISTS prato_grupos (
    prato_id INTEGER NOT NULL REFERENCES pratos(id) ON DELETE CASCADE,
    grupo_id INTEGER NOT NULL REFERENCES grupos_alimentares(id) ON DELETE CASCADE,
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (prato_id, grupo_id)
);

-- 3. Preferências do paciente (privilégio: grupo OU prato — CHECK garante exatamente um)
CREATE TABLE IF NOT EXISTS preferencias_paciente (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paciente_id INTEGER NOT NULL REFERENCES pacientes(id) ON DELETE CASCADE,
    grupo_id INTEGER REFERENCES grupos_alimentares(id) ON DELETE CASCADE,
    prato_id INTEGER REFERENCES pratos(id) ON DELETE CASCADE,
    tipo_refeicao_id INTEGER REFERENCES tipos_refeicao(id) ON DELETE CASCADE,  -- NULL = todas as refeições
    prioridade INTEGER NOT NULL DEFAULT 1,   -- coeficiente do estágio 1 (lexicográfico)
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    editado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    desativado BOOLEAN DEFAULT 0,
    CHECK ((grupo_id IS NOT NULL) + (prato_id IS NOT NULL) = 1)
);

-- 4. Composição por grupo em nível paciente (espelho de regras_composicao por grupo)
CREATE TABLE IF NOT EXISTS regras_composicao_paciente (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paciente_id INTEGER NOT NULL REFERENCES pacientes(id) ON DELETE CASCADE,
    tipo_refeicao_id INTEGER NOT NULL REFERENCES tipos_refeicao(id) ON DELETE CASCADE,
    grupo_id INTEGER NOT NULL REFERENCES grupos_alimentares(id) ON DELETE CASCADE,
    qtd_minima INTEGER,
    qtd_maxima INTEGER,
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    editado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    desativado BOOLEAN DEFAULT 0,
    CHECK (qtd_minima IS NOT NULL OR qtd_maxima IS NOT NULL),
    CHECK (qtd_minima IS NULL OR qtd_maxima IS NULL OR qtd_minima <= qtd_maxima)
);

CREATE INDEX IF NOT EXISTS idx_pg_grupo ON prato_grupos(grupo_id);
CREATE INDEX IF NOT EXISTS idx_pp_paciente ON preferencias_paciente(paciente_id);
CREATE INDEX IF NOT EXISTS idx_rcp_paciente ON regras_composicao_paciente(paciente_id, tipo_refeicao_id);
