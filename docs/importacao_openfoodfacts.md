# Importação Open Food Facts → alimentos_industrializados

> Fonte de dados externa para popular `alimentos_industrializados` com produtos
> industrializados vendidos no Brasil. Mapeamento de colunas + conversão 100g→porção.
> Status: **planejado (18/08/2026)** — aguarda revisão do Bruno e execução do script.
> Data: 18/08/2026

## 1. Contexto

O módulo de rótulo (`api/rotulo.py`, `models_rotulo.py`) cadastra produtos em
`alimentos_industrializados` com os nutrientes **da porção declarada no rótulo**
(RDC 429/2020). O cadastro atual é manual (fonte `barcode|ia|ocr|manual`).

O [Open Food Facts](https://openfoodfacts.org) publica o dump completo dos produtos
em CSV (`https://openfoodfacts.org/data` → "products CSV", arquivo grande ~1–2 GB).
Cada linha é um produto com ~400 colunas; as de interesse para este projeto estão
listadas na seção 3. **O OFF entrega nutrientes em base 100g** — a importação precisa
converter para a base do schema (porção do rótulo), usando `serving_quantity`.

A tabela `alimentos_industrializados` já existe (DDL seção 5.2 do
`especificacao_modulo_rotulo.md`) e ganhou colunas novas para o motor
(`docs/sql/industrializados_no_motor.sql` — `tipo_prato_id`, sensoriais,
`porcao_padrao_g`). Este documento define como popular a tabela a partir do OFF.

## 2. Fonte e recorte

- **Arquivo:** dump CSV do OFF (o Bruno extrai o subconjunto de colunas desta seção —
  a lista de colunas que ele passou em 18/08/2026 corresponde ao dump).
- **Recorte automático no script (filtros, seção 4.1):** só produtos do Brasil,
  com tabela nutricional, com energia e com porção declarada.
- **Recorte manual (decisão do Bruno):** o script importa tudo que passa nos filtros.
  Se quiser limitar a categorias (ex.: só lanches/desjejum), o filtro por categoria
  fica para fase 2 — hoje a classificação `tipo_prato_id` é manual/sugerida (seção 5).

## 3. Mapeamento OFF → tabela

Convenção do módulo: **campo ausente → NULL** (nunca 0, nunca estimado).

### 3.1 Identificação

| Coluna OFF | Coluna tabela | Observação |
|---|---|---|
| `code` | `codigo_barras` | EAN; extrair só dígitos; 8–14 dígitos senão descarta |
| `product_name` | `nome` | fallback: `abbreviated_product_name` → `generic_name`; truncar 200 |
| `brands` | `marca` | 1ª marca da lista (split `,`); truncar 100 |
| `brand_owner` | `fabricante` | dono da marca ≈ fabricante; truncar 150 |
| `product_quantity` | `peso_liquido` | numérico, OFF normaliza em gramas → `unidade_peso='g'` |
| `quantity` | — (apoio) | texto ("200 g"); usado só se `product_quantity` vazio (parse) |

### 3.2 Porção

| Coluna OFF | Coluna tabela | Observação |
|---|---|---|
| `serving_quantity` | `porcao_qtd` | numérico (g ou ml) |
| `serving_size` | `porcao_unidade` | `'ml'` se o texto contém "ml", senão `'g'` |
| `serving_quantity` | `porcao_padrao_g` | pré-preenchido (antes era manual obrigatório); 1 ml ≈ 1 g, mesmo critério da view |
| `serving_size` | — (apoio) | texto completo fica fora do banco |

> Sem `serving_quantity` (>0) o produto é **descartado**: sem ela não há conversão
> 100g→porção e a view `vw_alimentos_industrializados_100g` não funciona.

### 3.3 Nutrientes — conversão 100g → porção

`valor_porcao = valor_100g × serving_quantity / 100` (arredondar 2 casas).
Valores negativos no OFF (erro de edição) → NULL.

| Coluna OFF (100g) | Coluna tabela (porção) |
|---|---|
| `energy-kcal_100g` | `energia_kcal` |
| `carbohydrates_100g` | `carboidratos_g` |
| `sugars_100g` | `acucares_totais_g` |
| `added-sugars_100g` | `acucares_adicionados_g` (cobertura baixa no OFF — virá NULL com frequência) |
| `proteins_100g` | `proteinas_g` |
| `fat_100g` | `gorduras_totais_g` |
| `saturated-fat_100g` | `gorduras_saturadas_g` |
| `trans-fat_100g` | `gorduras_trans_g` |
| `fiber_100g` | `fibras_g` |
| `sodium_100g` | `sodio_mg` |

Usar **sempre** `energy-kcal_100g` (não `energy_100g`, que é kJ). Potássio
(`potassium_100g`) **não é importado** — ver decisão 6.1.

### 3.4 Rótulo

| Coluna OFF | Coluna tabela | Observação |
|---|---|---|
| `ingredients_text` | `ingredientes_lista` | texto em PT (filtro Brasil) |
| `allergens_en` | `alergenos` | JSON array em PT (mapa de tradução de alérgenos comuns); ver 6.2 |
| `traces_en` | — (fora) | "pode conter" não entra na fase 1 (decisão 6.2) |

### 3.5 Controle

`fonte='barcode'` (único valor compatível com o CHECK da tabela — o CHECK atual
`('barcode','ia','ocr','manual')` **não aceita 'off'**; alternativa na decisão 6.3),
`versao=1`, `desativado=0`.

## 4. Lógica do importador (`scripts/importar_openfoodfacts.py`)

### 4.1 Filtros (ordem; cada falha conta numa categoria do relatório)

1. `code` presente e 8–14 dígitos → senão `codigo_invalido`
2. `countries_tags`/`countries_en`/`countries` contém "brazil" → senão `pais`
3. `no_nutrition_data` ≠ `1` → senão `sem_nutri`
4. `energy-kcal_100g` presente e > 0 → senão `sem_energia`
5. `serving_quantity` presente e > 0 → senão `sem_porcao`
6. `product_name` (ou fallbacks) presente → senão `sem_nome`
7. `codigo_barras` já existe na tabela → `ja_existente` (idempotência)

### 4.2 Validação de sanidade (não bloqueia; conta e lista exemplos)

Atwater em base 100g quando carb/prot/fat presentes:
`kcal_esperada = 4×carb + 4×prot + 9×fat`; divergência > 25% vs
`energy-kcal_100g` → alerta (produtos OFF com erro de edição conhecido).

### 4.3 Idempotência e segurança

- **Nunca faz UPDATE/DELETE/ALTER** — só INSERT; re-executar não duplica
  (skip por `codigo_barras`).
- `--seco` (dry-run): nenhum INSERT executado; relatório + primeiras linhas
  para conferência na mão.
- Tolerância a linhas inválidas do CSV (quotes quebradas no dump OFF):
  linha é descartada individualmente, contada como `linha_invalida`, a leitura continua.
- Colunas do motor (`porcao_padrao_g`, `tipo_prato_id`, sensoriais) são preenchidas
  **só se existirem na tabela** (PRAGMA dinâmico) — o script roda mesmo antes do
  DDL do motor.

### 4.4 Uso

```bash
cd /home/plena/novo_cardapio
~/.venv/bin/python scripts/importar_openfoodfacts.py --csv <dump.csv> --seco --limite 500
~/.venv/bin/python scripts/importar_openfoodfacts.py --csv <dump.csv> --sugerir-tipos
```

- `--csv` (obrigatório), `--db` (default `cardapio_hospitalar.db`), `--limite N`
  (teste), `--seco` (dry-run), `--sugerir-tipos` (aplica sugestões de `tipo_prato_id`,
  seção 5; sem a flag as sugestões só aparecem no relatório).

## 5. Classificação `tipo_prato_id` (sugestão automática)

O plano do motor define classificação **manual** nos tipos existentes
(`docs/industrializados_no_motor.md` §3.1). O script **sugere** o tipo a partir de
palavras-chave em `categories_en` + `categories_tags` + `pnns_groups_1` +
`product_name` (minúsculas), mas **só grava com `--sugerir-tipos`** (idempotente:
nunca sobrescreve tipo já preenchido). Mapa (editável no topo do script):

| Palavras-chave | Tipo (`tipos_preparacoes`) |
|---|---|
| biscoito, bolacha, cookie, biscuit, cracker, wafer, waffer | SD - Guarnição |
| iogurte, yogurt, queijo, cheese, requeijão, manteiga, cream cheese, petit suisse | DP - Laticínios |
| suco, juice, néctar, nectar, refresco | JC - Suco |
| fruta(s), fruit, banana, maçã, laranja, uva, apple, orange, grape | FT - Fruta |
| arroz, rice | RC - Arroz |
| feijão, feijao, bean, lentilha, grão de bico, chickpea | BE - Feijão |
| chocolate, pudim, gelatina, sorvete, doce, bolo, cake, sobremesa, dessert | DS - Sobremesa |
| cereal, granola, aveia, oat, muesli, corn flakes | BC1 - Cereal (Café) |

> Correção de nomenclatura: o plano do motor citava "suco→BE" — **BE é Feijão**;
> suco é **JC** (`SELECT` nos tipos em 18/08/2026). O mapa acima já usa o correto.

Casos fora do mapa ficam com `tipo_prato_id` NULL (não entram no motor até
classificação manual — filtro de entrada do motor exige o tipo preenchido).

## 6. Decisões do Bruno (confirmar)

1. **Potássio:** o plano define `potassio_mg` sempre NULL ("rótulo BR não traz").
   O OFF tem `potassium_100g` — se importarmos, o dado passa a existir e dietas
   renais passariam a considerar industrializados (política NULL deixa de excluir
   todos). **Recomendação: manter NULL nesta fase** (cobertura/confiabilidade OFF
   irregular) — decisão sua.
2. **Alérgenos/traços:** default implementado = `alergenos` JSON com apenas os
   alérgenos declarados ("contém"), traduzidos para PT; `traces_en` ("pode conter")
   **fora** na fase 1 (schema sem campo próprio). Se quiser traços, é coluna nova
   (`pode_conter TEXT`) — DDL de fase 2.
3. **Procedência (`fonte`):** o CHECK da tabela não aceita `'off'`; o importador
   grava `'barcode'`. Alternativa (se quiser rastreabilidade): estender o CHECK
   incluindo `'off'` — exige recriar a tabela no SQLite (risco; só se valer a pena).
4. **Atualização de produtos já importados:** fora desta fase — re-importar não
   sobrescreve; mudança de composição é fluxo manual de versões (`alimento_versoes`).
5. **`nova_group`/`nutriscore_grade`/imagens:** não entram no schema; `nova_group`
   (ultraprocessado) pode ser útil clinicamente — coluna nova se quiser (fase 2).

## 7. Plano de validação (valores conferíveis na mão)

1. **Sanidade da conversão** (exemplo hipotético): produto com 500 kcal, 60 g carb,
   8 g prot, 25 g fat por 100 g e porção 30 g → porção = 150 kcal, 18 g carb,
   2,4 g prot, 7,5 g fat. Atwater: 4×60 + 4×8 + 9×25 = 497 kcal ≈ 500 (0,6%) — passa.
2. **Dry-run:** `--seco --limite 500` — conferir relatório (filtros, sugestões) e as
   primeiras linhas; nenhum INSERT.
3. **Importação real em cópia:** rodar contra uma cópia do banco e conferir com
   `SELECT` o produto do passo 1 e a view `vw_alimentos_industrializados_100g`
   (roundtrip porção→100g deve devolver ~os valores de origem).
4. **Idempotência:** rodar 2× → segunda execução reporta tudo `ja_existente`, 0 inserts.
5. **E2E do Bruno:** importar no banco real, conferir cadastro na tela do módulo de
   rótulo, classificar tipos manualmente nos produtos sem sugestão e testar
   `/otimizacao` com `incluir_industrializados`.

## 8. Fora de escopo (fase 2, se desejado)

- Atualização automática de composição (versões via `alimento_versoes`).
- Colunas novas: `nova_group`, `pode_conter`, `imagem_url`, `nutriscore_grade`.
- Filtro por categoria/recorte manual mais fino; importação por API (paginação) em
  vez do dump.
