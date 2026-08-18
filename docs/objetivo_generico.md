# Função objetivo genérica (maximizar/minimizar qualquer nutriente)

**Status:** Proposta — aguardando aprovação do Bruno
**Data:** 18/08/2026
**Escopo:** `api/otimizacao.py`, `templates/otimizacao_form.html`, endpoint `POST /api/otimizacao/executar`
**Schema:** nenhuma mudança (zero DDL)

---

## 1. Contexto / problema atual

A tela `/otimizacao` oferece 3 opções de função objetivo:

- `max_energia` — funciona (default)
- `max_proteina` — **não funciona**: cai no `else` do `criar_modelo_otimizacao` e maximiza energia
- `min_custo` — **não funciona** (idem; e custo não é nem selecionado na query)

O motor (`criar_modelo_otimizacao`, linha 222) só tem 2 modos reais:

| valor | comportamento |
|---|---|
| `max_energia` (default) | maximiza Σ `energia_kcal` × X |
| `target` | minimiza desvio absoluto de `meta_kcal` (só com `meta_kcal` no overrides — fluxo do plano) |

**Motivação (pedido do Bruno, 18/08):** para dieta renal, por exemplo, o nutricionista quer
poder minimizar sódio, potássio ou fósforo — e em geral escolher **qualquer** parâmetro
registrado + a direção (max/min), em vez de opções pré-definidas.

## 2. Dados disponíveis (validado no banco)

O `SELECT` em `carregar_dados_otimizacao` (linha 113) já traz, por prato, via
`vw_pratos_nutricional`:

`energia_kcal`, `carboidrato_g`, `proteina_g`, `lipidios_g`, `fibra_alimentar_g`,
`sodio_mg`, `potassio_mg`, `fosforo_mg`, `calcio_mg`, `ferro_mg`, `gordura_saturada_g`
(+ `massa_total_calculada`, `qtd_ingredientes`)

Cobertura entre os 402 pratos candidatos do motor:

| nutriente | pratos SEM dado (virariam 0 no COALESCE) |
|---|---|
| sódio | 24 |
| fósforo | 11 |
| potássio | 6 |
| custo | **402/402 (zero)** — `custo_por_100g` nunca preenchido |

## 3. Proposta

### 3.1 Formato do objetivo (API)

`objetivo` passa a aceitar:

```
<sentido>_<nutriente>     ex.: min_sodio, max_proteina, min_fosforo, max_energia
```

- `<sentido>` ∈ `max` | `min`
- `<nutriente>` = nome **curto** (mesmo padrão de `restricoes_nutricionais_dieta`):
  `energia`, `proteina`, `carboidrato`, `lipidios`, `fibra`, `sodio`, `potassio`,
  `fosforo`, `calcio`, `ferro`, `gordura_saturada`, `custo`
- `target` continua especial (fluxo do plano, inalterado)
- Retrocompatível: `max_energia` continua sendo o default

### 3.2 Motor (`criar_modelo_otimizacao`)

- Parse: `sentido, nutriente = objetivo.split('_', 1)`; validar contra
  `COLUNAS_NUTRIENTES` (+ `custo` → `custo_total`, adicionar ao SELECT via
  `v.custo_total`).
- Coeficientes: `p[coluna]` — mesma estrutura do bloco atual de energia, só que
  com a coluna do nutriente escolhido.
- `pulp.LpProblem(nome, pulp.LpMaximize | pulp.LpMinimize)` conforme o sentido.
- Nome do problema dinâmico (ex.: `Cardapio_Hospitalar_Minimizar_Sodio`).
- Objetivo desconhecido → `ValueError` com a lista válida (vira 400 no endpoint).
- `target` sem `meta_kcal`: mantém fallback atual para `max_energia`.

### 3.3 Endpoint (`executar_otimizacao`)

- Validar `objetivo` contra o conjunto permitido; inválido → `400` com a lista.
- Nada mais muda (log do motor já registra o `objetivo` como string).

### 3.4 Frontend (`otimizacao_form.html`)

Substituir o `<select>` único por dois:

1. **Nutriente:** Energia (kcal) · Proteína (g) · Carboidratos (g) · Lipídios (g) ·
   Fibras (g) · Sódio (mg) · Potássio (mg) · Fósforo (mg) · Cálcio (mg) · Ferro (mg) ·
   Gordura Saturada (g) · Custo (R$, aviso "sem dados cadastrados")
2. **Direção:** Maximizar · Minimizar

Default = Maximizar Energia (comportamento atual). O JS monta `objetivo = sentido + '_' + nutriente`.

### 3.5 Fluxo do plano (`api/plano.py`) — INALTERADO

O cardápio do plano continua `target` (acertar a meta kcal do paciente é o objetivo
correto quando há plano). Extensão futura opcional (ver §5): deixar o nutricionista
escolher objetivo custom por plano/paciente (ex.: renal → `min_sodio`).

## 4. Decisões abertas (Bruno)

1. **Tratamento de NULL no nutriente objetivo.** Hoje `COALESCE(..., 0)` faz prato sem
   dado virar "zero" — inofensivo p/ max_energia, mas **perigoso p/ minimização**
   (ex.: `min_sodio` trataria 24 pratos sem medição como "sódio zero" e os preferiria).
   Recomendação: **excluir do conjunto candidato** pratos com NULL no nutriente
   objetivo (mesma política dos industrializados) + aviso no resultado. Alternativa:
   manter 0 (comportamento atual).
2. **`custo` na lista.** Dados zerados (0/402) — `min_custo` hoje daria qualquer
   cardápio. Recomendo incluir com aviso na UI (já prepara quando `custo_por_100g`
   for preenchido) ou deixar de fora até ter dados.
3. **Plano custom** (fase 2): quer opção de objetivo custom no cardápio do plano?

## 5. Fora de escopo (fase 2, se aprovado)

- Objetivo custom no fluxo de planos por paciente (`/planos/<id>/cardapio`) —
  ex.: renal `min_sodio` respeitando as metas do plano como restrições.
- Regra de **variedade** ligada ao objetivo (ex.: "não repetir prato X dias seguidos").

## 6. Testes de validação (read-only, sem gravar)

Script `/tmp/test_objetivo_generico.py` (padrão dos testes anteriores):
- `min_sodio` → sódio total do cardápio **menor** que `max_energia` (mesma dieta/dias)
- `max_proteina` → proteína total **maior** que `max_energia`
- `min_fosforo` → viável na dieta renal (se houver)
- `max_energia` reproduz resultado atual (regressão)
- `objetivo` inválido (`min_xyz`, `max_`) → erro com lista válida
- registro no `logs/motor_otimizacao.log` com o objetivo novo

## 7. Passos de implementação

1. Doc aprovado → alterar `criar_modelo_otimizacao` (parse + sense + coluna)
2. `COLUNAS_NUTRIENTES`/SELECT: adicionar `custo_total`
3. Validação no endpoint (400 com lista válida)
4. Frontend: 2 selects + montagem do payload
5. Rodar `/tmp/test_objetivo_generico.py` (PuLP read-only no banco real)
6. Subir instância temporária na 5001 e validar via curl (sem derrubar a 5000)
