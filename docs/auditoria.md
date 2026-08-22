# Auditoria de resultados — rastreando plano → cardápio

Status: EM USO (22/08/2026)
Escopo: como auditar um plano/cardápio a partir dos registros atuais (tabela `wolfram_consultas` + `logs/motor_otimizacao.log` + tabelas de plano/cardápio)
Decisão registrada: NÃO implementar snapshot de entrada nem versão de fórmulas por ora (decisão do Bruno 22/08/2026) — a cadeia atual já cobre o que se pretende rastrear.

## O que existe (fontes da auditoria)

| Fonte | Onde | Pergunta que responde |
|---|---|---|
| `wolfram_consultas` | tabela SQLite | **Por que a meta é X?** — entrada (query), fonte (`local`/`short_answers`/`full_results`), resposta bruta, ok, data |
| `planos_nutricionais` | tabela SQLite | Resultado consolidado do cálculo: get/meta/macros/pcts, fonte, alertas |
| `motor_otimizacao.log` | JSONL (`logs/`, via `motor_log.py`) | **Como o cardápio saiu assim?** — dieta, dias, objetivo, status, tempo_s, overrides efetivos, pratos_considerados, métricas, cardápio resumido, `usuario`, `ts` |
| `cardapios_salvos` → `cardapio_dias` → `cardapio_refeicoes` | tabelas SQLite | O que foi servido de fato (versão, datas, pratos + porção) |

**Chave de ligação:** `plano_id` — presente na tabela de auditoria (FK), no plano e na linha do log do motor (fluxo `plano`).

```
wolfram_consultas ──plano_id──> planos_nutricionais ──plano_id──> cardapios_salvos (versão)
                                        ▲
                    motor_otimizacao.log (plano_id, paciente_id, ts, usuario)
```

## Exemplo hipotético

**Plano #14 do paciente João (id 7), calculado em 12/08/2026 pela nutricionista Leticia (usuária do sistema), com cardápio gerado em seguida. Duas semanas depois, uma nutricionista questiona: "por que a meta é 2300 kcal e o cardápio saiu com média 2305?"**

### Passo 1 — localizar o plano

```sql
SELECT id, paciente_id, get_kcal, meta_kcal, proteinas_g, fonte, criado_em
FROM planos_nutricionais WHERE id = 14;
```

```
id | paciente_id | get_kcal | meta_kcal | proteinas_g | fonte | criado_em
14 |           7 |  2788.10 |   2300.00 |       115.0 | local | 2026-08-12 14:03:28
```

### Passo 2 — a origem da meta (tabela de auditoria)

```sql
SELECT id, plano_id, api, query, ok, criado_em
FROM wolfram_consultas WHERE plano_id = 14;
```

```
id | plano_id | api   | query                                     | ok | criado_em
52 |       14 | local | TMB Mifflin-St Jeor: M 30a 175cm 85kg    | 1  | 2026-08-12 14:03:28
53 |       14 | local | GET x1.55 + déficit 488 → meta 2300 kcal  | 1  | 2026-08-12 14:03:28
```

A meta 2300 = TMB 1798,75 (Mifflin-St Jeor, conferível na mão) × 1,55 − 488 de déficit, calculado localmente. Explica o número e a fonte.

### Passo 3 — a otimização (log do motor)

```bash
jq 'select(.plano_id == 14)' logs/motor_otimizacao.log
```

```json
{"ts":"2026-08-12T14:05:11","usuario":"leticia.karina","fluxo":"plano","paciente_id":7,"plano_id":14,
 "dieta":"LIVRE","dias":7,"objetivo":"target","status":"Optimal","tempo_s":0.84,
 "overrides":{"energia":[2200,2400],"proteinas":[100,130]},
 "pratos_considerados":352,
 "metricas":{"energia_media_dia":2305},
 "cardapio":[{"dia":1,"refeicoes":[{"refeicao":"Café da manhã","pratos":["Pão francês","Café puro com açúcar"]},{"refeicao":"Almoço","pratos":["Arroz branco","Feijão carioca","Isca de frango grelhada","Salada de alface e tomate"]}]}]}
```

Cardápio saiu **Optimal em 0,84s**, com os overrides do plano (energia 2200–2400), considerando 352 pratos; média de energia 2305 — **dentro da faixa**. Aderência confirmada sem abrir o cardápio.

### Passo 4 — o que foi servido de fato

```sql
SELECT id, versao, criado_em FROM cardapios_salvos WHERE plano_id = 14;
```

```
id | versao | criado_em
 9 |      3 | 2026-08-12 14:05:12
```

## Passo a passo (procedimento de auditoria)

1. **Achar o plano:** `SELECT * FROM planos_nutricionais WHERE id = <plano_id>;` (ou por paciente: `WHERE paciente_id = <id> ORDER BY criado_em DESC`).
2. **Entender a meta:** `SELECT * FROM wolfram_consultas WHERE plano_id = <plano_id>;` — confere a entrada, a fonte e o `ok`.
3. **Ver a otimização:** `jq 'select(.plano_id == <plano_id>)' logs/motor_otimizacao.log` — status, tempo, overrides efetivos, pratos considerados, cardápio gerado.
4. **Ver o servido:** `SELECT * FROM cardapios_salvos WHERE plano_id = <plano_id>;` e detalhar dias/refeições.
5. **Checar aderência:** comparar `planos_nutricionais.meta_kcal` com a métrica de energia do log (`metricas.energia_media_dia` ou, com `MOTOR_DEBUG=1`, `debug.totais_por_dia`).

Para auditar um **paciente inteiro** (todas as execuções):

```bash
jq 'select(.paciente_id == 7)' logs/motor_otimizacao.log
```

Para ver **falhas** (Infeasible/erro):

```bash
jq 'select(.status != "Optimal")' logs/motor_otimizacao.log
```

## O que a cadeia prova / não prova

**Prova:**
- Rastreabilidade completa: entrada → meta → otimização → cardápio salvo, com timestamp, usuário e fonte.
- Aderência cardápio ↔ plano (meta vs energia gerada, faixas de overrides).
- Diagnóstico de falha (Infeasible/erro) com os overrides que inviabilizaram.

**NÃO prova (limites assumidos, sem snapshot/versão):**
- **Replicar o cálculo exato** — se o peso do paciente mudou, recalcular hoje dá resultado diferente; a `query` guardada é descritiva, não um payload de entrada congelado.
- **Se as fórmulas mudarem** — não há versão do cálculo registrada; replay com a mesma entrada poderia divergir.
- **Vínculo exato log ↔ versão salva** — sem `cardapio_id` no log, o link com a versão é por proximidade de timestamp, não por FK.

## Decisões

- **D1 — Manter `wolfram_consultas` como está** (log de eventos): não renomear, não adicionar colunas por ora. Custo zero, histórico preservado.
- **D2 — Sem snapshot de entrada nem versão de fórmulas** (decisão Bruno 22/08/2026): a cadeia atual já cobre o rastreio pretendido; replicação exata fica como melhoria futura se surgir necessidade real.
- **D3 — Melhoria futura opcional (não implementada):** adicionar `cardapio_id` e `versao_motor` (e a meta-alvo) na linha do log do motor — fecha a cadeia com FK e permite replay da otimização. Mudança de 2 linhas em `api/plano.py`, sem DDL.

## Relacionados

- `motor_log.py` — estrutura do JSONL (campos, debug via `MOTOR_DEBUG=1`)
- `docs/motor_otimizacao/` — versionamento do motor (v1/v2/v3)
- `docs/personalizacao_por_paciente.md` — overrides por paciente (entram no log como `overrides`)
