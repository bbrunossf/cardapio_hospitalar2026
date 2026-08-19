# Motor de Otimização — v2 (`motor_otimizacao2.py`)

**Status:** aposentado (substituído pela [v3](v3-api_otimizacao.md))
**Arquivo:** `legado/motor_otimizacao2.py` (298 linhas)
**Commits:** `e04a3cd` (03/08) + `27eac77` "fix adicionado regras_elegibilidade
no motor" (08/08/2026)
**Papel:** segunda implementação — adaptada ao **schema v5**
(`prato_composicao` + `vw_pratos_nutricional`); ainda script de console.

## Modelo matemático

- **Problema:** `Cardapio_Hospitalar_Maximizar_Energia` (`LpMaximize`)
- **Objetivo:** maximizar energia (kcal) total do período
- **Variáveis:** `X[p, d]` binária — prato `p` servido no dia `d`
  (**sem tipo e sem refeição** na variável)
- **Dias:** 5 no main

## Fonte de dados

- `sqlite3` direto, nutrientes via **`vw_pratos_nutricional`** (JOIN +
  `COALESCE(..., 0)`), filtro: `desativado = 0`, `qtd_ingredientes > 0`,
  `energia_kcal IS NOT NULL`
- Novas tabelas: `tipos_preparacoes` (renomeação de `tipos_prato`),
  `regras_variedade`, `regras_elegibilidade_dieta`
- `MAP_ATRIBUTOS`: `cor → cor_predominante`, `consistencia`, `textura`,
  `temperatura_servimento`

## Restrições

1. **Limite de pratos/dia** — ≤ 18
2. **Composição por tipo (agregada no dia)** — demanda min = soma dos mínimos
   de todas as refeições; máx = `min + 2` (heurística); pula tipo sem pratos
   disponíveis com aviso
3. **Mínimo de pratos/dia** — `total_min_dia`
4. **Nutricionais** — 7 nutrientes (agora com `potassio`); nutriente
   desconhecido imprime aviso (não mais silencioso)
5. **Elegibilidade** — `IN`/`NOT IN` sobre atributos sensoriais, bloqueando
   pratos (`X == 0`) por dia
6. **Variedade** — carregada mas **desabilitada** (comentada: conflita com a
   composição)

## Solver e saída

- `PULP_CBC_CMD(timeLimit=180, gapRel=0.1, msg=1)` — **timeout e gap
  introduzidos aqui**
- Trata `Optimal` e `Undefined` (0) como aceitáveis; senão diagnostica
  restrições `Comp_Min` violadas (folga < −0.5)
- Saída: cardápio por dia com chaves únicas (`tipo#2` para duplicatas) +
  totais/médias de energia, proteína, lipídios, carboidrato, sódio

## Limitações / bugs conhecidos

- **Sem refeição**: `X[p, d]` não distingue almoço de jantar — o cardápio sai
  como lista de pratos por dia, não por refeição
- Composição agregada por tipo no dia (min somado, máx heurístico `min+2`) —
  não respeita as regras por refeição
- Variedade desabilitada; sensoriais (`regras_sensoriais_gerais`) não carregadas
- `msg=1` no solver polui o console em produção

## Substituição

A v3 migrou para um blueprint Flask (SQLAlchemy), introduziu a dimensão
**refeição** (`X[p, r, d]`) com composição por refeição e bloqueio de tipos não
autorizados, e acrescentou overrides do plano, `sem_quentes` e o log do motor.
