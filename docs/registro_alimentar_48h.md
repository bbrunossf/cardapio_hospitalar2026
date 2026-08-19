# Módulo "Registro Alimentar 48h" — plano (19/08/2026)

## Objetivo

Estimar **calorias e nutrientes ingeridos por um paciente** a partir do relato de
alimentação de 48h (registro alimentar), com abordagem **híbrida e auditável**:

- O **LLM apenas estrutura o texto** (relato livre → lista de itens) e **estima
  somente o que não existir no banco** (item marcado como "estimado")
- A **busca de dados nutricionais é forçada no banco de dados**, com precedência
  fixa: **pratos → alimentos industrializados → ingredientes**
- A **agregação é 100% local/determinística** (mesma filosofia do
  `calculo_nutricional`): soma por refeição/dia, mostrando o total consumido —
  insumo para a elaboração do plano/cardápio (o registro é a fotografia do que o
  paciente já ingere)

Cada item da resposta informa a **fonte** do valor (prato/industrializado/
ingrediente/estimado) — auditoria item a item, valores conferíveis na mão.

## Decisões do Bruno (19/08/2026)

- **Objetivo:** calcular o consumo do paciente **antes** da elaboração do
  plano/cardápio — **sem cardápio de referência**; a resposta mostra apenas o
  total consumido (por refeição e por dia)
- **Persistência:** v1 **grava direto** (status `processado`), sem confirmação
  prévia do nutricionista — auditoria + reprocessamento via tabelas novas (DDL
  em `docs/sql/registro_alimentar_48h.sql`)
- **Marcação "ESTIMADO":** item fora do banco → badge visível (mesmo padrão do
  Posso Comer); no banco → valor exato do cadastro
- **LLM:** a API isolada `api_posso_comer` (porta 5010, GPT-4o-mini) ganha um
  endpoint de estruturação; o app principal **continua sem LLM embutido**
- **Micronutrientes:** exibir os mesmos do cardápio (fibra, cálcio, ferro, sódio,
  potássio, fósforo, vit C); quando a fonte não tem o dado (ex.: potássio em
  industrializado, rótulo não traz) → exibir **"não informado"**, **nunca** zero
- **Medidas caseiras:** tabela de conversão local (determinística) + fallback
  LLM/consulta ao nutricionista quando não houver mapeamento

## Fluxo geral

```
entrada: paciente + texto do registro alimentar de 48h (colado pelo nutricionista)
   → 1. ESTRUTURAÇÃO (LLM via API 5010): texto → lista de itens
        {dia: 1|2, refeicao, descricao, quantidade_texto ("2 fatias"),
         valor, unidade}
        (LLM NÃO calcula nutrientes nesta etapa)
   → 2. LOOKUP FORÇADO NO BANCO (determinístico, obrigatório p/ todo item)
        2a. busca por tokens no banco: pratos → industrializados → ingredientes
        2b. fallback fuzzy (difflib)
        2c. fallback semântico (chroma `alimentos_embeddings`)
   → 3. CONVERSÃO de quantidade para gramas
        (medidas_caseiras → porção padrão → consulta nutricionista)
   → 4. CÁLCULO dos nutrientes (local, por fonte — ver §Cálculo)
        item sem match no banco → LLM estima → origem='estimado', badge
   → 5. AGREGAÇÃO: totais consumidos por refeição e por dia → resposta
        final (auditável item a item; insumo p/ o plano/cardápio)
```

## Arquitetura

```
┌───────────────────────────┐   HTTP   ┌──────────────────────────────┐
│ App principal (Flask)     │─────────▶│ API isolada api_posso_comer   │
│ novo_cardapio (porta 5000)│          │ (porta 5010, GPT-4o-mini)     │
│                           │◀─────────│ • POST /estruturar-registro   │
│ • lookup no banco         │   JSON   │   (texto → itens estruturados)│
│ • cálculo determinístico  │          │ • POST /estimar               │
│ • conversão de medidas    │          │   (item sem match → nutrientes│
│ • agregação + comparação  │          │    estimados, marcado)        │
│ • UI tabela/badges        │          └──────────────────────────────┘
└────────────┬──────────────┘
             │ SELECT (read-only)
┌────────────▼──────────────┐
│ cardapio_hospitalar.db     │        ┌──────────────────────────────┐
│ pratos (vw_pratos_nutricional)│      │ chroma_db/                    │
│ alimentos_industrializados │        │ alimentos_embeddings (novo)   │
│ ingredientes               │        │ fonte: prato|industrializado| │
│ medidas_caseiras (nova)    │        │        ingrediente            │
│ registros_alimentares (nova)        └──────────────────────────────┘
└───────────────────────────┘
```

## Pipeline de match (ordem de precedência)

Para **cada item** estruturado, nesta ordem — o primeiro que casar vence:

| # | Estratégia | Alvos (em ordem) | Critério |
|---|---|---|---|
| 1 | Tokens exatos (normalizado: minúsculas, sem acentos, sem plural) | `pratos.nome` → `alimentos_industrializados.(nome+marca)` → `ingredientes.nome` | **todos** os tokens do texto (padrão já usado no Posso Comer) |
| 2 | Fuzzy | idem | `difflib.SequenceMatcher.ratio ≥ 0.82` no nome normalizado |
| 3 | Semântica (chroma) | coleção `alimentos_embeddings` | top-k vizinhos + filtro de categoria (`tipo_prato`/`tipo_alimento`) + menor distância; desempate por kcal da porção mais próxima da faixa informada |

Regras:
- **Precedência de fonte é regra de aplicação, não de busca** — um item "arroz,
  feijão e bife" que casa com prato do hospital **sempre** resolve como prato
  antes de cair para ingrediente avulso
- Match ambíguo (vários candidatos com score próximo) → lista para o
  nutricionista escolher (mesmo padrão da busca do Posso Comer)
- **Estimativa LLM é o último recurso**, nunca concorre com o banco

## Cálculo por origem (determinístico)

| origem | Fórmula | Fonte dos nutrientes |
|---|---|---|
| `prato` | `vw_pratos_nutricional` × `quantidade_g / porcao_padrao_g` | view dinâmica (energia, carbo, prot, lip, fibra, cálcio, ferro, sódio, potássio, fósforo, vit C, gordura sat., colesterol) |
| `industrializado` | campos da porção × `quantidade_g / porcao_padrao_g` | **tabela base** (energia_kcal, carboidratos_g, proteinas_g, gorduras_totais_g, fibras_g, sodio_mg) — rótulo da porção, **não** a view 100g |
| `ingrediente` | base 100g × `quantidade_g / 100` | `ingredientes` (energia_kcal, carboidrato_g, proteina_g, lipidios_g, fibra_alimentar_g, calcio_mg, ferro_mg, sodio_mg, potassio_mg, fosforo_mg, vit_c_mg) |
| `estimado` | valores LLM por 100g × `quantidade_g / 100` | resposta da API `/estimar`, com `estimado=true` e nota na UI |

Atenção: `alimentos_industrializados.porcao_padrao_g` = gramas da porção do
rótulo (ex.: 30 g de biscoito) — o fator é `quantidade_g / porcao_padrao_g`,
**não** `/100`.

## Conversão de medidas caseiras

- O LLM entrega `{valor, unidade}` para cada item ("2 fatias", "1 copo", "200 g")
- Unidade em gramas → direto
- Unidade caseira → tabela `medidas_caseiras` (nova): match **alimento específico
  primeiro** (`alimento_padrao` preenchida, ex.: "fatia" de "pão de forma" = 25 g),
  senão genérico (ex.: "fatia" = 20 g); fonte da conversão registrada na tabela
- Sem mapeamento → `quantidade_g = NULL` + item marcado "revisar" na UI (o
  nutricionista informa a porção) — **nunca** inventar conversão silenciosa
- Conversões iniciais da tabela: valores TACO/rotulagem (fatia de pão de forma,
  copo americano 200 ml, xícara 240 ml, colher de sopa 15 ml, concha 100 ml,
  unidade média de frutas...), preenchidas pelo Bruno na revisão

## Coleção vetorial `alimentos_embeddings` (nova)

Unifica as 3 fontes numa única coleção para o registro de 48h (e módulos futuros).
A coleção `ingredientes_embeddings` existente **permanece intacta** (Posso Comer e
Alimentos Semelhantes continuam usando-a — não quebrar o que funciona).

| Campo | Valor |
|---|---|
| ids (strings) | `prato_<id>`, `ind_<id>`, `ing_<id>` (prefixo evita colisão entre fontes) |
| metadados | `fonte` (`prato`\|`industrializado`\|`ingrediente`), `nome`, `tipo` (`tipo_prato` ou `tipo_alimento`), `texto_original` (descrição), `kcal_porcao` (desempate) |
| espaço | `hnsw:space = cosine` (padrão atual) |
| modelo | `text-embedding-3-small` (1536 dims) — mesmo do índice atual |

**Textos de embedding:**
- **Ingredientes:** descrição já existente (reaproveitar cache/`texto_semantico`)
- **Pratos:** descrição **derivada da composição** — nome + tipo +
  consistência/textura + `GROUP_CONCAT` dos ingredientes da ficha técnica
  (`prato_composicao` → `ingredientes.nome`) — "bife acebolado, arroz branco,
  feijão" casa muito melhor com o relato do paciente do que "MD - Principal
  (Carne)"
- **Industrializados:** `nome (marca)` + porção + kcal da porção

**Script:** estender `scripts/gerar_embeddings_alimentos.py` (versionado) com:
- `--fontes ingredientes,pratos,industrializados` (default: todas) e `--recriar`
- Modos `template`/`llm`/`auto` já existentes — template determinístico para
  pratos/industrializados (composição vem do banco), `auto` para descrições
  ricas com cache (prompt existente já proíbe inventar dados fora dos fornecidos)
- Requer `OPENAI_API_KEY` no `.env` apenas para embeddings/LLM; `template`
  roda offline (zero custo)
- Regenerar pontualmente após mudanças relevantes de composição (embeddings são
  só recuperação, nunca cálculo)

## Endpoints (app principal)

- `GET /registro-alimentar` — página (regra UX: **sempre por paciente**,
  seleção primeiro; nunca lista geral)
- `POST /api/registro-alimentar/processar` — body `{paciente_id, texto}` →
  estrutura (API 5010) → lookup → conversão → cálculo → resposta:
  - `{registro_id, itens: [{dia, refeicao, descricao, quantidade_texto,
    quantidade_g, origem, estimado, nome_encontrado?, nutrientes: {...},
    fonte_dados?}], totais_por_dia: [{dia, kcal, macros...,
    micronutrientes...}], alertas: [...]}`
- `GET /api/registro-alimentar/<registro_id>` — detalhe persistido (auditoria)
- `PATCH /api/registro-alimentar/itens/<item_id>` — correção manual do
  nutricionista (origem/quantidade_g/nutrientes) — fase 2
- Fluxo em 2 passos na página (padrão Posso Comer): processar → itens com
  match ambíguo ou `quantidade_g NULL` aparecem para confirmação → 2ª chamada
  resolve; o registro só é gravado com os itens resolvidos

**API isolada (5010):** novo endpoint `POST /estruturar-registro` — texto →
`{itens: [{dia, refeicao, descricao, valor, unidade}]}`. Sem nutrientes; o
`/estimar` existente cobre o fallback. ⚠️ Avisar o Bruno para sincronizar o
repo local da api_posso_comer quando o endpoint for adicionado no servidor.

## DDL

`docs/sql/registro_alimentar_48h.sql` — 3 tabelas novas:

1. **`registros_alimentares`** — cabeçalho do registro: paciente_id (FK),
   período (data_inicio/data_fim), `texto_original` (relato cru), status,
   criado_por (escopo por dono herdado pela âncora `pacientes.criado_por`)
2. **`registro_alimentar_itens`** — item estruturado: dia (1|2), refeição,
   descrição, quantidade (texto + g), **origem** com CHECK
   (`prato|industrializado|ingrediente|estimado`), FKs nullable exclusivas
   (exatamente uma preenchida conforme a origem — CHECK garante), flag
   `estimado`, nutrientes calculados, `observacao` (ex.: "porção assumida")
3. **`medidas_caseiras`** — unidade + alimento_padrão (opcional) + gramas +
   fonte (TACO/rotulagem/estimativa)

Convenções do banco: `id INTEGER PRIMARY KEY AUTOINCREMENT`, `criado_em/
editado_em DATETIME DEFAULT CURRENT_TIMESTAMP`, `desativado BOOLEAN DEFAULT 0`,
`DECIMAL(8,2)` p/ quantidades, FKs com `ON DELETE CASCADE` onde faz sentido.

## Testes / validação

1. **Valores conferíveis na mão:** ex. item "arroz branco, 1 concha (100 g)" →
   ingrediente arroz 130 kcal/100g → 130 kcal; "bife, 150 g" → prato via view
   (energia_calculada × 150/porcao_padrao_g); conferir a soma do dia item a
   item numa planilha (sem cardápio de referência — registro é pré-plano)
2. **Fator industrializado:** biscoito porção 30 g = 140 kcal → 60 g consumidos =
   280 kcal (validar que o fator é `/porcao_padrao_g`, não `/100`)
3. **Casos de match:** item que casa com prato vs. ingrediente (precedência),
   industrializado por nome+marca, item fora do banco (estimado + badge),
   match ambíguo (lista), medida caseira sem conversão (revisar)
4. **Contrato do endpoint de estruturação** testado isoladamente na 5010
5. E2E do Bruno no navegador (regra 1) — gravação no banco fica com ele

## Decisões em aberto

- **Registro em lote vs. item a item:** nutricionista edita antes de gravar
  (fase 2: PATCH por item)
- **Uso futuro:** totais do registro (kcal/macros médios dos 2 dias) como
  insumo automático do plano (ex.: comparar consumo atual × meta calculada) —
  fora do escopo da v1

## Estado da implementação

Nada implementado — este é o doc de planejamento (fase doc primeiro, regra 2).
Próximos passos após aprovação do Bruno: (1) executar DDL; (2) endpoint
`/estruturar-registro` na api_posso_comer (5010); (3) extensão do script de
embeddings + gerar `alimentos_embeddings`; (4) blueprint no app.
