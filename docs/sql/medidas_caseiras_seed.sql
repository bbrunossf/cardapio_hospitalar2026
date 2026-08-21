-- Medidas caseiras → gramas — SEED PROPOSTO (20/08/2026)
-- Revisar os valores pelo Bruno ANTES de executar (regra: dados manuais são do Bruno).
-- Fontes: TACO (tabela oficial), rotulagem de produto, estimativa (média prática).
-- Idempotente MESMO com alimento_padrao NULL: no SQLite UNIQUE não deduplica NULL
-- (NULL != NULL) — cada linha usa INSERT...SELECT com WHERE NOT EXISTS.
--
-- Executar (depois de revisar):
--   sqlite3 cardapio_hospitalar.db < docs/sql/medidas_caseiras_seed.sql
-- Conferir:
--   SELECT unidade, alimento_padrao, gramas, fonte FROM medidas_caseiras;
--
-- Convenção de unidades (alinhada ao vocabulário do LLM em /estruturar-registro):
--   fatia, copo, xicara, xicara_cafe, colher_sopa, colher_sobremesa,
--   colher_cha, concha, unidade  (+ g, kg, ml diretos)

INSERT INTO medidas_caseiras (unidade, alimento_padrao, gramas, fonte)
SELECT 'fatia', 'pão de forma', 25, 'rotulagem'
WHERE NOT EXISTS (SELECT 1 FROM medidas_caseiras
                  WHERE unidade = 'fatia' AND alimento_padrao IS 'pão de forma');

INSERT INTO medidas_caseiras (unidade, alimento_padrao, gramas, fonte)
SELECT 'fatia', NULL, 20, 'estimativa'
WHERE NOT EXISTS (SELECT 1 FROM medidas_caseiras
                  WHERE unidade = 'fatia' AND alimento_padrao IS NULL);

INSERT INTO medidas_caseiras (unidade, alimento_padrao, gramas, fonte)
SELECT 'copo', 'copo americano', 200, 'taco'
WHERE NOT EXISTS (SELECT 1 FROM medidas_caseiras
                  WHERE unidade = 'copo' AND alimento_padrao IS 'copo americano');

INSERT INTO medidas_caseiras (unidade, alimento_padrao, gramas, fonte)
SELECT 'copo', NULL, 200, 'estimativa'
WHERE NOT EXISTS (SELECT 1 FROM medidas_caseiras
                  WHERE unidade = 'copo' AND alimento_padrao IS NULL);

INSERT INTO medidas_caseiras (unidade, alimento_padrao, gramas, fonte)
SELECT 'xicara', NULL, 240, 'taco'
WHERE NOT EXISTS (SELECT 1 FROM medidas_caseiras
                  WHERE unidade = 'xicara' AND alimento_padrao IS NULL);

INSERT INTO medidas_caseiras (unidade, alimento_padrao, gramas, fonte)
SELECT 'xicara_cafe', NULL, 50, 'taco'
WHERE NOT EXISTS (SELECT 1 FROM medidas_caseiras
                  WHERE unidade = 'xicara_cafe' AND alimento_padrao IS NULL);

INSERT INTO medidas_caseiras (unidade, alimento_padrao, gramas, fonte)
SELECT 'colher_sopa', NULL, 15, 'taco'
WHERE NOT EXISTS (SELECT 1 FROM medidas_caseiras
                  WHERE unidade = 'colher_sopa' AND alimento_padrao IS NULL);

INSERT INTO medidas_caseiras (unidade, alimento_padrao, gramas, fonte)
SELECT 'colher_sobremesa', NULL, 10, 'taco'
WHERE NOT EXISTS (SELECT 1 FROM medidas_caseiras
                  WHERE unidade = 'colher_sobremesa' AND alimento_padrao IS NULL);

INSERT INTO medidas_caseiras (unidade, alimento_padrao, gramas, fonte)
SELECT 'colher_cha', NULL, 5, 'taco'
WHERE NOT EXISTS (SELECT 1 FROM medidas_caseiras
                  WHERE unidade = 'colher_cha' AND alimento_padrao IS NULL);

INSERT INTO medidas_caseiras (unidade, alimento_padrao, gramas, fonte)
SELECT 'concha', NULL, 100, 'estimativa'
WHERE NOT EXISTS (SELECT 1 FROM medidas_caseiras
                  WHERE unidade = 'concha' AND alimento_padrao IS NULL);

-- Correções da análise do registro #1 (20/08/2026):
--   1. Café: o LLM devolve "xicara" (não "xicara_cafe") — regra específica evita
--      a genérica de 240g (2 xícaras de café viraram 480g no registro #1)
--   2. "unidade" para alimentos comuns, para não depender de ajuste manual
INSERT INTO medidas_caseiras (unidade, alimento_padrao, gramas, fonte)
SELECT 'xicara', 'café', 50, 'estimativa'
WHERE NOT EXISTS (SELECT 1 FROM medidas_caseiras
                  WHERE unidade = 'xicara' AND alimento_padrao IS 'café');

INSERT INTO medidas_caseiras (unidade, alimento_padrao, gramas, fonte)
SELECT 'unidade', 'ovo', 50, 'estimativa'
WHERE NOT EXISTS (SELECT 1 FROM medidas_caseiras
                  WHERE unidade = 'unidade' AND alimento_padrao IS 'ovo');

-- Limpeza de duplicadas da execução anterior (rodar UMA vez, com o banco parado):
--   DELETE FROM medidas_caseiras WHERE id NOT IN (
--       SELECT MIN(id) FROM medidas_caseiras
--       GROUP BY unidade, COALESCE(alimento_padrao, ''));
--
-- Ideias para complementar (REVISAR valores antes de incluir):
--   ('unidade', 'rap dez', 120, 'rotulagem'),  -- 1 wrap Rap10 com recheio (~120 g? conferir rótulo)
--   ('unidade', 'banana', 100, 'estimativa'),   -- banana-prata média sem casca
--   ('unidade', 'maca',   130, 'estimativa'),   -- maçã média
--   ('unidade', 'laranja',130, 'estimativa'),   -- laranja-pera média
--   ('prato_fundo', NULL, 300, 'estimativa'),   -- prato fundo de sopa cheio
--   ('fatia', 'queijo prato', 15, 'rotulagem'),
--   ('fatia', 'presunto', 15, 'rotulagem'),
--   ('colher_sopa', 'arroz cozido', 20, 'taco'),
--   ('colher_sopa', 'feijao cozido', 18, 'taco');
