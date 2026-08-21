# Preferências alimentares do paciente (hábitos → privilégio na otimização)

**Status:** Proposta — aguardando aprovação do Bruno
**Data:** 21/08/2026
**Escopo:** `api/otimizacao.py`, `api/regras_paciente.py` (+ catálogo de grupos), `models_personalizacao.py`, `motor_log.py`, frontend (`planos.html` bloco "Regras do cardápio" + tela de curadoria), `POST /api/otimizacao/executar` e fluxo do plano
**Schema:** 4 tabelas novas — DDL: `docs/sql/preferencias_alimentares.sql` (Bruno executa)

---

## 1. Contexto / problema

O paciente relata o que **costuma comer em cada refeição**. O nutricionista analisa a lista e marca quais alimentos/produtos são **bons hábitos** (privilégio), decidindo em qual regra a condição entra. O cardápio otimizado deve então **privilegiar essas escolhas** — objetivo: mínima intervenção na dieta diária já consolidada do paciente.

Exemplo (pedido): paciente costuma comer pão no café da manhã → regra de composição ("café da manhã com 1 cereal, min=max=1") + o motor **privilegia o grupo pão** (qualquer pão do banco).

## 2. O que já existe (validado no banco/código em 21/08)

- **Composição por refeição × tipo JÁ funciona** no motor: `Comp_Min_R{r}_T{t}`/`Comp_Max_R{r}_T{t}` a partir de `regras_composicao` (`qtd_minima`/`qtd_maxima`). No banco real:
  - CAFÉ DA MANHÃ (refeição 1): `BC1 - Cereal (Café)` com **min=2, max=2** — o "cereal obrigatório" do exemplo já é a regra vigente
  - CEIA (refeição 7): BC1 com **min=1, max=1** — exatamente o padrão min=max=1 descrito
  - ALMOÇO: EN/MD/SD/JC min=max=1 (estrutura rígida)
- **BC1 tem 11 pratos ativos**: 7 pães (francês, brioche, integrais...) + 3 biscoitos + **"Café puro com açúcar"** (dado questionável — classificados juntos). O "grupo pão" é um **subconjunto de BC1** → tipo de preparação NÃO é granularidade suficiente para o privilégio
- **Personalização por paciente Fase 1** (17/08, no ar): CRUD genérico `regras_paciente.py` (`TIPOS`: faixa|elegibilidade|variedade|exclusao) + merge no motor via `carregar_dados_otimizacao(..., paciente_id=...)` — padrão a seguir
- **Registro alimentar 48h** (20/08, no ar): pipeline relato livre → LLM estrutura → lookup no banco (pratos → industrializados → ingredientes) → medidas caseiras. Candidato natural de **fonte do relato**
- **Objetivo atual**: `max_energia` | `target` (desvio da meta kcal). `objetivo_generico.md` (pendente) generaliza para `max_/min_<nutriente>`

**Gaps:** (a) não existe termo de preferência/fidelidade na função objetivo; (b) composição é por `tipo_prato_id`, sem conceito de grupo alimentar; (c) não há fluxo relato → curadoria → regra.

## 3. Conceitos

- **Grupo alimentar**: classificação transversal a `tipos_preparacoes`, de curadoria manual. Ex.: "Pães e cereais" = {7 pães de BC1}. Um prato pode pertencer a N grupos. Industrializados entram em fase 2 (quando o motor deles existir — ver §10).
- **Preferência (privilégio)**: par **(grupo OU prato)** × **(refeição ou todas)** × **prioridade**, por paciente. Marcada **manualmente pela nutricionista** — o sistema não julga hábito bom/mau; ela decide (padrão de curadoria das regras por paciente).
- **Regra de composição por grupo (paciente)**: espelho de `regras_composicao` em nível paciente, usando `grupo_id` — para ajustar o caso individual (ex.: "no café, 1 porção do grupo Pães" sobrepondo o BC1 min=2 da dieta).

## 4. Fluxo proposto (3 blocos)

1. **Relato do paciente por refeição** — fonte: reuso do registro 48h OU módulo próprio de hábitos (decisão D1)
2. **Curadoria da nutricionista** — rota: lista de itens relatados → marcar como privilegiado → decidir a regra (composição por grupo e/ou preferência)
3. **Motor** — (a) composição por grupo (min/max); (b) preferência na função objetivo (lexicográfico 2 estágios, §6.2)

## 5. Schema proposto (DDL em `docs/sql/preferencias_alimentares.sql`)

| tabela | propósito | notas |
|---|---|---|
| `grupos_alimentares` | catálogo de grupos | `nome` UNIQUE; `desativado` |
| `prato_grupos` | vínculo prato↔grupo (N:N) | PK composta `(prato_id, grupo_id)`; padrão `prato_composicao` |
| `preferencias_paciente` | privilégio por paciente | `grupo_id` OU `prato_id` (CHECK =1); `tipo_refeicao_id` NULL = todas; `prioridade INT DEFAULT 1` |
| `regras_composicao_paciente` | composição por grupo em nível paciente | `qtd_minima`/`qtd_maxima`; CHECKs (ao menos um; min≤max) |

Convenções do banco: `id INTEGER PRIMARY KEY AUTOINCREMENT`, `criado_em/editado_em DATETIME DEFAULT CURRENT_TIMESTAMP`, `desativado BOOLEAN DEFAULT 0`, FKs `ON DELETE CASCADE`. Escopo por dono flui da âncora `pacientes.criado_por` (nenhuma coluna de dono — padrão da personalização).

## 6. Motor (`api/otimizacao.py`)

### 6.1 Composição por grupo (paciente)

- `carregar_dados_otimizacao` ganha: grupos + vínculos (`prato_grupos`) + `regras_composicao_paciente` e `preferencias_paciente` quando `paciente_id` presente (mesmo ponto de merge das exclusões)
- Novas restrições espelhando `Comp_Min/Max`, agora somando `X[pid][r][d]` sobre os pratos do grupo: `CompPac_Min_R{r}_G{g}_Dia{d}` / `CompPac_Max_R{r}_G{g}_Dia{d}`
- **Merge com a dieta**: as duas valem (interseção) — ex.: dieta exige 2 BC1 no café + paciente exige 1 pão (min=max=1) → 1 pão + 1 outro BC1. Para "os 2 slots são pães", nutricionista define grupo Pães com min=max=2 no café

### 6.2 Preferência no objetivo — **lexicográfico em 2 estágios (recomendado)**

Derivar pares privilegiados: preferência por grupo → expande para os pratos do grupo (na refeição indicada ou todas); preferência por prato → direto. Coeficiente = `prioridade`.

- **Estágio 1:** maximizar `F = Σ prioridade × X[p][r][d]` (apenas pares privilegiados), com **todas** as demais restrições
- Fixar o ótimo: `Σ prioridade × X ≥ F*` (F* inteiro — sem ε; o conjunto continua viável pois contém a solução do estágio 1)
- **Estágio 2:** resolver o objetivo real (`max_energia` | `target` — ou o futuro `max_/min_<nutriente>`, são ortogonais) com a restrição extra
- Efeito: mantém o hábito **sempre que viável** (ex.: os 2 slots do café viram pães se a nutrição permitir) e entrega o melhor cardápio dentro disso — literalmente "mínimo de intervenções"
- Sem preferências ativas → modelo idêntico ao atual (zero impacto de regressão)

Alternativas (decisão D4): peso λ numa soma única (frágil — mistura kcal com preferência, λ arbitrário, ruim no modo `target`) · mínimo obrigatório por dia (variante dura: "≥ N privilegiados/dia", sem gradação).

**Custo:** 2 solves por execução (estágio 1 costuma ser rápido — objetivo simples; mantém `timeLimit=180`/`gapRel=0.1` em ambos). `motor_log` registra `preferencias` (lista), `fidelidade` (F*/F_max) e tempo por estágio.

### 6.3 Integração

- Vale para a tela `/otimizacao` (quando houver `paciente_id`) **e** para o fluxo do plano (`api_gerar_cardapio`) — ambos passam por `carregar_dados_otimizacao` com `paciente_id`, mesmo padrão das restrições/personalização
- Independe da Fase 2 da personalização (merge de `regras_variedade_paciente`, pendente) — implementar sem conflitar no mesmo ponto de merge
- Guardrail junk: privilégio é curadoria manual + elegibilidade/exclusões continuam valendo; variedade inerte hoje permite repetir pão entre dias — se necessário, limitar com `regras_variedade_paciente` quando o merge da Fase 2 sair

## 7. API

- **Estender `regras_paciente.py`** (`TIPOS`): `preferencia` → `preferencias_paciente`, `composicao` → `regras_composicao_paciente` — reusa o CRUD genérico (GET/POST/PATCH/DELETE soft, gate `paciente_acessivel`) e a UI de abas
- **Catálogo de grupos**: `GET/POST /api/grupos-alimentares` + vínculo `POST /api/pratos/<id>/grupos` (lista de grupos do prato no GET de composição/ficha)
- **Curadoria**: `GET /api/pacientes/<id>/preferencias/sugestoes` — itens relatados (registro/hábitos) + pratos candidatos por refeição, para a nutricionista marcar privilegiados e montar a regra
- **Frontend**: abas novas ("Preferências", "Composição por grupo") no bloco "Regras do cardápio" de `planos.html`; tela de curadoria ligada ao relato

## 8. Log do motor

`motor_log.py`: campos novos por execução — `preferencias` (pares ativos), `fidelidade` (F*/F_max), `tempo_estagio_1_s`, `tempo_estagio_2_s`. Sem preferências: `preferencias: []`, fidelidade omitida (regressão limpa).

## 9. Decisões abertas (Bruno)

1. **Fonte do relato**: reuso do registro 48h (zero schema novo; semântica de recordatório) vs módulo próprio de hábitos por refeição (schema leve, reaproveita o lookup texto→prato; semântica certa de "costuma comer"). *Recomendação: módulo leve de hábitos, reusando o lookup; o registro 48h mantém finalidade própria.*
2. **Granularidade do grupo**: N:N (`prato_grupos`, recomendado) vs 1 grupo por prato (coluna em `pratos`).
3. **Alvo da preferência**: grupo e/ou prato (recomendado: ambos — grupo cobre o exemplo do pão; prato cobre "só pão francês").
4. **Modelagem da preferência**: lexicográfico 2 estágios (recomendado) vs peso λ vs mínimo/dia.
5. **Escopo do estágio 1**: global (Σ sobre dias, recomendado — mais flexível) vs por dia (todo dia ≥ K privilegiados, mais fiel ao hábito diário).
6. **Prioridade**: escalar inteiro (Fase 1: default 1) vs só binário.
7. **Composição por grupo em nível paciente**: tabela nova ok? (alternativa: só preferência, sem `regras_composicao_paciente` — o exemplo do pão funciona só com privilégio sobre o BC1 existente).

## 10. Fora de escopo (fases futuras)

- **Industrializados no privilégio**: `industrializado_grupos` + preferência sobre eles — quando os industrializados entrarem no motor (pendência em aberto)
- **Privilégio automático por frequência do relato** (sem curadoria) — não recomendado (risco de junk; curadoria humana é o guardrail)
- **Variedade ligada à preferência** (não repetir privilegiado em excesso) — junto com o merge da Fase 2 da personalização
- **Sinônimos/lematização de relato** — herda do pipeline do registro

## 11. Testes de validação (read-only, padrão `/tmp/test_*.py`)

- Regressão: `max_energia` sem preferências reproduz resultado atual
- Com preferência (grupo Pães no café): F* = 2 slots BC1 viram pães (conferível na mão — 7 pães de 11 BC1)
- Composição paciente-grupo: min/max aplicados; interseção com a dieta (2 BC1 ∩ 1 pão → 1 pão + 1 não-pão)
- Modo `target` com preferência: desvio da meta mantido + fidelidade
- Preferência em refeição específica vs todas; prioridade diferente (pão > mingau)
- Exclusão remove prato do conjunto ANTES da preferência (nunca privilegiar excluído)
- `motor_log` com `preferencias`/`fidelidade`/tempos

## 12. Passos de implementação

1. Doc aprovado
2. DDL `docs/sql/preferencias_alimentares.sql` (Bruno executa + `PRAGMA table_info`)
3. `models_personalizacao.py`: 4 classes novas (padrão das existentes)
4. `regras_paciente.py`: `TIPOS` + validação para `preferencia` e `composicao`
5. `carregar_dados_otimizacao`: grupos + preferências + composição paciente
6. `criar_modelo_otimizacao`: restrições por grupo + estágio 1/2 (param `preferencias`)
7. `motor_log`: campos novos
8. Catálogo de grupos (API + admin) e `sugestoes` de curadoria
9. Frontend: abas + tela de curadoria
10. Testes `/tmp/test_preferencias_paciente.py` + instância 5001 (sem derrubar a 5000) + E2E do Bruno
