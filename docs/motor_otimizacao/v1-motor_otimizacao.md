# Motor de Otimização — v1 (`motor_otimizacao.py`)

**Status:** aposentado (substituído pela [v2](v2-motor_otimizacao2.md))
**Arquivo:** `legado/motor_otimizacao.py` (241 linhas)
**Commit:** `e04a3cd` "novo commit" (03/08/2026)
**Papel:** primeira implementação do motor ("Épico 3 - Opção 1: Motor de
Otimização (Core)") — script de console, sem Flask.

## Modelo matemático

- **Problema:** `Cardapio_Hospitalar_Minimizar_Gordura` (`LpMinimize`)
- **Objetivo:** minimizar lipídios totais do período
- **Variáveis:** `X[p, t, d]` binária — prato `p` escolhido para o **tipo de
  prato** `t` no dia `d` (sem dimensão de refeição)
- **Dias:** configurável via main (`dias=2` no teste)

## Fonte de dados

- `sqlite3` direto, **colunas nutricionais da tabela `pratos`**
  (`lipidios_g`, `energia_kcal`, ...) — schema anterior à composição
- Tabelas: `dietas`, `pratos`, `tipos_prato`, `tipos_refeicao`,
  `regras_composicao`, `restricoes_nutricionais_dieta`, `regras_sensoriais_gerais`

## Restrições

1. **Composição** — soma dos pratos de cada `tipo_prato` no dia (min/max por
   regra) — **sem vínculo com a refeição**
2. **Nutricionais** — mapa de 6 nutrientes (`energia`, `proteina`, `lipidios`,
   `carboidrato`, `fibra`, `sodio`) com min/max por dia; nutriente desconhecido
   é silenciosamente ignorado (`continue`)
3. **Sensoriais** — **stub** (`pass`): regras carregadas mas nada é modelado
4. **Variedade** — no máximo 1 sobremesa na semana (busca o tipo contendo
   "Sobremesa")

## Solver e saída

- `PULP_CBC_CMD(msg=0)` — sem timeout, sem gap
- Console-only (`[1/6]` a `[6/6]`): imprime o cardápio por dia (chave = nome do
  tipo — duplicatas se sobrescrevem) e médias de lipídios

## Limitações / bugs conhecidos

- **Sem refeição no modelo**: `X[p, t, d]` amarra prato→tipo, mas a composição
  soma por tipo no dia inteiro — não monta almoço/jantar como unidades
- Objetivo com `for p_idx, p_real` redundante (lookup O(n²) sobre `pratos`)
- Sensoriais não implementadas; nutrientes fora do mapa ignorados sem aviso
- Duplicatas de tipo no mesmo dia se sobrescrevem na saída
- Não valida inviabilidade com diagnóstico (só imprime "modelo é INVIÁVEL")

## Substituição

A v2 resolveu o problema de dados (nutrientes via `vw_pratos_nutricional`),
trocou o objetivo para maximizar energia e implementou elegibilidade — mas
continuou sem refeições (só a v3 introduziu `X[p, r, d]`).
