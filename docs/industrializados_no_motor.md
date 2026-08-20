# Industrializados no motor de otimização

> Decisão de arquitetura: tratar `alimentos_industrializados` como **prato** no motor PuLP.
> Status: **aprovado (16/08/2026)** — pendente implementação.
> Data: 16/08/2026 (atualizado 20/08/2026 — seção 3.5: teto de industrializados/dia)

## 1. Contexto

O módulo de rótulo (`api/rotulo.py`, `models_rotulo.py`) cadastra produtos industrializados em
`alimentos_industrializados`, com nutrientes **informados pelo rótulo** (RDC 429/2020 — obrigatórios:
energia, carboidratos, açúcares totais/adicionados, proteínas, gorduras totais/saturadas/trans, fibras,
sódio). A view `vw_alimentos_industrializados_100g` converte os valores da porção do rótulo para base
100g (seção 5.3 do `especificacao_modulo_rotulo.md`).

O motor de otimização (`api/otimizacao.py`) **não considera** essa tabela hoje (verificado 16/08/2026):

- `carregar_dados_otimizacao(dieta_nome, incluir_industrializados=False)` — flag **default False**;
- o endpoint `executar_otimizacao()` chama o carregador **sem a flag** → lista chega vazia;
- `criar_modelo_otimizacao()` tem **zero referências** a `alimentos_industrializados` — as variáveis
  PuLP são criadas somente a partir de `dados['pratos']`.

A infraestrutura de carga existe (`carregar_alimentos_industrializados()`, chave
`'alimentos_industrializados'` no dict de dados) mas é código morto. O desenho original (seção 9 do
spec de rótulo) previa "unificar `ingredientes` (TACO) + `vw_alimentos_industrializados_100g` no
dicionário de entrada do PuLP" — porém foi escrito quando o motor consumia `ingredientes`
(`motor_otimizacao2.py`, legado). O motor atual consome **pratos** com nutrientes pré-agregados, e é
sobre ele que esta decisão é tomada.

## 2. A decisão: prato vs ingrediente

### 2.1 Como o motor funciona hoje

- Variáveis binárias `X[prato_id][refeicao_id][dia]` — 1 se o prato é servido naquela refeição/dia.
- Nutrientes de cada prato vêm prontos da `vw_pratos_nutricional` (calculados da composição).
- Restrições: composição por refeição via `regras_composicao` (tipo_prato × qtd min/max), tipos não
  autorizados por refeição, um prato por dia no máximo, limite de 18 pratos/dia, restrições
  nutricionais da dieta, variedade, elegibilidade (`regras_elegibilidade_dieta`) e sensoriais
  (`regras_sensoriais_gerais`) e teto de industrializados por dia (nova, seção 3.5).

**Não existe variável de ingrediente no modelo.** Ingredientes só entram indiretamente, já somados
nos nutrientes do prato pela view.

### 2.2 Análise

| Critério | Como prato | Como ingrediente |
|---|---|---|
| Encaixe no modelo atual | Direto: vira mais um item em `dados['pratos']` | **Nenhum**: o modelo não compõe pratos na otimização |
| Esforço | Colunas novas + classificação + normalização no carregador + filtro NULL | Reescrever o motor para escolher ingredientes/compor pratos — explosão combinatória, fora do escopo |
| Semântica do caso de uso | Industrializado É servido como item de refeição (biscoito no lanche, suco, iogurte) — é um prato no cardápio | Só faria sentido como matéria-prima de preparo, o que não é o uso real no cardápio hospitalar |
| Regras existentes | Herda composição/variedade/elegibilidade/sensoriais | Precisaria de regras novas para tudo |
| Rótulo 100g | `vw_alimentos_industrializados_100g` já entrega base 100g — mesma lógica de `ingredientes` | Idem, mas sem onde aplicar |

### 2.3 Recomendação

**Tratar como prato.** O modelo otimiza itens servidos; o industrializado é servido como item.
"Como ingrediente" exigiria reescrever o motor — esforço desproporcional para o caso de uso. A
recomendação difere do desenho original da seção 9 justamente porque o motor mudou (de `ingredientes`
para `pratos`) desde então.

## 3. Modelagem proposta

### 3.1 Schema — colunas novas em `alimentos_industrializados`

Seguindo as convenções do banco (`DECIMAL(8,2)`, `desativado` já existe, FK explícita). DDL pronto em
`docs/sql/industrializados_no_motor.sql`:

```sql
ALTER TABLE alimentos_industrializados ADD COLUMN tipo_prato_id INTEGER REFERENCES tipos_preparacoes(id);
ALTER TABLE alimentos_industrializados ADD COLUMN cor_predominante TEXT;
ALTER TABLE alimentos_industrializados ADD COLUMN textura TEXT;
ALTER TABLE alimentos_industrializados ADD COLUMN consistencia TEXT;
ALTER TABLE alimentos_industrializados ADD COLUMN temperatura_servimento TEXT;
ALTER TABLE alimentos_industrializados ADD COLUMN porcao_padrao_g DECIMAL(8,2);
-- porcao_padrao_g: gramas da porção do rótulo, preenchida manualmente (sem default)
CREATE INDEX idx_alimentos_industrializados_tipo_prato
    ON alimentos_industrializados(tipo_prato_id);
```

Justificativas:

- **`tipo_prato_id`** — necessário para o encaixe em `regras_composicao` (qtd min/max por refeição) e
  `regras_variedade`. Classificação manual no cadastro do produto, nos tipos **existentes** (ex.:
  biscoito → SD, iogurte → DP, suco de caixinha → BE). Não criar tipo novo ("IN"): as regras de
  composição são declaradas por tipo — tipo novo nasceria sem regras e ficaria de fora.
- **Sensoriais** (`cor_predominante`, `textura`, `consistencia`, `temperatura_servimento`) — mesmas
  colunas de `pratos`. Podem ser obtidas por classificação no cadastro (como Bruno fez em `pratos`).
  Permitem que `regras_sensoriais_gerais` e `regras_elegibilidade_dieta` operem sobre o produto.
- **`porcao_padrao_g`** — **gramas da porção declarada no rótulo** (ex.: 30g para "1 biscoito (30g)"),
  preenchimento **manual e obrigatório** no cadastro (Bruno informa). **Sem default** — produto sem
  `porcao_padrao_g` não entra no motor. Os nutrientes usados pelo modelo são os **da porção do
  rótulo** (campos base da tabela, seção 3.2), não os de 100g: 1 unidade no cardápio = 1 porção do
  rótulo.

### 3.2 Normalização no carregador

Ao carregar com `incluir_industrializados=True`, cada produto ativo vira um dicionário **no mesmo
formato de `pratos`**. **Os nutrientes são os declarados no rótulo para a porção** (campos base da
tabela `alimentos_industrializados` — não a view 100g; o motor conta 1 unidade = 1 porção do rótulo):

| Campo do prato | Fonte (tabela base, porção do rótulo) |
|---|---|
| `energia_kcal` | `energia_kcal` |
| `carboidrato_g` | `carboidratos_g` |
| `proteina_g` | `proteinas_g` |
| `lipidios_g` | `gorduras_totais_g` |
| `fibra_alimentar_g` | `fibras_g` |
| `sodio_mg` | `sodio_mg` |
| `potassio_mg` | **NULL** (não consta no rótulo) |

A view `vw_alimentos_industrializados_100g` e o mapeamento `COLUNAS_INDUSTRIALIZADOS` continuam
existentes para outros usos (busca, comparação) — o motor passa a ler os valores da porção direto.

**Filtros de entrada** (só entram no motor produtos com): `desativado = 0`, `tipo_prato_id`
preenchido, `porcao_padrao_g` preenchido e `energia_kcal IS NOT NULL` — o restante é tratado pela
política NULL (seção 3.3).

- **Colisão de IDs**: `pratos.id` e `alimentos_industrializados.id` são ambas autoincrement (as duas
  começam em 1) → colidiriam na mesma variável `X[id][r][d]` do PuLP. Cada produto entra com
  **`id_modelo = -id_real`** (ex.: produto id 3 → -3). Como `pratos.id` é sempre ≥ 1, nunca colide;
  é reversível (`id_real = -id_modelo`). O dict normalizado ganha `origem: 'industrializado'`
  (pratos ficam sem o campo), e um mapa auxiliar `origem_industrializado = {-id_real: {id_real,
  nome, marca}}` alimenta exibição e relatórios. O `resolver_e_extrair` usa `p['nome']` direto do
  dict e `p['id']` só como chave de variável — nenhuma outra parte do modelo precisa mudar.
- **Açúcares** (totais/adicionados) existem na tabela mas **não entram** no motor nesta fase — o motor
  não tem restrição de açúcar (ficam disponíveis para uso futuro).

### 3.3 Política de NULL (formalização da seção 10 do spec de rótulo)

1. **Nutriente restrito na dieta**: para cada restrição nutricional ativa da dieta (min ou max
   definido em `restricoes_nutricionais_dieta`), o industrializado com **NULL** nesse nutriente é
   **excluído do problema** e listado em `excluidos_null` no resultado (visível no relatório).
   Consequência prática: dietas com restrição de potássio **excluem todos** os industrializados
   (potássio nunca vem do rótulo) — comportamento correto e seguro: não se infere dado ausente.
2. **Atributo de elegibilidade NULL** (`regras_elegibilidade_dieta` sobre cor/textura/consistência/
   temperatura): produto com atributo NULL **não é elegível** quando a dieta tem regra sobre aquele
   atributo (conservador — elegibilidade é restrição clínica; sem o dado, não se garante).
3. **Sensoriais NULL sem regra ativa**: sem efeito — o produto participa normalmente.

### 3.4 Integração no código (`api/otimizacao.py`)

1. `carregar_dados_otimizacao(dieta_nome, incluir_industrializados=True)` — quando ativo:
   `pratos = pratos + industrializados_normalizados` (após filtro NULL da seção 3.3);
2. Endpoint `executar_otimizacao()`: ler `incluir_industrializados` do JSON (default **True** para o
   teste; aceitar `false` explícito) e repassar ao carregador;
3. `resolver_e_extrair()`: nome de exibição com marca para ids negativos; incluir
   `excluidos_null` no payload;
4. **Correção adjacente recomendada (bug latente)**: o endpoint lê `objetivo` do request mas não o
   repassa a `criar_modelo_otimizacao` (linha 466 chama sem `objetivo=`) — hoje só funciona porque o
   default do modelo é `max_energia`, que coincide com o default do request. Corrigir no mesmo
   commit para o teste de "maximizar energia" ser explícito.
5. `criar_modelo_otimizacao()`: adicionar a restrição do teto de industrializados/dia (seção 3.5).

### 3.5 Teto de industrializados por dia (20/08/2026)

**Motivação.** O motor otimiza nutrientes dentro das faixas da dieta — ele não tem noção de
"saudável". Com industrializados no modelo e objetivo `max_energia`, produtos densos em kcal
(ultraprocessados) são atraentes e podem ocupar slots obrigatórios (ex.: salgadinho como SD no
almoço) sem violar regra alguma, desde que as faixas da dieta permitam (a LIVRE hoje só limita
energia 1000–2500 kcal e proteína 50–100 g, sem sódio/gordura). Para responder à pergunta do
leigo ("o sistema pode oferecer um pacote de salgadinho no dia?"), entra uma regra explícita de
quantidade.

**Modelagem.** Constante `MAX_INDUSTRIALIZADOS_DIA` (default **2**) no `api/otimizacao.py` + uma
restrição por dia:

```
Σ_{p ∈ industrializados} Σ_{r} X[p][r][d] ≤ MAX_INDUSTRIALIZADOS_DIA   ∀ d
```

- `industrializados` = pratos com `origem == 'industrializado'` (flag prevista na seção 3.2)
  **após** o filtro da política NULL (seção 3.3) — só contam produtos que entraram no problema.
- Não conflita com `Unico_Dia` (≤ 1 refeição/dia por prato) nem com `MaxPratos_Dia` (≤ 18/dia):
  é um corte adicional sobre o total diário. Nome da restrição: `MaxInd_Dia{d}`.
- `MAX_INDUSTRIALIZADOS_DIA = 0` força zero industrializados por dia (equivale a desligar a
  inclusão via restrição, sem mudar o carregador) — útil para dieta restritiva sem nova flag.

**Implementação.** No `criar_modelo_otimizacao`, junto às demais restrições por dia:
`ids_ind = [p['id'] for p in dados['pratos'] if p.get('origem') == 'industrializado']`; se
`ids_ind` não vazio, adicionar a restrição `Σ X[pid][r][d] ≤ MAX_INDUSTRIALIZADOS_DIA`.

**Relatório.** `resolver_e_extrair` expõe `industrializados_por_dia` (contagem por dia) nas
métricas — o E2E confere o teto no próprio payload, sem consultar o banco.

## 4. Fora de escopo (fase 2, se desejado)

- **Salvar cardápio com industrializados**: `cardapio_refeicoes.prato_id` é FK de `pratos(id)` — o
  resultado da otimização com industrializados **não deve ser salvo** nesta fase. A tela
  `/otimizacao` (que só exibe/exporta) funciona; o módulo de planos (`api/plano.py`, que persiste)
  continua sem industrializados. Fase 2: coluna de origem alternativa em `cardapio_refeicoes`.
- Restrições de açúcar/alérgenos no motor.
- Lista de compras considerando industrializados (composição não se aplica — produto entra como item
  comprado).

## 5. Plano de validação (valores conferíveis na mão)

1. **Carga**: `carregar_dados_otimizacao('LIVRE', incluir_industrializados=True)` — conferir
   contagem, formato dos dicionários e ids negativos (SELECTs read-only, sem gravar).
2. **Entrada no cardápio**: dieta LIVRE, 1 dia, `max_energia`, flag ON vs OFF — com ON o resultado
   deve ser ≥ energia de OFF (mais opções disponíveis) e pode listar industrializados com `(marca)`.
3. **Filtro NULL**: dieta com restrição de sódio + produto sem `sodio_mg_100g` → excluído e
   presente em `excluidos_null` (caso da seção 10 do spec, linha 393).
4. **E2E do Bruno**: rodar `/otimizacao` com flag, conferir que o relatório mostra origem dos itens.
5. **Teto de industrializados/dia**: LIVRE, flag ON, `MAX_INDUSTRIALIZADOS_DIA=1` num teste →
   conferir no payload `industrializados_por_dia` que nenhum dia passa de 1; com `0`, nenhum dia
   tem industrializado.

## 6. Decisões do Bruno (16/08/2026)

1. **Classificação `tipo_prato_id`** — **manual por produto**, nos tipos existentes;
2. **`porcao_padrao_g`** — **gramas da porção do rótulo, informada manualmente** (sem default, sem
   100g — ver seções 3.1/3.2);
3. **Política NULL** (excluir + reportar — seção 3.3) — ok;
4. **Fase 1 sem salvar cardápio com industrializados** — ok;
5. **Flag `incluir_industrializados` na tela de otimização (`/otimizacao`)** — ok, default marcada.
6. **Teto de industrializados por dia** — ok (20/08/2026); default `MAX_INDUSTRIALIZADOS_DIA = 2`
   (constante no `api/otimizacao.py`), valor ajustável pelo Bruno.
