-- ============================================================================
-- Módulo de Pacientes — DDL
-- Aplicar manualmente no banco cardapio_hospitalar.db antes de usar o módulo.
-- ============================================================================

CREATE TABLE IF NOT EXISTS pacientes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome VARCHAR(150) NOT NULL,
    data_nascimento DATE,
    sexo VARCHAR(1) CHECK (sexo IN ('M', 'F')),
    peso_kg DECIMAL(6, 2),
    altura_cm DECIMAL(6, 2),
    cintura_cm DECIMAL(6, 2),
    quadril_cm DECIMAL(6, 2),
    objetivo VARCHAR(20) DEFAULT 'manter' CHECK (objetivo IN ('ganhar', 'perder', 'manter')),
    observacoes TEXT,
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    editado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    desativado BOOLEAN DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_pacientes_nome ON pacientes(nome);
