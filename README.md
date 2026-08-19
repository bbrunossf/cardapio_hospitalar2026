# Cardápio Hospitalar (NutriClin)

Sistema web de **planejamento nutricional hospitalar**: catálogo de pratos e
ingredientes, regras de dietas, geração de cardápios por **otimização
matemática (PuLP/CBC)**, planos nutricionais **por paciente** (cálculo local
determinístico), cadastro de alimentos por **rótulo/código de barras** e
ferramentas clínicas ("Posso Comer?", busca de alimentos semelhantes).

A visão de produto original está em [`inicial.md`](inicial.md).

## Stack

- **Flask 3** + Flask-SQLAlchemy + Flask-Admin (Bootstrap 4) + Flask-Login
- **SQLite** (`cardapio_hospitalar.db`) — decisão de manter SQLite em 16/08/2026
- **PuLP/CBC** — otimização de cardápio (timeout 180s, gap 10%)
- **d3.js** local (`static/vendor/`) — simulador de estratégia
- **ChromaDB 1.5.9** — embeddings semânticos de ingredientes (1536d,
  OpenAI text-embedding-3-small)
- **API isolada** `api_posso_comer` (porta 5010, GPT-4o-mini visão) — interpretação
  de foto/descrição de alimentos (opcional; modo FAKE sem chave)
- Identidade visual: NHS Blue/paleta Blues, IBM Plex Sans, acessível a daltônicos
  (tokens em [`DESIGN.md`](DESIGN.md))

## Funcionalidades

### Catálogo e regras (Flask-Admin)
- CRUD de ingredientes, pratos, composição de pratos, dietas, tipos de
  preparação/refeição e alimentos industrializados (com versionamento)
- Regras do motor: composição de refeições, elegibilidade por dieta,
  restrições nutricionais, regras sensoriais (ex.: bloquear pratos quentes na
  colação), variedade (frequência máxima de repetição)
- Consultas prontas: nutrientes por prato (`vw_pratos_nutricional`) e
  alimentos 100g

### Ficha Técnica (`/composicao-view`)
- Composição de pratos com edição inline de quantidades (gramas por porção)
- Modo de preparo em passos e tempo de produção
- Nutrientes e massa calculados dinamicamente pela view

### Otimização de Cardápio (`/otimizacao`)
- Gera cardápio diário respeitando dieta, composição por refeição,
  elegibilidade e regras sensoriais (`sem_quentes`)
- Objetivos: `max_energia` (default) e `target` (meta kcal do plano —
  minimiza o desvio absoluto diário)
- Overrides por plano: energia meta ±10%, macros ±15%
- Histórico versionado do motor (v1→v2→v3):
  [`docs/motor_otimizacao/`](docs/motor_otimizacao/README.md)

### Cadastro por Rótulo (`/rotulo`)
- Leitura de código de barras (OpenFoodFacts), OCR (Tesseract) e visão LLM
- Rastreabilidade por versão (`alimento_versoes`)

### Pacientes e Planos Nutricionais
- Cadastro de pacientes (antropometria, objetivo, nível de atividade)
- Plano por paciente: TMB/GET/meta/macros via **cálculo local determinístico**
  (`calculo_nutricional/`, stdlib puro) — WolframAlpha opcional via
  `FONTE_CALCULO=wolfram` (benchmark)
- Cardápio dimensionado por plano, salvo e **versionado**
  (cardapios_salvos → dias → refeições)
- Simulador interativo d3 (`/planos/<id>/simulador`): arrastar
  ingestão/peso-alvo com projeção ao vivo (7700 kcal/kg)

### Posso Comer? (`/posso-comer`)
- Consequências de ingerir alimento fora do cardápio do paciente: semáforo
  verde/amarelo/vermelho por acréscimo de kcal e sódio vs. total do dia
- Alternativas em camadas: vizinhos semânticos (chroma) + mesma categoria com
  menos kcal + fallback determinístico

### Alimentos Semelhantes (`/busca-semelhantes`)
- Busca semântica por nome/descrição sobre os 323 ingredientes indexados

### Autenticação e Permissões (17/08/2026)
- Login com e-mail/senha (hash scrypt via Werkzeug), sessão Flask-Login
- **Papéis**: `admin` (tudo), `nutricionista` (CRUD operacional; Regras
  globais e Usuários só leitura/oculto), `leitura` (somente GET)
- **Escopo por dono**: cada nutricionista vê/edita apenas os próprios
  pacientes (coluna `pacientes.criado_por`) — equivalente a RLS na aplicação
  (SQLite não tem RLS nativo; planos/cardápios/restrições escopam via JOIN)
- Detalhes: [`docs/autenticacao.md`](docs/autenticacao.md)

### Regras por Paciente (Fase 1 — 17/08/2026)
- Faixas nutricionais, elegibilidade, variedade e exclusões **por paciente**
  (`/pacientes/<id>/planos`, 4 abas) — precedência no motor:
  **paciente > plano > dieta**
- Fases 2-3 (elegibilidade/variedade no motor, refeições do paciente) planejadas
- Detalhes: [`docs/personalizacao_por_paciente.md`](docs/personalizacao_por_paciente.md)

### Monitor de uso
- Acessos anônimos por rota/dia em SQLite separado (`usage.db`), painel em
  `/api/usage` protegido por token (`USAGE_ADMIN_TOKEN`)

## Como rodar

```bash
cd novo_cardapio

# 1. Dependências (venv sem pip: usar uv)
uv pip install --python ~/.venv/bin/python -r requirements.txt

# 2. Ambiente
cp .env.example .env        # preencher SECRET_KEY, FONTE_CALCULO, etc.
python -c "import secrets; print(secrets.token_hex(32))"   # gerar SECRET_KEY

# 3. Aplicar DDLs pendentes (executados manualmente — ver docs/sql/)
sqlite3 cardapio_hospitalar.db < docs/sql/autenticacao.sql

# 4. Criar usuário inicial (senha via prompt)
flask --app app2.py criar-usuario --email admin@exemplo.com --nome Admin --papel admin

# 5. Rodar (dev)
flask --app app2.py run --host 0.0.0.0 --port 5000
```

> Banco e `chroma_db/` **não são versionados** (`.gitignore`). `FONTE_CALCULO=local`
> é o default — determinístico, sem rede, sem quota.

## Rotas principais

| Rota | Função |
|---|---|
| `/admin` | Flask-Admin (catálogo, regras, consultas, usuários) |
| `/login` `/logout` | Autenticação |
| `/composicao-view` | Ficha Técnica (composição + modo de preparo) |
| `/otimizacao` | Otimização de cardápio (PuLP) |
| `/rotulo` | Cadastro por rótulo/barcode |
| `/pacientes` | Lista de pacientes (por dono) |
| `/pacientes/<id>/planos`, `/planos/<id>`, `/planos/<id>/simulador` | Planos e simulador |
| `/cardapios/<id>` | Visualização do cardápio dimensionado |
| `/posso-comer` | "Posso Comer?" (semáforo + alternativas) |
| `/busca-semelhantes` | Busca semântica de alimentos |
| `/api/usage` | Painel do monitor de uso (token) |

APIs REST: `/api/pacientes*`, `/api/planos*`, `/api/cardapios*`,
`/api/posso-comer/*`, `/api/busca-semelhantes`, `/api/pratos*`,
`/api/composicao*`, `/api/ingredientes`, `/api/otimizacao/executar`.

## Estrutura

```
app2.py                  # create_app: blueprints, auth (before_request), CLI
config.py / extensions.py
models.py                # catálogo + regras + passos de preparo
models_paciente.py       # pacientes (criado_por = dono)
models_plano.py          # planos, cardápios, restrições
models_personalizacao.py # regras por paciente (4 tabelas)
models_rotulo.py         # alimentos industrializados
models_auth.py           # usuarios (Flask-Login)
authz.py                 # papéis + escopo por dono (paciente_acessivel)
admin_views.py           # Flask-Admin (BaseModelView com papel/escopo)
dashboard.py             # home do admin
motor_log.py             # log do motor (JSONL; MOTOR_DEBUG p/ artefatos PuLP)
api/                     # blueprints: auth, paciente, plano, regras_paciente,
                         #   posso_comer, busca_semelhantes, composicao,
                         #   otimizacao, rotulo
calculo_nutricional/     # TMB/GET/meta/macros/antropometria (stdlib puro)
wolfram_client.py        # cliente WolframAlpha (legado/benchmark)
usage_monitor.py         # monitor de uso por rota
scripts/                 # embeddings, escopo auth, importação OFF (off_utils)
legado/                  # arquivos antigos fora do app (app antigo, diagnósticos)
templates/ static/       # páginas, JS (d3 local), CSS (paleta Blues)
docs/                    # planos e DDLs por feature (docs/sql/)
```

## Documentação de decisões (`docs/`)

- `autenticacao.md` — papéis + escopo por dono (17/08/2026, implementado)
- `personalizacao_por_paciente.md` — regras por paciente (Fase 1 implementada
  17/08/2026; Fases 2-3 planejadas)
- `industrializados_no_motor.md` — industrializados no motor (aprovado; DDL
  executado 18/08, código pendente)
- `importacao_openfoodfacts.md` — importação do dump Open Food Facts
- `busca_semelhantes.md` — busca semântica de alimentos (15/08/2026, implementado)
- `posso_comer.md` — "Posso Comer?" (15/08/2026, implementado)
- `ficha_tecnica.md` — ficha técnica das preparações (implementado)
- `plano_calculos_locais.md`, `analise_integracao_wolfram.md` — cálculos locais
  determinísticos vs. Wolfram (benchmark)
- `objetivo_generico.md` — função objetivo genérica max/min de nutrientes
  (proposta 18/08/2026, aguardando aprovação)
- `motor_otimizacao/` — histórico versionado do motor (v1/v2 arquivadas,
  v3 = `api/otimizacao.py`) + pendências
- `especificacao_modulo_rotulo.md` — spec do cadastro por rótulo nutricional
  (DDL base + roteiro; referencia da seção 9 do motor)
- `registro_alimentar_48h.md` — registro alimentar 48h (planejamento 19/08/2026)
- DDLs prontos para execução manual em `docs/sql/`

## Workflow git

- Branch atual: `main` (feature/calculos-locais mergeada em 16/08/2026)
- Push/merge são **manuais** (feitos pelo Bruno); o servidor não tem auth GitHub
