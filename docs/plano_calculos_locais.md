# Plano — Cálculos Nutricionais Locais (novo_cardapio)

> **Data:** 10/08/2026
> **Branch:** `feature/calculos-locais`
> **Motivação:** eliminar a dependência de API terceirizada (WolframAlpha) para os
> cálculos do plano nutricional — todas as grandezas são obtidas por fórmulas
> fechadas, públicas e estáveis, calculáveis localmente com determinismo total.

---

## 1. Decisão

Substituir a WolframAlpha como **fonte padrão de cálculo** do plano nutricional
por um pacote Python local (`calculo_nutricional/`). A Wolfram não é removida —
vira **fonte alternativa/benchmark** selecionável por flag, preservando o
trabalho já feito (cliente, auditoria, docs).

**Flag de configuração** (`.env`):

```ini
FONTE_CALCULO=local        # local (padrão) | wolfram
```

- `local` → `calculo_nutricional.calcular_plano_completo()` (determinístico, sem rede)
- `wolfram` → `WolframDietClient.calcular_plano_completo()` (comportamento atual)

## 2. Por que local é a decisão certa

| Grandeza | Fonte atual (Wolfram) | Fórmula local |
|---|---|---|
| TMB | query "basal metabolic rate ..." | Mifflin-St Jeor (padrão clínico) |
| GET/TDEE | pod EnergyExpenditure (tabela) | TMB × fator de atividade |
| Meta calórica | pod SuggestedCaloricIntake | GET + déficit/superávit |
| Déficit/prazo | query "how long to lose ..." | 7700 kcal/kg ÷ prazo (Wishnofsky) |
| Macros | pod de distribuição | % por perfil ÷ (4/4/9 kcal por g) |
| IMC / peso ideal / % gordura | não usado | fórmulas OMS / Devine / Deurenberg |

Benefícios:
- **Zero custo por chamada** (sem quota, sem AppID, sem latência)
- **Determinístico e auditável** — o nutricionista confere a conta no papel
- **Funciona offline** (servidor na LAN, sem depender de internet)
- **Metodologia documentada e escolhível** (equação de TMB configurável)

Ressalva honesta: os valores podem diferir alguns pontos da Wolfram (ela usa uma
média própria de equações). Ex: paciente #1 (M, 30y, 175cm, 85kg) — a Wolfram
retornou TMB 1678; Mifflin-St Jeor local retorna **1798.75** (~7% de diferença).
Isso é esperado e clinicamente aceitável — o ganho é controle total da
metodologia.

## 3. Arquitetura do pacote `calculo_nutricional/`

```
calculo_nutricional/
├── __init__.py      # orquestrador calcular_plano_completo() + re-exports
├── tmb.py           # Mifflin-St Jeor, Harris-Benedict (original/revisada), Katch-McArdle
├── get.py           # GET = TMB × fator de atividade (sedentario..atleta)
├── meta.py          # déficit/superávit, prazo, meta_kcal, projeção de peso (p/ gráfico)
├── macros.py        # distribuição por perfil (30/40/30 etc.), gramas por kcal
├── antropometria.py # IMC + classificação OMS, peso ideal (Devine), % gordura (Deurenberg)
└── validador.py     # faixas clínicas plausíveis + alertas (pré-validação)
```

Todos os módulos são **puro Python stdlib** (sem requests, sem PuLP) — testáveis
isoladamente.

### 3.1 `calcular_plano_completo(dados, meta) -> dict`

Contrato **idêntico** ao `WolframDietClient.calcular_plano_completo`, para o
`api/plano.py` não saber (nem se importar) com a fonte:

```python
{
  "tmb_kcal": float, "get_kcal": float, "meta_kcal": float,
  "deficit_diario_kcal": float, "prazo_dias": int,
  "proteinas_g": float, "carboidratos_g": float, "lipidios_g": float,
  "proteinas_pct": float, "carboidratos_pct": float, "lipidios_pct": float,
  "fonte": "local", "alertas": [str, ...],
  "consultas": [{"query", "api": "local", "resposta", "ok"}, ...],  # auditoria
  "metodo_tmb": "mifflin_st_jeor",
}
```

- `consultas` alimenta a tabela `wolfram_consultas` existente (sem mudança de
  schema — coluna `api` guarda `'local'`).
- Nenhum ALTER/CREATE no banco: a coluna `fonte` (String(10)) comporta `'local'`.

### 3.2 Fórmulas implementadas

**TMB — Mifflin-St Jeor (default):**
- M: `10×peso + 6.25×altura − 5×idade + 5`
- F: `10×peso + 6.25×altura − 5×idade − 161`

**TMB — Harris-Benedict revisada (1984) [opcional via parâmetro]:**
- M: `88.362 + 13.397×peso + 4.799×altura − 5.677×idade`
- F: `447.593 + 9.247×peso + 3.098×altura − 4.330×idade`

**TMB — Katch-McArdle [se houver massa magra]:**
- `370 + 21.6 × massa_magra_kg`

**GET:** `TMB × fator` — sedentario 1.2 | leve 1.375 | moderado 1.55 | intenso 1.725 | atleta 1.9

**Meta:**
- Com prazo: `deficit = ∓(diff_kg × 7700 ÷ prazo_dias)`; `meta = GET + deficit`
- Sem prazo: `deficit` informado ou padrão (perder −500, ganhar +300, manter 0);
  `prazo = round(diff_kg × 7700 ÷ |deficit|)`
- Manter: `deficit = 0`, `meta = GET`

**Macros (kcal por g: proteína 4, carboidrato 4, lipídio 9):**
- equilibrado 30/40/30 · hipocalorico 30/30/40 · hiperproteico 35/35/30 · hipolipidico 25/50/25

**Antropometria:**
- IMC = peso ÷ altura²  (classificação OMS)
- Peso ideal (Devine): M `50 + 0.91×(altura−152.4)`; F `45.5 + 0.91×(altura−152.4)`
- % gordura (Deurenberg): `1.20×IMC + 0.23×idade − 10.8×sexo − 5.4` (sexo: M=1, F=0)

**Projeção de peso (Fase 2 — gráfico d3):**
- `peso(dia) = peso_inicial + (meta_kcal − get_kcal) × dia ÷ 7700`
- Série semanal pronta para o simulador arrastável.

### 3.3 Validador (alertas clínicos)

- IMC fora de 10–60 → alerta
- meta_kcal < 800 ou > 5000 → alerta
- déficit < −1000 kcal/dia → alerta ("déficit agressivo")
- prazo < 14 dias para perda/ganho > 5 kg → alerta
- dados ausentes (peso/altura/idade) → alerta (não bloqueia, usa default)

## 4. Mudanças em `api/plano.py`

1. Renomear `_dados_wolfram` → `_dados_para_calculo` (o dict de entrada é o
   mesmo para ambas as fontes).
2. Em `api_criar_plano`, ler `FONTE_CALCULO` (com fallback de leitura direta do
   `.env` — robustez caso o app rode fora do CLI do flask):
   - `wolfram` → fluxo atual (`WolframDietClient`, erro 502 em falha de rede)
   - senão → `calculo_nutricional.calcular_plano_completo`
3. Auditoria: usar a lista `consultas` comum (do cliente OU do pacote local)
   persistida em `wolfram_consultas` (sem mudança de schema).
4. Nenhuma mudança no PuLP — `_overrides_do_plano` continua consumindo os
   campos do `PlanoNutricional`.

## 5. Fase 2 (fora deste commit) — Simulador interativo d3.js

Página `/planos/<id>/simulador` com drag bidirecional:
- Eixo X: semanas do prazo · Eixo Y: kcal/dia (ou peso)
- Modo 1: arrastar a curva de ingestão → projeção de peso ao vivo
- Modo 2: arrastar o peso-alvo → ingestão média necessária
- Faixa sombreada de déficit seguro (−500 a −1000 kcal/dia)
- d3.js servido localmente em `static/vendor/d3.v7.min.js` (sem CDN)
- Resultado vira override do PuLP

A função `meta.projecao_peso()` deste pacote já entrega a série para o gráfico.

## 6. Pendências / decisões em aberto

- [ ] Escolher se mantém `metodo_tmb` selecionável por paciente (hoje: Mifflin
      global no pacote; campo no plano seria Fase 2)
- [ ] Decidir se a tabela `wolfram_consultas` é renomeada futuramente para algo
      genérico (ex: `consultas_calculo`) — exigiria DDL (feito manualmente por você)
- [ ] Dados de teste do paciente #1 (3 planos + 4 cardápios) — limpar ou manter
- [ ] Atualizar README com as novas rotas
