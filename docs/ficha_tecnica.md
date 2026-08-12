# Plano — Ficha Técnica das Preparações (novo_cardapio)

> **Data:** 11/08/2026 (rev. 3 — custo fora; modo de preparo em tabela separada; rendimento fora)
> **Branch:** `main` (a definir — sugiro `feature/ficha-tecnica`)
> **Motivação:** apresentar e editar numa única página a composição das preparações
> (ingredientes + quantidades), modo de preparo (em passos) e tempo de produção — de
> forma profissional. A ficha também é a fundação de dados para o próximo módulo de
> **lista de compras** (cardápio dimensionado × composição × nº de porções).

---

## 1. Decisão

Evoluir o módulo de composição existente (`/composicao-view` + `api/composicao.py`)
para virar a **Ficha Técnica das Preparações**, em vez de criar uma página paralela.
Reaproveita 100% do padrão já validado de "buscar prato → ver composição → buscar
ingrediente e adicionar", acrescentando os blocos que faltam: modo de preparo (em
tabela separada, com passos numerados), tempo de produção e resumo nutricional por
porção.

**Decisões do Bruno (11/08/2026):**
- **Custo: FORA desta fase.** As colunas de custo existentes ficam intocadas; quando
  a lista de compras precisar de custo, entra como fase própria (preencher
  `ingredientes.custo_por_100g`).
- **Modo de preparo: tabela separada** (`passos_preparo`), não coluna em `pratos`.
- **Rendimento: FORA por enquanto.** As quantidades de `prato_composicao` são POR
  PORÇÃO; a decisão de como modelar lote/rendimento fica para o módulo de compras
  (onde a pergunta real é "quantas porções produzir").

**Fora de escopo agora (Fase 2):** módulo de lista de compras — apenas desenhado na §8.

## 2. O que já existe (inventário validado em 11/08/2026)

- **Schema:**
  - `pratos` — `porcao_padrao_g` (preenchido nos 405 ativos), `custo_total` (coluna
    órfã, 0 preenchidos — intocada), `tempo_producao_min` (0 preenchidos), **sem
    coluna de modo de preparo**
  - `prato_composicao` — `quantidade_g` (724 linhas ativas), soft delete
  - `ingredientes` — nutrientes por 100g na forma final; `custo_por_100g` existe
    mas 0/323 preenchidos (fora de escopo)
  - `vw_pratos_nutricional` — calcula dinamicamente nutrientes + massa por prato
    (base 100g × qtd), inclui `tempo_producao_min`
- **API `api/composicao.py`** (8 rotas): listar pratos, detalhe, atualizar porção,
  atualizar qtd, listar ingredientes, adicionar ingrediente, remover ingrediente,
  página `/composicao-view`
- **Frontend `templates/composicao.html`:** dois painéis (lista de pratos com busca
  à esquerda; detalhe à direita), tabela de composição com edição inline de
  quantidade, bloco "Adicionar Ingrediente" com busca + chips, badge ok/dif
  (Σqtd vs porção)

## 3. Decisões de projeto

1. **`quantidade_g` = gramas POR PORÇÃO padrão.** É assim que o app já trata
   (badge "ok" = Σqtd ≈ `porcao_padrao_g`; `vw_pratos_nutricional` e o PuLP usam a
   composição como 1 porção). A ficha é sempre "por porção"; o dimensionamento para
   N porções/pacientes fica para o módulo de compras. **Não mudar essa semântica** —
   quebraria badge, view e otimizador.
2. **Modo de preparo em tabela própria, 1 passo por linha.** Modelo de ficha
   clássica: passos numerados (ordem), texto livre, soft delete. O `pratos` não
   ganha coluna de texto longo.
3. **Custo não é exibido nem editado nesta fase** (decisão do Bruno). A view já
   calcula, mas a ficha não mostra — evita exibir "—" em tudo sem dado.
4. **Schema novo é executado manualmente pelo Bruno** (regra 1 do projeto). Nada de
   migração automática.
5. **Paleta visual:** manter `identidade_paginas.css` (azul monocromático,
   daltônico-safe) — sem cores novas.

## 4. Mudança de schema (executada pelo Bruno, manual)

```sql
-- Modo de preparo: um passo por linha, ordenado
CREATE TABLE passos_preparo (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    prato_id    INTEGER NOT NULL REFERENCES pratos(id) ON DELETE CASCADE,
    ordem       INTEGER NOT NULL DEFAULT 1 CHECK(ordem >= 1),
    descricao   TEXT NOT NULL,
    criado_em   DATETIME DEFAULT CURRENT_TIMESTAMP,
    editado_em  DATETIME DEFAULT CURRENT_TIMESTAMP,
    desativado  BOOLEAN DEFAULT 0
);
CREATE INDEX ix_passos_preparo_prato ON passos_preparo(prato_id);
```

- Arquivo executável: `docs/sql/ficha_tecnica.sql`
- Modelo SQLAlchemy: classe `PassoPreparo` + `Prato.passos_preparo` (relationship,
  cascade delete-orphan para os não desativados).

## 5. Backend — `api/composicao.py` (estender, sem blueprint novo)

### 5.1 Estender `GET /api/pratos/<id>/composicao` (backward compatible)

O mesmo endpoint passa a retornar o payload completo da ficha:

```json
{
  "prato": {
    "id": 1, "nome": "...", "tipo": "...",
    "consistencia": "...", "textura": "...", "temperatura_servimento": "...",
    "porcao_padrao_g": 120.0,
    "tempo_producao_min": 45
  },
  "ingredientes": [
    { "ingrediente_id": 3, "ingrediente": "Arroz", "quantidade_g": 80.0 }
  ],
  "modo_preparo": [
    { "id": 1, "ordem": 1, "descricao": "Lavar o arroz..." },
    { "id": 2, "ordem": 2, "descricao": "Cozinhar..." }
  ],
  "nutrientes": { "energia_kcal": 145.2, "proteina_g": 3.1, "carboidrato_g": 31.9,
                  "lipidios_g": 0.4, "fibra_alimentar_g": 0.8, "sodio_mg": 2.1 },
  "massa_calculada": 120.0, "diferenca": 0.0, "ok": true
}
```

Implementação:
- Adicionar à query do prato: `p.tempo_producao_min`
- Nova query: `SELECT id, ordem, descricao FROM passos_preparo WHERE prato_id = :pid AND desativado = 0 ORDER BY ordem, id`
- Novo JOIN com `vw_pratos_nutricional` para `nutrientes` (read-only)
- Campos de custo **não** entram no payload

### 5.2 CRUD de passos (espelha o padrão da composição)

- `POST /api/pratos/<id>/modo-preparo` — body `{ "descricao": "..." }`; cria com
  `ordem = COALESCE(MAX(ordem), 0) + 1` dos ativos; retorna o passo criado (201)
- `PATCH /api/modo-preparo/<passo_id>` — body `{ "descricao"?, "ordem"? }`
  (valida: descricao não vazia; ordem ≥ 1 inteiro)
- `DELETE /api/modo-preparo/<passo_id>` — soft delete (`desativado = 1`)
- Reordenação explícita fica para depois (v1 ordena por `ordem`; inserção no fim)

### 5.3 Novo `PATCH /api/pratos/<id>/preparo`

```json
{ "tempo_producao_min": 45 }
```

- Campo opcional; `null` limpa; validação: inteiro ≥ 0
- `UPDATE pratos SET ... editado_em = CURRENT_TIMESTAMP`

## 6. Frontend — `templates/composicao.html` (+ print CSS)

Blocos, preservando o que existe:

1. **Header** (existe): nome + tipo + badges consistência/textura/temperatura
2. **Cards de info** (estender o existente "porção"):
   - Porção padrão (g) — editável (existe)
   - Tempo de preparo (min) — novo, editável (PATCH 5.3)
3. **Tabela de composição** (existe, sem mudanças): ingrediente, quantidade (g),
   ações salvar/remover; footer massa total + status ok/dif. **Sem coluna de custo.**
4. **Adicionar ingrediente** (existe, intocado): busca + chips + quantidade
5. **Modo de preparo** (novo): lista de passos numerados com edição inline —
   cada passo tem input de texto + botões salvar/remover; botão "+ Adicionar passo"
   (endpoints 5.2). Ordem = numeração exibida (1., 2., ...).
6. **Resumo nutricional por porção** (novo, read-only): kcal, PTN, CHO, LIP, fibra,
   sódio, potássio (do payload 5.1)
7. **Print stylesheet** (novo, pequeno): `@media print` esconde controles de edição e
   formata a ficha para impressão (título, blocos, tabela, passos numerados)

## 7. Validação (regras de trabalho do Bruno)

- **Agente:** valida com app-context em modo leitura (SELECTs) e contas na mão —
  ex.: prato com 2 ingredientes, somar nutrientes por porção no papel e comparar
  com o payload.
- **Bruno (E2E, grava dados):** PATCH de preparo, CRUD de passos, edição de qtd,
  adicionar/remover ingrediente, impressão da ficha.

## 8. Fase 2 — Lista de compras (desenho, NÃO implementa agora)

- **Fonte:** cardápio dimensionado salvo (`cardapios_salvos` → `cardapio_dias` →
  `cardapio_refeicoes`: `prato_id` + `porcao_g`) × composição (`quantidade_g` por
  porção) × nº de pacientes/porções.
- **Fórmula:** ingrediente necessário = Σ_refeições (`quantidade_g` × fator_escala);
  fator_escala = porções servidas (`porcao_g`/`porcao_padrao_g` × pacientes) —
  a definir com o Bruno na fase.
- **Agregação:** por `ingrediente_id` → lista de compras com quantidade total.
- **Rendimento/lote:** decisão de modelagem fica para esta fase (quantidades por
  porção × N porções já resolvem a massa; lote/rendimento só se a cozinha precisar).
- **Custo na lista:** fica para fase própria — exige preencher `custo_por_100g`
  (decisão: custo fora desta fase).

## 9. Tarefas (ordem de execução)

1. **[Bruno]** Executar o `CREATE TABLE passos_preparo` (§4 — `docs/sql/ficha_tecnica.sql`)
2. Modelo SQLAlchemy: `PassoPreparo` + relationship no `Prato`
3. Estender `GET /api/pratos/<id>/composicao` (§5.1)
4. CRUD de passos (§5.2)
5. `PATCH /api/pratos/<id>/preparo` (§5.3)
6. Frontend: card de tempo + bloco modo de preparo (passos) + resumo nutricional +
   print (§6)
7. Renomear link no admin (`admin_views.py`): "Ajustar Composição" → "Ficha Técnica"
8. Validação: agente (leitura + contas na mão) → Bruno (E2E)
