### novo status de onde parei:
os dados no banco de dados, na tabela 'pratos', ainda são dados mockados.
Preciso pegar os pratos da tabela original Excel, e relacionar eles com os ingredientes que estão corretos.
Posso fazer isso inicialmente limpando a tabela 'pratos', e inserindo novamente com os id's.
E também fazer uma interface que leia a composição e exiba a quantidade da porção definida no prato, a soma das massas dos alimentos que compõem o prato, e verifique se a soma não ultrapassa o valor, e também tenha campos para excluir, editar ou inserir novos alimentos.



##apenas como referencia de coisas a fazer:
 criar a nova tabela 'prato_composicao'
 
 criar a view que irá fornecer os dados nutricionais dos pratos através da soma composta dos ingredientes e quantidades de cada prato
 
 excluir as tabelas 'preparacoes', 'variacoes_preparacao', 'formas_preparo' e as colunas de dados nutricionais da tabela 'pratos' (porque agora esses dados vão ficar na view), e a tabela 'prato_preparacoes'
 
 aproveitando, também acho bom renomear (ou melhor, criar uma tabela nova e depois renomear) a tabela 'tipos_prato' para 'tipos_preparacoes'
 
 
 

-- ============================================================
-- Script 002: Criar tabela prato_composicao e view nutricional
-- Cardápio Hospitalar
-- ============================================================
-- Instruções:
--   sqlite3 cardapio_hospitalar.db < 002_prato_composicao.sql
-- ============================================================

BEGIN TRANSACTION;

-- ─── 1. TABELA prato_composicao ────────────────────────────

CREATE TABLE IF NOT EXISTS prato_composicao (
    prato_id INTEGER NOT NULL REFERENCES pratos(id) ON DELETE CASCADE,
    ingrediente_id INTEGER NOT NULL REFERENCES ingredientes(id),
    quantidade_g DECIMAL(8,2) NOT NULL CHECK(quantidade_g > 0),
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    editado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    desativado BOOLEAN DEFAULT 0,
    PRIMARY KEY (prato_id, ingrediente_id)
);

-- ─── 2. VIEW vw_pratos_nutricional ─────────────────────────

CREATE VIEW IF NOT EXISTS vw_pratos_nutricional AS
SELECT
    p.id AS prato_id,
    p.nome AS prato_nome,
    p.porcao_padrao_g,
    p.tipo_prato_id,
    tp.nome AS tipo_prato,
    p.consistencia,
    p.textura,
    p.temperatura_servimento,
    p.cor_predominante,
    p.tempo_producao_min,

    -- Nutrientes calculados dinamicamente (base 100g × quantidade real)
    ROUND(SUM(i.energia_kcal * pc.quantidade_g / 100.0), 2)        AS energia_kcal,
    ROUND(SUM(i.carboidrato_g * pc.quantidade_g / 100.0), 2)       AS carboidrato_g,
    ROUND(SUM(i.proteina_g * pc.quantidade_g / 100.0), 2)          AS proteina_g,
    ROUND(SUM(i.lipidios_g * pc.quantidade_g / 100.0), 2)          AS lipidios_g,
    ROUND(SUM(i.fibra_alimentar_g * pc.quantidade_g / 100.0), 2)   AS fibra_alimentar_g,
    ROUND(SUM(i.calcio_mg * pc.quantidade_g / 100.0), 2)           AS calcio_mg,
    ROUND(SUM(i.ferro_mg * pc.quantidade_g / 100.0), 2)            AS ferro_mg,
    ROUND(SUM(i.sodio_mg * pc.quantidade_g / 100.0), 2)            AS sodio_mg,
    ROUND(SUM(i.potassio_mg * pc.quantidade_g / 100.0), 2)         AS potassio_mg,
    ROUND(SUM(i.fosforo_mg * pc.quantidade_g / 100.0), 2)          AS fosforo_mg,
    ROUND(SUM(i.vit_c_mg * pc.quantidade_g / 100.0), 2)            AS vit_c_mg,
    ROUND(SUM(i.vit_a_mg * pc.quantidade_g / 100.0), 2)            AS vit_a_mg,
    ROUND(SUM(i.gordura_saturada_g * pc.quantidade_g / 100.0), 2)  AS gordura_saturada_g,
    ROUND(SUM(i.colesterol_mg * pc.quantidade_g / 100.0), 2)       AS colesterol_mg,
    ROUND(SUM(i.custo_por_100g * pc.quantidade_g / 100.0), 4)      AS custo_total,

    -- Metadados da composição
    COUNT(pc.ingrediente_id)              AS qtd_ingredientes,
    ROUND(SUM(pc.quantidade_g), 2)        AS massa_total_calculada

FROM pratos p
LEFT JOIN tipos_prato tp ON p.tipo_prato_id = tp.id AND tp.desativado = 0
LEFT JOIN prato_composicao pc ON p.id = pc.prato_id AND pc.desativado = 0
LEFT JOIN ingredientes i ON pc.ingrediente_id = i.id AND i.desativado = 0
WHERE p.desativado = 0
GROUP BY p.id;

COMMIT;

-- ─── 3. VERIFICAÇÃO ────────────────────────────────────────

SELECT '✓ prato_composicao criada' AS status;
SELECT '✓ vw_pratos_nutricional criada' AS status;
