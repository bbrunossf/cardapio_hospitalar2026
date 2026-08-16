# Módulo "Posso Comer?" — plano (15/08/2026)

## Objetivo

Atendimento personalizado de pacientes: mostrar as **consequências de ingerir um
alimento fora do cardápio estabelecido**, com comparativos visuais (semáforo,
texto formatado, imagem, gráfico de acréscimo de kcal). O paciente informa o nome
do alimento (ou envia foto) e o sistema responde quanto aquele alimento acrescenta
ao total diário que ele deve seguir.

## Decisões do Bruno (15/08/2026)

- **Referência de comparação:** total de nutrientes **calculado por dia** para o
  paciente seguir (o cardápio estabelecido) — a resposta mostra o **acréscimo**
  que o alimento fora do cardápio representa
- **Nutrientes avaliados:** só **kcal e sódio** (não a tabela completa de macros)
- **LLM:** dedicado, **com capacidade de visão**, mais caro, **exclusivo para
  esta função**, isolado em uma **API separada** (não acoplado ao app principal)
- **Alimento fora do banco:** o LLM **estima** kcal/sódio e a resposta é marcada
  como **"estimado"** de forma visível
- **UI:** página com **campo de texto** (não é um chat), **estrutura fixa com
  barra de rolagem vertical**, resultado visual e chamativo: semáforo, texto
  formatado, imagem do alimento e gráfico do acréscimo de kcal
- **Cores:** verde/amarelo/vermelho **permitidos** neste item (exceção explícita
  à regra de daltonismo — o público é o paciente)

## Fluxo (texto e foto)

```
entrada: nome do alimento (+ porção opcional) ou foto
   → API LLM (visão/texto) interpreta → nome_sugerido (e descrição, se foto)
   → busca no banco (ingredientes + pratos ativos) por nome

Caso A — achou no banco:
   → pede/usa a porção (g)
   → calcula kcal e sódio DA PORÇÃO (determinístico, dados do cadastro)
   → compara com o total do dia do cardápio estabelecido
   → resposta: semáforo + acréscimo % + gráfico + texto de consequência

Caso B — não achou:
   → mostra o alimento sugerido pelo LLM ("você quis dizer X?") p/ confirmar
   → se confirmado sem match, pede descrição + porção (campos da página)
   → LLM estima kcal e sódio por 100g (badge "ESTIMADO" na resposta)
   → compara com o total do dia
```

A página **não é um chat**: entrada em campos fixos (nome + porção + upload de
foto), resultado em área de scroll vertical.

## Arquitetura

```
┌───────────────────────────┐        ┌──────────────────────────────┐
│ App principal (Flask)     │  HTTP  │ API separada de interpretação │
│ novo_cardapio (porta 5000)│───────▶│ (ex.: porta 5010)            │
│                           │        │ modelo LLM com visão          │
│ • busca no banco          │        │ • texto → nome_sugerido       │
│ • cálculo determinístico  │◀───────│ • foto → descrição + nome      │
│   (kcal/sódio da porção)  │  JSON  │ • estimativa kcal/sódio/100g  │
│ • comparativo c/ o dia    │        │   (quando fora do banco)      │
│ • UI semáforo/gráfico     │        └──────────────────────────────┘
└───────────────────────────┘
```

- **App principal:** zero LLM embutido. Cálculo 100% local/determinístico
  (mesma filosofia do `calculo_nutricional`). Consulta ao banco e comparativos.
- **API separada (`api-posso-comer` / interpretador):** único lugar com chave do
  modelo de visão; isola custo (modelo caro, exclusivo) e permite trocar provedor
  sem tocar no app. Recebe `{texto? | imagem_base64 + mime}` e devolve
  `{nome_sugerido, descricao?, kcal_100g?, sodio_mg_100g?, estimado, confianca}`.
  Endpoints: `POST /interpretar` (texto ou imagem). Timeout/retry definidos no
  contrato; indisponibilidade → app responde erro amigável ("interpretação
  indisponível no momento") sem quebrar a página.
- **Modelo de visão:** a escolher (recomendação: Gemini 2.0 Flash ou GPT-4o-mini —
  bom custo/benefício p/ descrição de alimento; a API separada isola a troca).

## Referência do dia ("cardápio estabelecido")

Fonte primária: **cardápio salvo ativo do paciente** (`cardapios_salvos` →
`cardapio_dias` → `cardapio_refeicoes`):

- **kcal do dia:** `cardapio_dias.energia_kcal_total` (já calculado)
- **sódio do dia:** soma dos pratos do dia via `vw_pratos_nutricional`,
  corrigindo pela porção da refeição:
  `Σ (vw.sodio_mg × cr.porcao_g / p.porcao_padrao_g)`

Fallbacks (em ordem):
1. Cardápio salvo ativo do paciente (dia atual do ciclo — `data_inicio`..`data_fim`
   ou `dia_numero` por data)
2. Sem cardápio → metas do plano ativo (`planos_nutricionais.meta_kcal`; sódio sem
   meta → mostra só kcal com aviso)
3. Sem plano/cardápio → resposta sem semáforo, só valores do alimento + aviso
   "paciente sem cardápio estabelecido"

## Cálculo do alimento (determinístico)

- **Ingrediente:** `kcal = energia_kcal × porcao_g / 100` (idem sódio) — valores
  por 100g da tabela
- **Prato:** `kcal = vw_pratos_nutricional.energia_kcal × porcao_g / porcao_padrao_g`
  (a view é por porção padrão; corrige pela porção consumida)
- **Busca por nome:** normalizar (minúsculas, sem acentos) + `LIKE` em
  `ingredientes.nome` e `pratos.nome` (ativos). Múltiplos resultados → lista
  clicável na página. O `nome_sugerido` do LLM guia a busca; a busca em si é
  determinística
- **Estimativa (fora do banco):** `kcal_100g` e `sodio_mg_100g` vêm do LLM com
  base na descrição + porção; resposta marcada **"ESTIMADO"** (badge + aviso no
  texto)

## Semáforo (proposta de critérios — ajustável)

Base: **pior dos dois nutrientes** (kcal e sódio) considerando o acréscimo % sobre
o total do dia:

| Acréscimo sobre o dia | Semáforo | Mensagem |
|---|---|---|
| ≤ +10% | 🟢 Verde | Liberado — impacto pequeno no dia |
| +10% a +25% | 🟡 Amarelo | Consumir com moderação |
| > +25% | 🔴 Vermelho | Evitar — compromete o dia + alternativas |

Exemplo de texto de consequência (gerado deterministicamente, sem LLM):
> "Este alimento acrescenta **320 kcal (+16%)** e **480 mg de sódio (+9%)** ao seu
> dia de 2.000 kcal. Fica perto do limite — consuma com moderação."

Se vermelho: sugere **alternativas** do banco (top 3 pratos/ingredientes ativos com
kcal da porção menor que o alimento consultado — determinístico).

## UI (página fixa, scroll vertical)

`GET /posso-comer` — mesma identidade visual do app (porém semáforo
verde/amarelo/vermelho, autorizado):

1. **Topo (fixo):** paciente selecionado (regra UX: sempre por paciente) + resumo
   do cardápio do dia (kcal e sódio totais de referência)
2. **Entrada (fixa):** campo "nome do alimento" + campo "porção (g)" (opcional) +
   upload de foto + botão "Ver impacto"
3. **Resultado (scroll vertical):**
   - **Semáforo grande** (círculo/card colorido + rótulo: Liberado / Moderação /
     Evitar)
   - **Card do alimento:** nome; **imagem** (a foto enviada, se entrada por foto;
     sem foto → placeholder/ícone — banco não tem imagens de alimentos);
     badge **"ESTIMADO"** quando aplicável
   - **Tabela kcal/sódio** da porção (consumido hoje vs. + este alimento)
   - **Gráfico de acréscimo:** barras horizontais (CSS, sem lib) — "kcal do dia"
     vs. "kcal do dia + alimento", com % de aumento destacado
   - **Texto de consequência** formatado + alternativas (se vermelho)
4. Lista de resultados múltiplos (busca ambígua) → cards clicáveis

## Endpoints (app principal)

- `GET /posso-comer` — página (seleção de paciente primeiro)
- `GET /api/posso-comer/contexto/<paciente_id>` — totais do dia de referência:
  `{tem_cardapio, kcal_dia, sodio_mg_dia, fonte: 'cardapio'|'plano'|'nenhum'}`
- `POST /api/posso-comer/consultar` — body `{paciente_id, texto?, imagem?,
  porcao_g?}` → resposta:
  - `{encontrado, alimento: {id?, tipo: 'ingrediente'|'prato'|'estimado', nome,
    kcal_porcao, sodio_mg_porcao, estimado, imagem?}, contexto: {kcal_dia,
    sodio_mg_dia, fonte}, impacto: {kcal_pct, sodio_pct, semaforo, mensagem},
    alternativas: [...]}`
- Fluxo em 2 passos na própria página (não é chat): consultar → se `encontrado:
  false`, mostra o `nome_sugerido` p/ confirmar + campos de descrição/porção →
  segunda chamada com `modo: 'estimar'`

## DDL

**Nenhuma obrigatória na v1** (nada de novo é gravado). Opcional fase 2:
`posso_comer_consultas` (histórico/auditoria: paciente, entrada, alimento
encontrado/estimado, impacto, semáforo, timestamp) — DDL em `docs/sql/` se Bruno
quiser.

## Testes / validação

1. Valores conferíveis na mão: ex. banana 92 kcal/100g × 100g → 92 kcal; sódio
   análogo; comparar com `cardapio_dias.energia_kcal_total` e soma de sódio do dia
2. Contrato da API de interpretação testado isoladamente (texto e imagem; sem
   depender do app)
3. Casos: alimento no banco (ingrediente e prato), fora do banco (estimado),
   busca ambígua (lista), paciente sem cardápio/plano
4. E2E do Bruno no navegador (regra 1)

## Estado da implementação (15/08/2026)

**API de interpretação — implementada e em MODO REAL** em
`/home/plena/api_posso_comer/` (serviço Flask isolado, porta 5010, bind
127.0.0.1, GPT-4o-mini): `POST /interpretar` (texto/foto → nome_sugerido +
descricao), `POST /estimar` (descricao + porção → kcal/sódio por 100g e por
porção, `estimado: true`), `POST /embed` (texto → embedding 1536d,
text-embedding-3-small), `GET /health`. ✅ Chave OpenAI no `.env` (FAKE=0) —
validado em modo real.

**Módulo no app — implementado e validado (E2E headless chromium):**

- `api/posso_comer.py` (blueprint `posso_comer_bp`): página `/posso-comer`,
  `GET /api/posso-comer/contexto/<paciente_id>` (totais do dia: cardápio →
  plano → nenhum) e `POST /api/posso-comer/consultar` (modos: texto/imagem →
  busca; candidato escolhido; estimar). Registrado no `app2.py`; link
  "Posso Comer?" no menu Ferramentas (`admin_views.py`)
- `templates/posso_comer.html` + `static/js/posso_comer.js`: página fixa com
  scroll vertical — semáforo grande, card do alimento (imagem ou placeholder;
  badge ESTIMADO), tabela consumido vs. +alimento, gráfico de barras,
  mensagem e alternativas; lista de candidatos com "Nenhum desses"
- Busca por nome com regra estrita (todos os tokens); sem match → descrição/estimativa

**Alternativas híbridas (camadas) + banco vetorial:**

- Banco vetorial `chroma_db/` (coleção `ingredientes_embeddings`, 323
  embeddings, 1536 dims = OpenAI text-embedding-3-small, criado 04/08) — abre
  com **chromadb==1.5.9** (adicionado ao `requirements.txt`; instalado no
  `~/.venv` via `uv pip install`, pois o venv não tem pip)
- `_alternativas(alimento)` em camadas: (1) vizinhos semânticos no chroma
  (vetor do próprio id p/ ingrediente, ou `/embed` do nome/descrição p/ prato e
  estimado); (2) filtro MESMA categoria (`tipo_alimento`) + kcal menor;
  (3) qualquer vizinho com kcal menor; fallback determinístico (kcal 30–90%).
  Fallback silencioso se o chroma estiver indisponível
- Validado: bolo de chocolate 150g (estimado, vermelho) → Pudim de chocolate
  (119), Pudim Diet (76), Pudim de coco (117) — todos "produtos açucarados";
  azeite 100g (vermelho) → substitutos com menos kcal
- **Script versionado** `scripts/gerar_embeddings_alimentos.py`: recria a
  coleção a partir do banco relacional (text-embedding-3-small, upsert
  idempotente, espaço COSINE). Descrições em 3 modos: `--modo auto` (default:
  GPT-4o-mini com fallback por item p/ template se a chamada falhar), `llm`
  (só LLM) e `template` (determinístico, offline). Cache das descrições em
  `scripts/descricoes_llm_cache.json` (gitignorado; reutiliza entre execuções
  sem custo). Flags: `--recriar`, `--ids 1,48` (testes), `--somente-descricoes`,
  `--dry-run`, `--cache PATH`. ⚠️ Requer `OPENAI_API_KEY` no `.env` do
  novo_cardapio para os modos llm/auto (sem chave, auto cai p/ template com
  aviso). NÃO rodado em modo real (não sobrescreve o índice atual sem aval)

**Pendente:** E2E do Bruno no navegador real (regra 1) e commit da feature.

## Pendências / fase 2

- Histórico de consultas (`posso_comer_consultas`) — fase 2, opcional
- Modo LLM no script de embeddings (regenerar descrições ricas antes de recriar)
