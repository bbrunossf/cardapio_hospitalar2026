# Análise — Integração WolframAlpha + Plano por Paciente (novo_cardapio)

> **Data:** 09/08/2026
> **Fonte analisada:** `cardapio_crew/resultado_final_wolfram.md` (Módulo 8, RF-801 a RF-812)
> **Docs oficiais consultadas:** Full Results API, Short Answers API, LLM API, Simple/Spoken/Conversational APIs
> **Banco analisado:** `cardapio_hospitalar.db` (SQLite, schema v5/v6)

---

## 1. O que o documento do CrewAI entrega (aproveitável)

O design do `WolframDietClient` é **sólido e reutilizável**:

- ✅ Arquitetura em camadas: cliente → resultado → adaptador PuLP
- ✅ Hierarquia de exceções (ErroConfiguracao, ErroAPI, ErroTimeout, ErroParsing)
- ✅ Fallbacks locais clinicamente aceitos: Mifflin-St Jeor (TMB), fator de atividade (GET), regra 7700 kcal/kg (meta), distribuição padrão de macros
- ✅ Cache com TTL (RF-812) — essencial para quota da API
- ✅ Adaptador PuLP com tolerâncias (±10% energia, ±15% macros) + verificação de atingibilidade (RF-808/809)
- ✅ Retry com backoff exponencial e tratamento 403/503

**Pode ser aproveitado quase integralmente** como especificação — precisa de correções pontuais (seção 2) e adaptação ao modelo `pacientes` real (seção 5).

---

## 2. Correções e melhorias no design

### 2.1 BUG: regra do déficit ignora o prazo (fallback)
No `_fallback_meta`:
```
deficit_semanal = diff_kg * 7700      # "semanal" mas é o TOTAL
deficit_diario  = deficit_semanal / 7  # divide por 7 (dias da semana), ignora prazo_dias
```
O correto é espalhar o déficit total pelo prazo inteiro:
```
total_kcal      = diff_kg * 7700
deficit_diario  = total_kcal / prazo_dias     # ex: 5kg → 38.500 kcal / 56 dias ≈ -688 kcal/dia
```
Do jeito escrito, perder 5 kg em 8 semanas daria -5.500 kcal/dia (absurdo). A variável `semanas` é calculada e nunca usada.

### 2.2 Endpoint: usar Short Answers para valores únicos
O doc usa só a **Full Results API** (`v2/query`) com parse de XML. Para TMB, GET e meta calórica (1 valor por consulta), o **Short Answers API** é muito melhor:

```
GET https://api.wolframalpha.com/v1/result?appid=XXX&i=basal+metabolic+rate+male+30+years+175cm+85kg
→ "1886 kcal/day (kilocalories per day)"
```
- Retorna texto puro (o pod "Result") — **sem parse de XML/JSON**
- Parâmetro é `i` (não `input`)
- Timeout default 5s; HTTP 501 = query não interpretável (aciona fallback)
- Menor custo de processamento e de tokens

Para macros (vários valores), usar **Full Results com `output=json`** + `includepodid=Result` + `format=plaintext` (parse de JSON é mais robusto que XML). Alternativa moderna: **LLM API** (`www.wolframalpha.com/api/v1/llm-api`) que devolve texto estruturado para LLM ("Query:", "Input interpretation:", "Result:", ...) — útil para gerar a justificativa do plano e até para o kimi interpretar.

### 2.3 Faltou `units=metric`
Wolfram pode responder em unidades imperiais dependendo da query. Adicionar **`units=metric`** em todas as chamadas garante "kcal/day" consistente no parsing.

### 2.4 RF-810 e RF-811 não cobertos
- RF-810: kcal/macros **por refeição** e % do total diário — é pós-otimização, não Wolfram
- RF-811: validação de aderência da refeição à meta — mesmo
Ambos são outputs do motor PuLP + cálculo simples — incluir na implementação (o doc não cobre).

### 2.5 Direção do tempo: prazo ⇄ déficit
O doc trata `prazo_dias` como **entrada**. O fluxo do nutricionista também pede o **inverso**: dado o déficit (ex: -500 kcal/dia), estimar o tempo até o objetivo. Wolfram responde:
- "how long to lose 5 kg at a 500 kcal/day deficit" → ~10 semanas

Implementar os dois sentidos (o `calcular_plano_completo` deve aceitar prazo OU déficit e preencher o outro).

### 2.6 Objetivo do PuLP: "Maximizar Energia" conflita com plano de perda
O motor atual usa `LpMaximize` de energia. Com restrições [min,max], a solução tende ao teto — ruim para perda de peso. Sugestão: quando houver plano do paciente, usar **objetivo de TARGET** (minimizar desvio absoluto da meta_kcal) ou flag `modo='perda'` com `LpMinimize`. Atingir a meta dentro da faixa é o que interessa, não maximizar.

---

## 3. O que mais a API Wolfram oferece (personalização)

Além de TMB / GET / meta calórica / macros, o domínio Health & Nutrition da Wolfram computa:

| Item | Query exemplo | Uso no plano |
|---|---|---|
| **IMC** | "BMI male 30 years 175cm 85kg" | classificação + acompanhamento |
| **Peso ideal** | "ideal weight for 175cm male 30 years" | alvo sugerido automático |
| **% gordura corporal** | "body fat percentage male 175cm 85kg waist 95cm neck 40cm" | perfil mais preciso (requer cintura/pescoço) |
| **Equação de TMB específica** | "basal metabolic rate using Mifflin-St Jeor equation ..." | escolher fórmula (cross-check do fallback) |
| **Tempo até a meta** | "how long to lose 5 kg at 500 kcal/day deficit" | estimativa de prazo (RF-805 inverso) |
| **Água diária** | "daily water intake male 30 years 85kg" | meta de hidratação no plano |
| **Zonas de FC / exercício** | "target heart rate zones male 30 years" | bônus p/ plano de atividade |
| **Interpretação de refeição** | "nutrition of 200g grilled chicken" | validação de pratos (uso futuro) |

**Observação importante:** cintura e quadril já existem no `pacientes` — dá para calcular gordura corporal sem pedir campo novo (falta só `pescoço_cm` para o método da Marinha, opcional).

### Quotas (tier grátis, valores típicos)
~2.000 queries/mês por AppID (Short Answers e Full Results) e ~1.000/mês (LLM API). Com **cache + fallback** (que o doc já prevê) e ~4-5 chamadas por paciente, a quota é folgada — e cada plano novo reaproveita cache de pacientes com mesmos parâmetros.

---

## 4. Fluxo proposto (melhorado)

```
1. Nutricionista abre o paciente cadastrado
2. "Novo plano nutricional" → form:
   objetivo (perder/ganhar/manter), peso_alvo_kg,
   nivel_atividade (NOVO campo), prazo_dias OU déficit diário,
   perfil_macro (equilibrado/hipocalórico/hiperproteico/hipolipídico)
3. Backend: WolframDietClient.calcular_plano_completo(paciente, meta)
   → TMB, GET, meta_kcal, déficit, macros (com fallback + alertas)
   → se prazo vazio: query inversa estima o prazo
4. Pré-validação de ATINGIBILIDADE (RF-808/809):
   meta dentro da faixa viável com os pratos disponíveis?
   → sugestão automática de ajuste (prazo/meta) antes de salvar
5. Nutricionista revisa o resumo (valores + alertas de fallback) e CONFIRMA
6. Salva plano_paciente (resultado Wolfram + metas) — vínculo paciente
7. Otimização PuLP roda com:
   restrições clínicas da dieta base  +  overrides do plano
   (energia ±10%, macros ±15%) + elegibilidade do paciente
   → objetivo TARGET (não maximizar) quando há plano
8. Cardápio gerado é salvo (cardapios_salvos → dias → refeições)
   vinculado ao plano/paciente (versionado v1, v2...)
```

**Ponto de integração no código atual:** `api/otimizacao.py::criar_modelo_otimizacao(dados, dias)` já consome `restricoes_nutricionais` (min/max por nutriente/dia) e `regras_elegibilidade`. Basta aceitar um dict `overrides` do plano do paciente (energia_kcal/proteina/carboidrato/lipidios min/max) mesclado nas restrições — sem tocar no resto do motor.

---

## 5. Estado do banco — suficiente? NÃO (gap analysis)

### Tabelas atuais (16)
`alimento_versoes, alimentos_industrializados, dieta_refeicoes, dietas, ingredientes, pacientes, prato_composicao, pratos, regras_composicao, regras_elegibilidade_dieta, regras_sensoriais_gerais, regras_variedade, restricoes_nutricionais_dieta, tipos_preparacoes, tipos_refeicao`

### `pacientes` hoje
`id, nome, data_nascimento, sexo, peso_kg, altura_cm, cintura_cm, quadril_cm, objetivo, observacoes, criado_em, editado_em, desativado`

### O que FALTA (não existe nada de plano/meta/cardápio salvo)

| Necessidade do fluxo | Estado atual | Ação |
|---|---|---|
| Nível de atividade física (GET exige) | ❌ não existe | + coluna `nivel_atividade_fisica` em pacientes |
| Meta do paciente (peso_alvo, prazo, déficit, perfil) | ❌ não existe | nova tabela `planos_nutricionais` |
| Resultado Wolfram (TMB, GET, meta, macros, alertas, resposta bruta) | ❌ não existe | campos no plano + tabela de log/auditoria |
| Regras específicas do paciente (alergias/exclusões) | ❌ só por dieta global | nova tabela `restricoes_paciente` (ou reuso elegibilidade) |
| Cardápio dimensionado salvo p/ paciente | ❌ otimização roda solta | tabelas `cardapios_salvos`, `cardapio_dias`, `cardapio_refeicoes` |
| Acompanhamento (peso ao longo do tempo) | ❌ só peso atual | tabela `peso_historico` (opcional, p/ evolução) |

### Sugestão de schema (adaptado do v7 do crewai ao modelo `pacientes`)

```sql
-- Meta + resultado Wolfram por paciente (1:N — paciente pode ter vários planos)
CREATE TABLE planos_nutricionais (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paciente_id INTEGER NOT NULL REFERENCES pacientes(id) ON DELETE CASCADE,
    objetivo VARCHAR(20) NOT NULL,            -- perder | ganhar | manter
    peso_alvo_kg DECIMAL(6,2),
    prazo_dias INTEGER,
    deficit_diario_kcal DECIMAL(8,2),          -- negativo p/ perda
    nivel_atividade VARCHAR(20),
    perfil_macro VARCHAR(20) DEFAULT 'equilibrado',
    tmb_kcal DECIMAL(8,2),
    get_kcal DECIMAL(8,2),
    meta_kcal DECIMAL(8,2),
    proteinas_g DECIMAL(8,2), carboidratos_g DECIMAL(8,2), lipidios_g DECIMAL(8,2),
    proteinas_pct DECIMAL(5,2), carboidratos_pct DECIMAL(5,2), lipidios_pct DECIMAL(5,2),
    fonte VARCHAR(10) DEFAULT 'wolfram',       -- wolfram | fallback
    alertas TEXT,                              -- JSON: fallbacks aplicados
    status VARCHAR(20) DEFAULT 'ativo',        -- ativo | concluido | cancelado
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    editado_em DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Auditoria: resposta bruta da API (diagnóstico de parsing/fallback)
CREATE TABLE wolfram_consultas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plano_id INTEGER REFERENCES planos_nutricionais(id) ON DELETE SET NULL,
    query VARCHAR(500) NOT NULL,
    api VARCHAR(30) NOT NULL,                  -- short_answers | full_results | llm
    resposta TEXT,
    ok BOOLEAN DEFAULT 1,
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Regras exclusivas do paciente (exclusões/alergias — pluga na elegibilidade do PuLP)
CREATE TABLE restricoes_paciente (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paciente_id INTEGER NOT NULL REFERENCES pacientes(id) ON DELETE CASCADE,
    tipo VARCHAR(20) NOT NULL,                 -- alergia | restricao | preferencia
    atributo VARCHAR(50),                      -- ex: tipo_prato, ingrediente, cor_predominante
    valor VARCHAR(100),
    observacao TEXT
);

-- Cardápio dimensionado salvo (versionado)
CREATE TABLE cardapios_salvos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paciente_id INTEGER NOT NULL REFERENCES pacientes(id) ON DELETE CASCADE,
    plano_id INTEGER REFERENCES planos_nutricionais(id) ON DELETE SET NULL,
    dieta_id INTEGER REFERENCES dietas(id) ON DELETE SET NULL,
    nome VARCHAR(100),
    versao INTEGER DEFAULT 1,
    dias INTEGER DEFAULT 7,
    data_inicio DATE, data_fim DATE,
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE cardapio_dias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cardapio_id INTEGER NOT NULL REFERENCES cardapios_salvos(id) ON DELETE CASCADE,
    dia_numero INTEGER NOT NULL,
    energia_kcal_total DECIMAL(8,2),
    UNIQUE (cardapio_id, dia_numero)
);

CREATE TABLE cardapio_refeicoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cardapio_dia_id INTEGER NOT NULL REFERENCES cardapio_dias(id) ON DELETE CASCADE,
    tipo_refeicao_id INTEGER NOT NULL REFERENCES tipos_refeicao(id),
    prato_id INTEGER NOT NULL REFERENCES pratos(id),
    porcao_g DECIMAL(8,2)
);
```

> **Nota:** O crewai propõe tabela `usuarios` genérica (v7). O projeto real já usa `pacientes` com página própria — **não migrar para `usuarios`**; adaptar as tabelas novas com FK `paciente_id` (menor atrito, mantém o que já funciona).

---

## 6. Resumo executivo

1. **Aproveitar** o `WolframDietClient` do doc quase como está (arquitetura, fallbacks, cache, adaptador PuLP).
2. **Corrigir** o bug do déficit (7700 kcal ÷ prazo, não ÷ 7) e adicionar `units=metric`.
3. **Simplificar** com Short Answers (`v1/result`, param `i`) para TMB/GET/meta; Full Results `output=json` para macros; LLM API como opção para justificativa do plano.
4. **Ampliar** com IMC, peso ideal, % gordura (já temos cintura/quadril), tempo-para-meta inverso, água diária.
5. **Banco: não está suficiente.** Faltam: `nivel_atividade_fisica` no paciente, `planos_nutricionais`, `restricoes_paciente`, `cardapios_salvos/dias/refeicoes` (+ `wolfram_consultas` p/ auditoria).
6. **Fluxo**: form de plano → cálculo Wolfram → pré-validação de atingibilidade → confirmação do nutricionista → PuLP com overrides (objetivo TARGET p/ perda) → cardápio salvo versionado.

---

## 7. Status da implementação (09/08/2026)

### Concluído e testado ✅

- **`wolfram_client.py`**: cliente completo com Short Answers + Full Results,
  cache TTL, retry com backoff, hierarquia de exceções, fallbacks clínicos e auditoria
  (`consultas` → `wolfram_consultas`).
- **`models_plano.py`**: 6 modelos SQLAlchemy (PlanoNutricional, WolframConsulta,
  RestricaoPaciente, CardapioSalvo, CardapioDia, CardapioRefeicao) — DDL aplicado no banco.
- **`api/plano.py`**: blueprint com rotas:
  - `POST /api/planos` — calcula plano via Wolfram + salva (201)
  - `GET /api/pacientes/<id>/planos` — lista planos do paciente
  - `GET/DELETE /api/planos/<id>` — detalhe / cancelar
  - `POST /api/planos/<id>/cardapio` — PuLP com overrides + salva versionado
  - `GET /api/cardapios/<id>` — cardápio salvo completo (JSON)
  - `GET /planos` — **seleção de paciente** (nunca lista geral; redireciona com `?paciente_id=`)
  - `GET /pacientes/<id>/planos` — página com planos **somente** daquele paciente
  - `GET /planos/novo` — form (puxa peso/altura do cadastro; permite preencher se faltar)
  - `GET /planos/<id>` — detalhe do plano + cardápios linkados
  - `GET /cardapios/<id>` — **página de visualização** do cardápio (dias × refeições × pratos)
- **`api/otimizacao.py`**: `criar_modelo_otimizacao(dados, dias, overrides, objetivo)`
  — objetivo `target` (minimiza desvio da meta) e overrides por nutriente que
  **substituem** as faixas genéricas da dieta (meta individual prevalece).
- **`api/paciente.py`**: corrigido `_preencher_paciente` para salvar
  `nivel_atividade_fisica` (antes o PUT ignorava o campo).
- **Templates**: `planos.html` (lista por paciente), `planos_selecao.html` (escolha
  do paciente), `plano_form.html` (com dados do cadastro + aviso de campos faltantes),
  `plano_detalhe.html`, `cardapio_detalhe.html`.
- **Navbar standalone**: itens fixos "Planos" e "Pacientes" fora do menu do Flask-Admin.
- **UX decidida (a pedido do usuário)**: planos são SEMPRE vistos por paciente —
  seleciona o paciente primeiro (`/planos` ou botão "Planos" no card de `/pacientes`),
  depois vê somente os planos dele. Não existe lista geral de planos.

### Corrigido durante a implementação (descobertas da API, 09/08/2026)

1. **GET/TDEE**: a Wolfram NÃO interpreta "total daily energy expenditure" (501).
   A query que funciona é `energy expenditure male 30y 175cm 85kg` via **Full Results**,
   lendo o pod `EnergyExpenditure` (tabela por nível de atividade: sedentary 2225,
   lightly 2549, moderately 2874, very 3198, extra 3523 Cal/d).
2. **Meta de perda**: "lose 5 kg in 8 weeks" → 501. Funciona a forma por taxa semanal:
   `calories to lose weight at 0.62 kg per week ...` → pod `SuggestedCaloricIntake`.
3. **Ganho de peso: NÃO suportado** pela API (todas as variações → 501) → fallback
   local (7700 kcal/kg ÷ prazo) com alerta.
4. **Macros: NÃO suportado** (Short Answers, Full Results e LLM API → 501 em 9 variações)
   → distribuição por perfil (30/40/30 etc.) com alerta.
5. **Bug do PuLP**: overrides interseccionavam com restrições da dieta (proteína
   50-100g da LIVRE vs 123-166g do plano → Infeasible). Corrigido: overrides
   **substituem** a restrição da dieta para o mesmo nutriente.
6. **Form de plano**: paciente sem peso/altura no cadastro bloqueava o cálculo sem
   explicação. Corrigido: o form puxa os dados do cadastro via `/api/pacientes/<id>`,
   mostra aviso + campos destacados quando faltam, e salva os valores no cadastro
   (PUT) antes de criar o plano.
7. **`nivel_atividade_fisica`**: era enviado pelo form mas ignorado pelo backend
   (`_preencher_paciente` não copiava o campo) — corrigido.

### Teste de fumaça (paciente #1 Bruno Oliveira)

- Plano #2: perder 5kg em 56 dias → TMB 1678, GET 2601, meta 1927 kcal/dia,
  déficit -674 (≈ 7700×5/56 = 687), macros P/C/L 144.5/192.7/64.2 g.
- Cardápio v1 (7 dias): **Optimal**, média **1927.0 kcal/dia** (bate exatamente na
  meta), energia diária 1906-1945 (faixa ±10%), 108 refeições salvas.
- `wolfram_consultas`: 8 registros de auditoria (TMB via Short Answers ok;
  GET/meta via Full Results ok; macros fallback).
- Plano #3 após a correção do form: TMB 1678, GET 2601, meta 1860 kcal/dia
  (peso atualizado para 78.5 kg no cadastro via PUT).

### Pendências

- `restricoes_paciente` (tabela criada, sem rota CRUD ainda) — plugar na elegibilidade
  do PuLP (futuro).
- `peso_historico` (evolução do paciente) — opcional.
- Atualizar README com as novas rotas.
- Dados de teste no banco (3 planos + 4 cardápios do paciente #1) — aguardando
  decisão de limpar ou manter como exemplo.
- Servidor Flask roda como processo gerenciado (porta 5000); para persistência
  independente, rodar como serviço ou no terminal do usuário.
