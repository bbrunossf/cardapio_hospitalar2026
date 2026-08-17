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
- Gera cardápio diário respeitando dieta, regras sensoriais e de variedade
- Objetivos: maximizar energia, minimizar custo, target
- Overrides por plano: energia meta ±10%, macros ±15%

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
models_rotulo.py         # alimentos industrializados
models_auth.py           # usuarios (Flask-Login)
authz.py                 # papéis + escopo por dono (paciente_acessivel)
admin_views.py           # Flask-Admin (BaseModelView com papel/escopo)
dashboard.py             # home do admin
api/                     # blueprints: auth, paciente, plano, posso_comer,
                         #   busca_semelhantes, composicao, otimizacao, rotulo
calculo_nutricional/     # TMB/GET/meta/macros/antropometria (stdlib puro)
wolfram_client.py        # cliente WolframAlpha (legado/benchmark)
usage_monitor.py         # monitor de uso por rota
scripts/                 # gerar_embeddings_alimentos.py, aplicar_escopo_auth.py
templates/ static/       # páginas, JS (d3 local), CSS (paleta Blues)
docs/                    # planos e DDLs por feature (docs/sql/)
```

## Documentação de decisões (`docs/`)

- `autenticacao.md` — papéis + escopo por dono (17/08/2026)
- `personalizacao_por_paciente.md` — delta de restrições por paciente (proposto)
- `industrializados_no_motor.md` — alimentos industrializados no motor (aprovado)
- `posso_comer.md`, `ficha_tecnica.md`, `plano_calculos_locais.md`,
  `analise_integracao_wolfram.md`
- DDLs prontos para execução manual em `docs/sql/`

## Workflow git

- Branch atual: `main` (feature/calculos-locais mergeada em 16/08/2026)
- Push/merge são **manuais** (feitos pelo Bruno); o servidor não tem auth GitHub
