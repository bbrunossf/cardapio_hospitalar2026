-- ══════════════════════════════════════════════════════════════════
-- Ficha Técnica das Preparações — schema novo (11/08/2026)
-- Banco: cardapio_hospitalar.db (SQLite)
-- Executar manualmente (Bruno) ANTES de implementar a feature.
-- Convenções seguidas: mesmo estilo de prato_composicao/pratos
-- (criado_em/editado_em DATETIME, desativado BOOLEAN, FK CASCADE).
--
-- Decisões do Bruno (11/08/2026):
--   - custo: fora desta fase (colunas existentes ficam intocadas)
--   - rendimento_porcoes: fora por enquanto (quantidades de
--     prato_composicao são POR PORÇÃO; lote/rendimento fica para o
--     módulo de lista de compras)
-- ══════════════════════════════════════════════════════════════════

-- Modo de preparo em passos (1 passo por linha, ordenado)
CREATE TABLE passos_preparo (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    prato_id    INTEGER NOT NULL REFERENCES pratos(id) ON DELETE CASCADE,
    ordem       INTEGER NOT NULL DEFAULT 1 CHECK(ordem >= 1),
    descricao   TEXT NOT NULL,
    criado_em   DATETIME DEFAULT CURRENT_TIMESTAMP,
    editado_em  DATETIME DEFAULT CURRENT_TIMESTAMP,
    desativado  BOOLEAN DEFAULT 0
);

-- Índice para o WHERE prato_id = ? das consultas da ficha
CREATE INDEX ix_passos_preparo_prato ON passos_preparo(prato_id);
