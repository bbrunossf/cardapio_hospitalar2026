-- ============================================================================
-- Autenticação — tabela de usuários e papéis + dono de pacientes
-- Plano: docs/autenticacao.md
--
-- Executar:
--   sqlite3 cardapio_hospitalar.db < docs/sql/autenticacao.sql
--
-- Depois criar o admin inicial (NUNCA via INSERT com senha em claro):
--   flask --app app2.py criar-usuario
--
-- Pacientes existentes ficam com criado_por = NULL (só admin os vê até
-- atribuir um nutricionista).
-- ============================================================================

-- ─── Usuários ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    senha_hash TEXT NOT NULL,
    papel TEXT NOT NULL DEFAULT 'nutricionista'
        CHECK (papel IN ('admin','nutricionista','leitura')),
    desativado BOOLEAN NOT NULL DEFAULT 0,
    ultimo_login DATETIME,
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    editado_em DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_usuarios_papel ON usuarios (papel);

-- ─── Dono de pacientes (âncora do escopo por nutricionista) ─────────────────
ALTER TABLE pacientes ADD COLUMN criado_por INTEGER REFERENCES usuarios(id);

CREATE INDEX IF NOT EXISTS idx_pacientes_criado_por ON pacientes (criado_por);
