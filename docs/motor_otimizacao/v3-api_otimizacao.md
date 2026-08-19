# Motor de Otimização — v3 (`api/otimizacao.py`) — ATUAL

**Status:** versão viva (única em uso)
**Arquivo:** `api/otimizacao.py` (611 linhas) — blueprint `otimizacao_bp`
**Histórico git:** `e04a3cd` (03/08) → `de611ad` (04/08) → `27eac77` (08/08) →
`1b42a2d` (09/08) → `e1e861e` (12/08) → `71bdf90` (17/08, personalização) →
`1567420` (18/08, fix objetivo + motor_log + docs)
**Versões anteriores:** [v1](v1-motor_otimizacao.md) e
[v2](v2-motor_otimizacao2.md) em `legado/`

## Papel

Gera cardápios otimizados por **programação linear inteira (PuLP/CBC)** via
`POST /api/otimizacao/executar` e alimenta o fluxo de **planos por paciente**
(`api/plano.py` chama o mesmo `criar_modelo_otimizacao` com `objetivo='target'`
e overrides do plano). Migrou do `sqlite3` direto para **SQLAlchemy** dentro do
app Flask.

## Modelo matemático

- **Variáveis:** `X[p, r, d]` binária — prato `p` na **refeição** `r` no dia
  `d` (a dimensão refeição é a grande mudança vs. v1/v2)
- **Objetivo** (`criar_modelo_otimizacao(dados, dias, overrides, objetivo)`):
  - `max_energia` (default) — `LpMaximize` de Σ kcal
  - `target` — `LpMinimize` do desvio absoluto diário |energia_dia − meta_kcal|,
    via variáveis auxiliares `DesvPos[d]`/`DesvNeg[d]`; só ativo quando
    `overrides['meta_kcal']` existe (fluxo do plano — perda de peso)
  - Qualquer outro valor cai no default (objetivo genérico: proposta em
    `docs/objetivo_generico.md`)
- **Timeout do solver:** `PULP_CBC_CMD(timeLimit=180, gapRel=0.1)` — no limite
  com incumbente viável o CBC retorna Optimal; sem solução → `Not Solved`

## Dados (`carregar_dados_otimizacao`)

- **Pratos:** `pratos` JOIN `vw_pratos_nutricional`, `COALESCE(..., 0)`,
  filtros `desativado=0` + `qtd_ingredientes > 0` + `energia_kcal IS NOT NULL`
- **Nutrientes** (`COLUNAS_NUTRIENTES`, nome curto ↔ coluna): `energia`,
  `proteina`, `lipidios`, `carboidrato`, `fibra`, `sodio`, `potassio`,
  `fosforo`, `calcio`, `ferro`, `gordura_saturada` — entrada tolera nome de
  coluna legado (`sodio_mg`) e normaliza
- **Refeições da dieta:** `tipos_refeicao` JOIN `dieta_refeicoes` (a dieta
  define quais refeições entram — `refeicoes_ordenadas`)
- **Regras:** composição (`regras_por_refeicao`), restrições nutricionais da
  dieta, variedade (`regras_variedade` — carregada, **não aplicada**),
  elegibilidade (`regras_elegibilidade_dieta` + `MAP_ATRIBUTOS`),
  sensoriais (`regras_sensoriais_gerais`)
- **Personalização (Fase 1):** `paciente_id` opcional aplica `carregar_pratos_excluidos`
  (exclusão direta ou via ingrediente em `prato_composicao`) filtrando o
  conjunto candidato
- **Industrializados:** `carregar_alimentos_industrializados()` lê a view
  `vw_alimentos_industrializados_100g` quando `incluir_industrializados=True` —
  mas o modelo **ainda não os usa** (ver Pendências)

## Restrições do modelo (ordem no código)

1. **Um prato ≤ 1 refeição/dia** (`Unico_Dia`)
2. **Máximo de pratos/dia** — ≤ 18
3. **Composição por refeição** — min/max por `(refeição, tipo)`; tipos sem
   pratos disponíveis são pulados
4. **Bloqueio de tipos não autorizados** por refeição (pares fora de
   `regras_composicao` → soma == 0)
5. **Nutricionais da dieta** — nutrientes cobertos por override do plano são
   **substituídos** (o override prevalece; interseção incorreta → Infeasible —
   pitfall já corrigido)
6. **Overrides do plano** — faixas `{nutriente: (min, max)}` (meta ±10%,
   macros ±15%); `meta_kcal` não vira restrição (dirige o `target`)
7. **Elegibilidade** — `IN`/`NOT IN` sobre atributos sensoriais → `X == 0`
   por (prato, refeição, dia)
8. **Sensoriais** — `sem_quentes` implementada (11/08): bloqueia pratos com
   `temperatura_servimento='quente'` dos grupos afetados na refeição; abreviatura
   do tipo = `nome.split(' - ')[0]` (ex.: 'MD - Principal (Carne)' → 'MD');
   bebidas = grupos fora de `grupos_afetados` continuam permitidas.
   `max_cores_iguais` e `consistencia_unica` **inertes** (carregadas, ignoradas)

## Rotas

- `GET /otimizacao` → `otimizacao_form.html` (formulário: dieta, dias,
  objetivo, formato)
- `POST /api/otimizacao/executar` — body `{dieta, dias (1–30), objetivo,
  formato}` → valida dieta (404), monta modelo, resolve, **registra no log do
  motor** e devolve:
  - `formato=json` → `{dieta, dias, objetivo, resultado}` onde
    `resultado = {status, cardapio: [{dia, refeicoes: [{refeicao_id, nome,
    horario, tipos: [{tipo, pratos: [...]}]}]}], metricas: {...}}`
  - `formato=html` → `otimizacao_retrato.html`; `html_paisagem` →
    `otimizacao_paisagem.html`

## Log do motor (`motor_log.py`)

- **JSONL** em `logs/motor_otimizacao.log` (ou `MOTOR_LOG_PATH`), **uma linha
  por execução**: fluxo (`otimizacao|plano`), dieta, dias, objetivo, status,
  tempo_s, overrides, pratos_considerados, métricas, cardápio resumido
- **`MOTOR_DEBUG=1`** (`.env`) adiciona por execução: dump do modelo
  (`motor_lp_<ts>.lp`), log do CBC (`motor_solver_<ts>.log` via `logPath` do
  `PULP_CBC_CMD` — `redirect_stdout` NÃO captura CBC no PuLP 3.x), nº de
  variáveis/restrições e `totais_por_dia`
- ⚠️ O log foi o que pegou o bug do **objetivo descartado** (endpoint lia e não
  repassava — corrigido 17/08/2026) e o bug dos **overrides com nome de coluna**
  (`sodio_mg` vs `sodio` — corrigido 17/08)

## Pendências (ver `docs/motor_otimizacao/README.md`)

- Industrializados no motor (DDL pronto; código pendente — `docs/industrializados_no_motor.md`)
- Objetivo genérico max/min (proposta — `docs/objetivo_generico.md`)
- Regras de variedade carregadas mas não aplicadas
- Sensoriais `max_cores_iguais` / `consistencia_unica` inertes
