# Personalização por paciente no motor de otimização

> Decisão de arquitetura: **catálogo global + regras por paciente**. Ingredientes e pratos são
> sempre os mesmos (referenciados, nunca copiados); as regras do motor ganham **tabelas
> dedicadas por paciente** (espelho do schema das tabelas de regra existentes, com `paciente_id`),
> de preenchimento **opcional** — o que o paciente não preenche herda da dieta; o que preenche vence.
> Status: **proposto (16/08/2026)** — aguardando aprovação do Bruno.
> Data: 16/08/2026

## 1. Contexto

O motor de otimização (`api/otimizacao.py`) hoje é 100% orientado a **dietas globais**:

- `carregar_dados_otimizacao(dieta_nome)` carrega regras filtradas por `dieta_id`
  (`restricoes_nutricionais_dieta`, `regras_elegibilidade_dieta`) + regras globais
  (`regras_composicao`, `regras_variedade`, `regras_sensoriais_gerais`);
- a única personalização por paciente existente é via **plano nutricional**
  (`_overrides_do_plano` em `api/plano.py`): faixas de `energia_kcal` (meta ±10%) e
  P/C/L (±15%) que **substituem** as faixas da dieta no PuLP (linhas 269–295 de
  `api/otimizacao.py`);
- `restricoes_paciente` existe no banco (0 linhas, sem CRUD, sem timestamps) mas
  **não é lida por ninguém** — pendência conhecida "plugar na elegibilidade do PuLP".

O que falta para personalização real por paciente:

1. **Micronutrientes** — sódio, potássio, fósforo, fibra etc. (o plano só cobre kcal/P/C/L);
2. **Elegibilidade sensorial** — consistência/textura/temperatura por condição clínica
   (disfagia → pastosa/líquida), independente da dieta base;
3. **Exclusões** — prato específico ou ingrediente (alergia: tudo que contém leite);
4. **Aversões/variedade** — nunca repetir um tipo de prato (ex.: peixe).

## 2. Princípio: catálogo global + regras por paciente

| Camada | Tabelas | Estratégia |
|---|---|---|
| **Catálogo** (sempre igual) | `pratos`, `ingredientes`, `prato_composicao`, `tipos_preparacoes`, `tipos_refeicao`, `alimentos_industrializados`, `passos_preparo` | **Referenciar, nunca copiar** — corrigir 1 nutriente de ingrediente não pode virar N cópias |
| **Regras** (por paciente) | espelhos das tabelas de regra com `paciente_id` (novas) | **Tabelas dedicadas por paciente**, preenchimento opcional (delta) |
| **Resultados** (por paciente) | `pacientes`, `planos_nutricionais`, `cardapios_salvos`→`dias`→`refeicoes` | Já são por paciente — nada a fazer |

**Semântica do preenchimento opcional (delta):** o nutricionista só preenche o que difere da
dieta base. Ex.: paciente renal usa a dieta RENAL NÃO DIALÍTICO e preenche apenas
`potassio_mg ≤ 3000`; todo o resto das regras vem da dieta. Se um dia precisar de um cardápio
100% individual, preenche todas as regras do paciente — o mecanismo suporta os dois extremos.

## 3. Modelagem: tabelas de regras dedicadas por paciente

Espelham o schema das tabelas de regra existentes (mesmas colunas, `paciente_id` no lugar do
filtro por dieta), seguindo as convenções do banco. DDL completo em
`docs/sql/personalizacao_por_paciente.sql`.

### 3.1 Tabelas novas

| Tabela nova | Espelho de | Colunas-chave | Cobre |
|---|---|---|---|
| `restricoes_nutricionais_paciente` | `restricoes_nutricionais_dieta` | `nutriente`, `valor_minimo`, `valor_maximo` | Sódio, potássio, fósforo, fibra, kcal, macros... — o que o plano automático não cobre |
| `regras_elegibilidade_paciente` | `regras_elegibilidade_dieta` | `atributo`, `valores_permitidos`, `operador` (`IN`/`NOT IN`) | Disfagia (consistência pastosa/líquida), temperatura, textura, tipo de prato |
| `regras_variedade_paciente` | `regras_variedade` | `tipo_prato_id`, `dias_minimos_repeticao`, `frequencia_maxima_semanal` | Aversão (frequência 0 = nunca servir); repetição controlada |
| `exclusoes_paciente` | — (nova) | `prato_id` XOR `ingrediente_id` (CHECK), `motivo` | Alergia a ingrediente (remove pratos que o contêm via `prato_composicao`); prato específico banido |

### 3.2 `restricoes_paciente` (existente)

Fica como **registro clínico livre** (`alergia`/`preferencia`/observações) — informativo, não
entra no motor. Se na prática não for usada, pode ser descartada depois (decisão do Bruno).

### 3.3 Precedência (quem vence)

```
dieta base  →  plano (overrides automáticos ±10/±15%)  →  tabela de regras do paciente (manual)
```
Por tipo de regra: **paciente preenchido > dieta > ausente**. Implementação:
- `restricoes_nutricionais_paciente` → converte em overrides e funde por último (o motor
  existente já substitui por nutriente, linhas 269–295);
- `regras_elegibilidade_paciente` → interseção (`IN`) ou subtração (`NOT IN`) sobre os
  valores da dieta; interseção vazia → `Infeasible` com mensagem clara;
- `regras_variedade_paciente` → substitui a regra global do mesmo `tipo_prato_id`;
- `exclusoes_paciente` → remove pratos do conjunto candidato (ingrediente: subquery em
  `prato_composicao`).

### 3.4 Fora do escopo (deliberadamente não replicado)

- `regras_composicao` (qtd de pratos por refeição) — estrutura do serviço, não do paciente;
- `regras_sensoriais_gerais` (sem_quentes) — casos pontuais cobertos por
  `regras_elegibilidade_paciente` (`temperatura_servimento NOT IN ('Quente')`);
- `dieta_refeicoes` (quais refeições o paciente faz) — caso raro (jejum intermitente);
  se necessário, tabela fraca `paciente_refeicoes` (pequena), não cópia.

## 4. Onde entra no código

1. **`carregar_dados_otimizacao(dieta_nome, paciente_id=None)`** — novo parâmetro opcional;
   após carregar as regras da dieta, aplica as do paciente (só as linhas preenchidas):
   - `restricoes_nutricionais_paciente` → funde no dict de overrides (`dados['overrides_paciente']`);
   - `regras_elegibilidade_paciente` → interseção/subtração sobre `regras_elegibilidade`
     (reusar `MAP_ATRIBUTOS` existente);
   - `exclusoes_paciente` → filtra `dados['pratos']`;
   - `regras_variedade_paciente` → substitui entradas de `regras_variedade`.
2. **`api_gerar_cardapio`** (`api/plano.py`) já tem `plano.paciente_id` → passa ao carregador
   e soma o delta ao `overrides` (precedência §3.3).
3. **`executar_otimizacao`** (`/api/otimizacao/executar`) — aceitar `paciente_id` opcional no
   payload (a tela `/otimizacao` ganha seletor de paciente; UX padrão do projeto: SEMPRE por paciente).
4. **CRUD** — página do paciente (`/pacientes/<id>`) ganha bloco "Regras do cardápio" com as
   quatro abas (faixas, elegibilidade, variedade, exclusões), mesmo padrão do módulo Ficha Técnica.
   Regra: sem ALTER/INSERT/UPDATE sem o Bruno rodar.

## 5. DDL

`docs/sql/personalizacao_por_paciente.sql`:

```sql
-- 1. Faixas nutricionais por paciente (espelho de restricoes_nutricionais_dieta)
CREATE TABLE restricoes_nutricionais_paciente (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paciente_id INTEGER NOT NULL REFERENCES pacientes(id) ON DELETE CASCADE,
    nutriente VARCHAR(50) NOT NULL,        -- energia_kcal, sodio_mg, potassio_mg, fosforo_mg, fibra_alimentar_g...
    valor_minimo DECIMAL(10,2),
    valor_maximo DECIMAL(10,2),
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    editado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    desativado BOOLEAN DEFAULT 0,
    CHECK (valor_minimo IS NOT NULL OR valor_maximo IS NOT NULL)
);

-- 2. Elegibilidade por paciente (espelho de regras_elegibilidade_dieta)
CREATE TABLE regras_elegibilidade_paciente (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paciente_id INTEGER NOT NULL REFERENCES pacientes(id) ON DELETE CASCADE,
    atributo VARCHAR(50) NOT NULL,         -- consistencia, textura, cor_predominante, temperatura_servimento, tipo_prato
    valores_permitidos TEXT NOT NULL,      -- 'PASTOSA;LÍQUIDA' (separador ;)
    operador VARCHAR(20) NOT NULL DEFAULT 'IN',  -- IN (interseção) | NOT IN (subtração)
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    editado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    desativado BOOLEAN DEFAULT 0,
    CHECK (operador IN ('IN','NOT IN'))
);

-- 3. Variedade/aversão por paciente (espelho de regras_variedade)
CREATE TABLE regras_variedade_paciente (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paciente_id INTEGER NOT NULL REFERENCES pacientes(id) ON DELETE CASCADE,
    tipo_prato_id INTEGER NOT NULL REFERENCES tipos_preparacoes(id) ON DELETE CASCADE,
    dias_minimos_repeticao INTEGER,
    frequencia_maxima_semanal INTEGER,     -- 0 = nunca servir (aversão)
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    editado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    desativado BOOLEAN DEFAULT 0
);

-- 4. Exclusões por paciente (prato OU ingrediente)
CREATE TABLE exclusoes_paciente (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paciente_id INTEGER NOT NULL REFERENCES pacientes(id) ON DELETE CASCADE,
    prato_id INTEGER REFERENCES pratos(id) ON DELETE CASCADE,
    ingrediente_id INTEGER REFERENCES ingredientes(id) ON DELETE CASCADE,
    motivo TEXT,
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    editado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    desativado BOOLEAN DEFAULT 0,
    CHECK ((prato_id IS NOT NULL) + (ingrediente_id IS NOT NULL) = 1)
);

CREATE INDEX idx_rnp_paciente ON restricoes_nutricionais_paciente(paciente_id);
CREATE INDEX idx_rep_paciente ON regras_elegibilidade_paciente(paciente_id);
CREATE INDEX idx_rvp_paciente ON regras_variedade_paciente(paciente_id, tipo_prato_id);
CREATE INDEX idx_ep_paciente ON exclusoes_paciente(paciente_id);
```

## 6. Fases

- **Fase 1** — DDL + CRUD na página do paciente + `restricoes_nutricionais_paciente` e
  `exclusoes_paciente` no motor (via `api_gerar_cardapio`, que já tem `paciente_id`).
  Cobre os casos clínicos mais urgentes (renal: K/fósforo/sódio; alergia).
- **Fase 2** — `regras_elegibilidade_paciente` (disfagia, temperatura) + `regras_variedade_paciente`
  (aversão).
- **Fase 3 (opcional)** — `paciente_refeicoes`, porcionamento individual (`regras_composicao`).

## 7. Casos de uso (validação manual sugerida)

| Paciente | Regras preenchidas | Resultado esperado |
|---|---|---|
| Renal dialítico (dieta RENAL DIALÍTICO) | faixas `potassio_mg≤3000`, `fosforo_mg≤900`, `sodio_mg≤2000`; excluir embutidos | Cardápio dentro das faixas, sem embutidos |
| Disfagia (dieta BRANDA) | elegibilidade `consistencia IN (PASTOSA;LÍQUIDA)` | Só pratos pastosos/líquidos (interseção com BRANDA) |
| Alergia a lactose (dieta LIVRE) | exclusão `ingrediente_id = leite` | Nenhum prato contendo leite (via `prato_composicao`) |
| Aversão a peixe (dieta LIVRE) | variedade `tipo_prato_id` dos peixes, `frequencia_maxima_semanal = 0` | Nenhum peixe em N dias |

## 8. Decisões abertas

- As regras são do **paciente** (valem para todos os planos). Confirmar se alguma precisará ser
  **por plano** (ex.: restrição temporária durante o tratamento) — se sim, acrescentar
  `plano_id` opcional (nullable) nas tabelas.
- `regras_elegibilidade_paciente`: validar com a nutricionista se `NOT IN` (banir) é necessário
  de cara ou se `IN` (permitir) cobre os casos iniciais.
- Interação com o **Posso Comer?**: as regras do paciente também devem alimentar o
  contexto/alternativas do módulo (fora do escopo do motor, mas natural de ligar depois).
- `restricoes_paciente` (existente, genérica): manter como registro clínico livre ou descartar.
