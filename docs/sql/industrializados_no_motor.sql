-- Industrializados no motor de otimização (16/08/2026)
-- Executar como: sqlite3 cardapio_hospitalar.db < docs/sql/industrializados_no_motor.sql
-- Ver: docs/industrializados_no_motor.md (seção 3.1)

ALTER TABLE alimentos_industrializados ADD COLUMN tipo_prato_id INTEGER REFERENCES tipos_preparacoes(id);
ALTER TABLE alimentos_industrializados ADD COLUMN cor_predominante TEXT;
ALTER TABLE alimentos_industrializados ADD COLUMN textura TEXT;
ALTER TABLE alimentos_industrializados ADD COLUMN consistencia TEXT;
ALTER TABLE alimentos_industrializados ADD COLUMN temperatura_servimento TEXT;
-- porcao_padrao_g: gramas da porção declarada no rótulo (ex.: 30g p/ "1 biscoito (30g)")
-- preenchimento manual obrigatório — produto sem valor não entra no motor (sem default)
ALTER TABLE alimentos_industrializados ADD COLUMN porcao_padrao_g DECIMAL(8,2);
CREATE INDEX idx_alimentos_industrializados_tipo_prato
    ON alimentos_industrializados(tipo_prato_id);
