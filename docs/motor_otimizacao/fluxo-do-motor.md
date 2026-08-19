# Motor de Otimização — fluxo do código (passo a passo)

**Arquivo:** `api/otimizacao.py` (v3 — versão viva; arquitetura/pendências em
[v3-api_otimizacao.md](v3-api_otimizacao.md))
**Objetivo deste doc:** descrever **como o motor funciona de ponta a ponta** —
como recebe os dados, quais variáveis cria e quais regras aplica — sem entrar
nos detalhes do algoritmo do PuLP/CBC. É o fluxo do código, função por função.

## Visão geral — dois caminhos de entrada

O mesmo núcleo (`carregar_dados_otimizacao` → `criar_modelo_otimizacao` →
`resolver_e_extrair`) é usado por dois fluxos:

```
┌─ CAMINHO 1: Otimização livre ─────────────────────────────────────┐
│ POST /api/otimizacao/executar (formulário /otimizacao)            │
│   dieta + dias + objetivo(max_energia) + formato                  │
└──────────────┬────────────────────────────────────────────────────┘
               ▼
┌─ CAMINHO 2: Cardápio do plano ────────────────────────────────────┐
│ POST /api/planos/<id>/cardapio (api/plano.py)                     │
│   dieta do paciente + overrides do plano + objetivo='target'      │
└──────────────┬────────────────────────────────────────────────────┘
               ▼
   carregar_dados_otimizacao(dieta[, paciente_id, incluir_industrializados])
               ▼
   criar_modelo_otimizacao(dados, dias, overrides, objetivo)
               ▼
   resolver_e_extrair(problema, X, dados, dias)   →  motor_log.registrar()
               ▼
   resposta (JSON | HTML)  /  salva cardápio versionado (só plano)
```

---

## 1. Entrada — como o motor recebe os dados

### Caminho 1 — endpoint livre (`executar_otimizacao`, linha 523)

Body JSON do `POST /api/otimizacao/executar`:

| Campo | Tratamento |
|---|---|
| `dieta` | `.strip().upper()` — default `"LIVRE"` |
| `dias` | `int()` — validado `1 ≤ dias ≤ 30` (senão **400**) |
| `objetivo` | `.strip().lower()` — default `"max_energia"` |
| `formato` | `.strip().lower()` — `json` (default), `html`, `html_paisagem` |

Fluxo: parse → valida dias → `carregar_dados_otimizacao(dieta_nome)` (dieta
inexistente → `ValueError` → **404**) → monta modelo → resolve → loga → renderiza.

### Caminho 2 — plano do paciente (`api/plano.py`, linha 438)

`carregar_dados_otimizacao(dieta_nome, paciente_id=plano.paciente_id)` — o
mesmo carregamento, mas **filtrado pelas exclusões do paciente** (ver §2.2).

---

## 2. Carregamento (`carregar_dados_otimizacao`, linha 99)

Executa, nesta ordem, um bloco de consultas SQLAlchemy e monta um dict que é o
**contrato de entrada do modelo**.

### 2.1 Consultas (na ordem do código)

1. **Dieta** — `dietas WHERE nome = :nome` → `dieta_id` (erro se não achar)
2. **Pratos** — `pratos JOIN vw_pratos_nutricional` com `COALESCE(..., 0)` em
   todos os nutrientes; filtros: `desativado = 0`, `qtd_ingredientes > 0`,
   `energia_kcal IS NOT NULL`
3. **Exclusões do paciente** (só com `paciente_id`) —
   `carregar_pratos_excluidos`: `exclusoes_paciente` direta (prato) **UNION**
   via `prato_composicao` (ingrediente banido → pratos que o contêm); remove do
   conjunto candidato
4. **Tipos de prato** — `tipos_preparacoes` → `{id: nome}`
5. **Refeições da dieta** — `tipos_refeicao JOIN dieta_refeicao` (a **dieta
   define quais refeições existem**) → `tipos_refeicao` (id → {id, nome,
   horario_padrao}) + `refeicoes_ordenadas` (lista de ids, ordem do banco)
6. **Regras de composição** — `regras_composicao` (todas as dietas) e depois
   agrupadas por refeição → `regras_por_refeicao` (defaultdict)
7. **Restrições nutricionais da dieta** — `restricoes_nutricionais_dieta`
   `WHERE dieta_id`
8. **Variedade** — `regras_variedade` (carregada, **não usada no modelo**)
9. **Elegibilidade** — `regras_elegibilidade_dieta` `WHERE dieta_id`
10. **Sensoriais** — `regras_sensoriais_gerais` (todas)
11. **Industrializados** (só com `incluir_industrializados=True`) —
    `carregar_alimentos_industrializados` lê `vw_alimentos_industrializados_100g`
    (hoje o modelo **não os consome** — pendência)

### 2.2 Estrutura de dados retornada (contrato do modelo)

```python
{
  'dieta_id': int,
  'dieta_nome': str,
  'pratos': [ {id, nome, tipo_prato_id, cor_predominante, consistencia, textura,
               temperatura_servimento, porcao_padrao_g, energia_kcal,
               carboidrato_g, proteina_g, lipidios_g, fibra_alimentar_g,
               sodio_mg, potassio_mg, fosforo_mg, calcio_mg, ferro_mg,
               gordura_saturada_g, massa_total_calculada, qtd_ingredientes}, ...],
  'mapa_pratos': {id: prato},
  'tipos_prato': {id: nome},
  'tipos_refeicao': {id: {id, nome, horario_padrao}},
  'refeicoes_ordenadas': [id_refeicao, ...],
  'regras_composicao': [ {tipo_refeicao_id, tipo_prato_id, qtd_minima, qtd_maxima}, ...],
  'regras_por_refeicao': {id_refeicao: [regras...]},
  'restricoes_nutricionais': [ {nutriente, valor_minimo, valor_maximo}, ...],
  'regras_variedade': [ ... ],
  'regras_elegibilidade': [ {atributo, valores_permitidos, operador}, ...],
  'regras_sensoriais': [ {tipo_refeicao_id, regra, valor_limite, grupos_afetados}, ...],
  'alimentos_industrializados': [ ... ],   # vazio por padrão
}
```

`COLUNAS_NUTRIENTES` (linha 22) mapeia nome curto ↔ coluna e é usado em todo o
modelo: `energia→energia_kcal`, `proteina→proteina_g`, `lipidios→lipidios_g`,
`carboidrato→carboidrato_g`, `fibra→fibra_alimentar_g`, `sodio→sodio_mg`,
`potassio→potassio_mg`, `fosforo→fosforo_mg`, `calcio→calcio_mg`,
`ferro→ferro_mg`, `gordura_saturada→gordura_saturada_g`. Nomes de coluna
legados (`sodio_mg`) são tolerados e normalizados.

---

## 3. Modelagem (`criar_modelo_otimizacao`, linha 222)

Recebe `(dados, dias=5, overrides=None, objetivo='max_energia')`.

### 3.1 Variáveis de decisão

| Variável | Domínio | Papel |
|---|---|---|
| `X[p, r, d]` | binária (0/1) | **1 se o prato `p` é servido na refeição `r` no dia `d`** — a dimensão refeição existe só a partir da v3 |
| `desv_pos[d]`, `desv_neg[d]` | ≥ 0 (contínuas) | só no modo `target`: desvio da energia do dia para cima/para baixo da meta |

### 3.2 Objetivo

- `max_energia` (default): `LpMaximize` de Σ `energia_kcal × X[p,r,d]`
- `target`: `LpMinimize` de Σ (desv_pos + desv_neg), com a restrição
  `energia_dia[d] − desv_pos[d] + desv_neg[d] == meta_kcal` por dia — só ativo
  quando `overrides['meta_kcal']` existe (fluxo do plano)
- Qualquer outro valor cai no default (objetivo genérico é proposta em
  `docs/objetivo_generico.md`)

### 3.3 Regras — na ordem em que entram no modelo

| # | Nome da restrição | O que faz | Observação |
|---|---|---|---|
| 1 | `Unico_Dia` | um prato não pode aparecer em duas refeições no mesmo dia | `Σ_r X[p,r,d] ≤ 1` |
| 2 | `MaxPratos_Dia` | máximo de 18 pratos por dia | `Σ_{p,r} X[p,r,d] ≤ 18` |
| 3 | `Comp_Min/Max_R_T_Dia` | composição por **(refeição, tipo)**: mínimo/máximo de pratos daquele tipo naquela refeição | só com `qtd_min > 0` / `qtd_max < 99`; tipo sem pratos disponíveis é pulado |
| 4 | `Bloq_R_T_Dia` | **bloqueio de tipos não autorizados** na refeição (pares fora de `regras_composicao` → soma == 0) | impede prato "errado" na refeição |
| 5 | `Nut_Min/Max_Dia` | faixas nutricionais **da dieta** | nutrientes com override do plano são **pulados aqui** |
| 6 | `Override_Min/Max_Dia` | faixas **do plano/paciente** (overrides) | **substituem** a faixa da dieta para o mesmo nutriente (intersectar → Infeasible; pitfall já corrigido 17/08) |
| 7 | `Eleg_*_R_P_Dia` | elegibilidade: pratos fora dos `valores_permitidos` (IN/NOT IN sobre cor/consistência/textura/temperatura via `MAP_ATRIBUTOS`) → `X == 0` | por (prato, refeição, dia) |
| 8 | `Sensorial_SemQuentes_R_Dia` | `sem_quentes`: soma de pratos QUENTES dos grupos afetados na refeição ≤ `valor_limite` | abreviatura do tipo = `nome.split(' - ')[0]` (ex. 'MD - Principal (Carne)' → 'MD'); bebidas (grupos fora de `grupos_afetados`) continuam permitidas |

**Não aplicadas (apesar de carregadas):** `regras_variedade` (desde a v2,
comentada por conflito com composição) e as sensoriais `max_cores_iguais` /
`consistencia_unica` (inertes — a regra 8 só trata `sem_quentes`).

---

## 4. Resolução (`resolver_e_extrair`, linha 423)

1. **Solver:** `PULP_CBC_CMD(timeLimit=180, gapRel=0.1)` — 180s + gap 10%.
   Com `log_path` (debug), a saída do CBC vai para o arquivo via `logPath`
   (`redirect_stdout` não captura o CBC no PuLP 3.x)
2. **Status:** `Optimal (1)` ou `Undefined (0)` (incumbente viável no tempo
   limite) são aceitos; qualquer outro → retorna
   `{status, cardapio: [], metricas: {erro: 'Modelo inviável...'}}`
3. **Extração:** percorre `X[p][r][d] == 1` e monta o cardápio estruturado:
   `[{dia, refeicoes: [{refeicao_id, refeicao_nome, horario, tipos:
   [{tipo, pratos: [prato_info]}]}]}]` — cada `prato_info` carrega id, nome,
   porcao_g e **todos os nutrientes** do prato
4. **Métricas:** energia total, médias diárias (energia, proteína, lipídios,
   carboidrato, sódio) e total de pratos selecionados

---

## 5. Log do motor (`motor_log.py`)

Toda execução grava **uma linha JSONL** em `logs/motor_otimizacao.log`
(`MOTOR_LOG_PATH` sobrescreve): `ts`, `usuario`, `fluxo` (`otimizacao`|`plano`),
`dieta`, `dias`, `objetivo`, `status`, `tempo_s`, `pratos_considerados`,
`metricas`, `cardapio` (resumo: nomes por refeição/dia). Falha de escrita é
engolida (o log nunca derruba a requisição).

**`MOTOR_DEBUG=1`** (`.env`) adiciona: dump do modelo (`motor_lp_<ts>.lp` via
`writeLP`), log do solver (`motor_solver_<ts>.log`), nº de variáveis/
restrições e `totais_por_dia` (todos os nutrientes por dia).

Exemplo de consulta:
```bash
jq -r 'select(.status == "Optimal") | .ts, .dieta, .tempo_s' logs/motor_otimizacao.log
```

---

## 6. Resposta

- `formato=json` → `{dieta, dias, objetivo, resultado}` (resultado da §4)
- `formato=html` → `templates/otimizacao_retrato.html`
- `formato=html_paisagem` → `templates/otimizacao_paisagem.html`

No **caminho do plano** (api/plano.py) a resposta não é renderizada: o cardápio
é **salvo versionado** (`cardapios_salvos` → `cardapio_dias` →
`cardapio_refeicoes`) com `fluxo='plano'` no log.

---

## 7. Resumo do caminho do plano (overrides)

`_overrides_do_plano(plano)` (api/plano.py linha 80) monta:
- `meta_kcal` → dirige o modo `target`
- `energia = (meta × 0.90, meta × 1.10)` — meta ±10%
- macros (`proteina`, `carboidrato`, `lipidios`) ±15%
- `overrides.update(carregar_restricoes_paciente(paciente_id))` — faixas
  nutricionais do paciente (personalização Fase 1) têm precedência

Precedência final no modelo: **paciente (Fase 1) > plano > dieta**.
