# Autenticação e Permissões por Papel + Dono

**Data:** 17/08/2026
**Status:** Plano proposto — aguardando aprovação do Bruno
**DDL:** `docs/sql/autenticacao.sql` (Bruno executa)

## Objetivo

Adicionar usuários e senha ao app, com controle de acesso **por papel** (role-based) **e por dono** (cada nutricionista só vê/edita os próprios pacientes), antes da implementação da personalização por paciente. Hoje o app não tem autenticação nenhuma e está público em `https://cardapio.nutriaxis.com.br` (túnel Cloudflare sem policy de Access) — qualquer pessoa com a URL acessa dados de pacientes.

## Decisões

1. **Permissão por papel + por dono.** Papel define *áreas* (admin/nutricionista/leitura); dono define *escopo*: nutricionista só acessa pacientes com `criado_por = id dela` (e tudo que deriva deles: planos, cardápios, restrições). Admin enxerga tudo.
2. **SQLite não tem RLS nativo** — o isolamento por dono é feito **na aplicação**: toda query de dado de paciente ganha `AND criado_por = <usuário>`. Coluna única de âncora em `pacientes.criado_por`; as tabelas filhas (planos, cardápios, restrições) são escopadas via JOIN pelo paciente. Se um dia migrar para PostgreSQL, a mesma coluna vira política RLS real.
3. **Flask-Login** como base de sessão (padrão, integra nativamente com Flask-Admin via `is_accessible`). Dependência nova: `flask-login` (puro Python, pequeno).
4. **Hash de senha** via `werkzeug.security` (scrypt — já é dependência do Flask, zero código novo de criptografia).
5. **Três papéis:** `admin`, `nutricionista`, `leitura`.
6. **Senha nunca versionada**: usuário inicial é criado via comando CLI (`flask --app app2.py criar-usuario`), não via INSERT no SQL.
7. **SECRET_KEY vai para o `.env`** (hoje está hardcoded no `config.py` — com login real, chave fixa = sessões forjáveis).
8. **Regras globais vs regras do paciente:** regras globais do motor (dietas, elegibilidade, sensoriais...) são config — admin. Regras do paciente (`restricoes_paciente` e o delta da personalização futura) são clínicas — nutricionista tem CRUD **dos próprios pacientes**.
9. **Transferência de paciente** entre nutricionistas = admin altera `criado_por` (UPDATE numa coluna, sem tocar tabelas filhas).

## Schema

### Nova tabela `usuarios`

```sql
CREATE TABLE usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    senha_hash TEXT NOT NULL,
    papel TEXT NOT NULL DEFAULT 'nutricionista'
        CHECK (papel IN ('admin','nutricionista','leitura')),
    desativado BOOLEAN NOT NULL DEFAULT 0,
    ultimo_login DATETIME,
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    editado_em DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_usuarios_papel ON usuarios (papel);
```

### ALTER em `pacientes`

```sql
ALTER TABLE pacientes ADD COLUMN criado_por INTEGER REFERENCES usuarios(id);
CREATE INDEX idx_pacientes_criado_por ON pacientes (criado_por);
```

- `criado_por` NULL é permitido (SQLite exige default NULL para FK em ADD COLUMN).
- **Pacientes existentes ficam sem dono (NULL)** — só o admin os vê até atribuir um nutricionista (reclassificar manualmente na tabela).
- Tabelas filhas **não** ganham coluna: `planos_nutricionais`, `cardapios_*` e `restricoes_paciente` são escopadas via JOIN com `pacientes.criado_por`. Se algum dia houver necessidade de "adotar" dados órfãos, resolve-se na âncora.

## Matriz de permissões

| Área | admin | nutricionista | leitura |
|---|---|---|---|
| **Usuários** | CRUD | — | — |
| **Regras globais** (Dietas, Tipos, Elegibilidade, Restrições Nutricionais, Sensoriais, Variedade, Composição Refeições, Dietas×Refeições) — config do motor | CRUD | somente leitura | somente leitura |
| **Regras do paciente** (`restricoes_paciente` + delta da personalização futura) | CRUD (todos) | CRUD **só dos próprios pacientes** | somente leitura |
| **Catálogo** (Ingredientes, Pratos, Composição de Pratos, Alimentos Industrializados) | CRUD | CRUD | somente leitura |
| **Pacientes** (tabela admin + página `/pacientes`) | CRUD (todos) | CRUD **só dos próprios** | somente leitura (só dos próprios) |
| **Planos e cardápios** | CRUD (todos) | CRUD **só dos próprios** | somente leitura (só dos próprios) |
| **Consultas** (views de nutrientes) | leitura | leitura | leitura |
| **Ferramentas** (Ficha Técnica, Cadastro por Rótulo, Otimização, Posso Comer?, Alimentos Semelhantes) | total | total (Posso Comer/planos limitados aos próprios pacientes) | GET liberado, POST bloqueado (403) |

## Mecanismo

- **`models_auth.py`** — modelo `Usuario` (UserMixin) com `set_senha()/check_senha()`, `is_admin`, `pode(acao)`.
- **`SecureModelView`** (em `admin_views.py`, substituindo `BaseModelView` como base):
  - atributo `papeis_permitidos` (lista) por view;
  - `is_accessible()` → `current_user.is_authenticated` e papel ∈ `papeis_permitidos` (admin passa em tudo);
  - `can_create/can_edit/can_delete` viram métodos que avaliam papel;
  - `inaccessible_callback` → redireciona para `/login?next=...`.
- **Escopo por dono no Flask-Admin** (views de paciente/plano/restrição):
  - sobrescrever `get_query()` e `get_count_query()` → `criado_por == current_user.id` (ou via JOIN no paciente) quando não-admin;
  - sobrescrever `get_one()` → retorna None (404) se o registro não for do usuário;
  - admin não aplica filtro.
- **Escopo por dono nas rotas de API** (`api/paciente.py`, `api/plano.py`, `api/posso_comer.py`):
  - toda rota que recebe `paciente_id` valida posse antes de ler/gravar (404 se não for do usuário);
  - listagens filtram `criado_por`;
  - criar paciente grava `criado_por = current_user.id`.
- **`UsuarioView`** — só admin; `senha_hash` fora de `column_list`; form com campos Senha/Confirmar (widget password) que gravam hash.
- **`DashboardView`** — exige login; menu ganha "Sair" (logout).
- **Proteção global** (`before_request` em `app2.py`): qualquer rota fora de exceções (`/login`, `/logout`, `/static/*`) exige sessão; endpoints `/api/*` respondem **401 JSON** (em vez de redirect); demais redirecionam para `/login?next=...`.
- **Rotas**: `/login` (GET form + POST valida) e `/logout` (POST) num blueprint `auth.py`. Template `templates/login.html` no tema Bootstrap4 atual (paleta Blues — daltônico).
- **CLI**: `flask --app app2.py criar-usuario --email ... --nome ... --papel admin` (senha via prompt, sem senha default).

## Rollout (ordem segura)

1. `uv pip install --python ~/.venv/bin/python flask-login` + adicionar ao `requirements.txt`.
2. Bruno executa o DDL: `sqlite3 cardapio_hospitalar.db < docs/sql/autenticacao.sql`.
3. Bruno cria o admin inicial via CLI `criar-usuario` (e um usuário `nutricionista` + um `leitura` para testar).
4. `.env`: adicionar `SECRET_KEY=<valor longo aleatório>`; `config.py` passa a ler `os.getenv`.
5. Deploy do código com auth ativo — validar primeiro em instância temporária na porta 5001 (login com os 3 papéis, 401 JSON em `/api/*`, isolamento entre nutricionistas), depois restart do serviço real.
6. Atribuir dono aos pacientes existentes (admin).
7. Teste E2E do Bruno: login/logout; nutricionista A não vê paciente da B (nem por URL direta); admin vê tudo; leitura só visualiza; POST de leitura bloqueado.

## Impacto no plano de personalização por paciente

O delta de `restricoes_paciente` (faixas, exclusões, aversões...) será escopado **pelo paciente** (JÁ tem `paciente_id`) → a posse flui da âncora `pacientes.criado_por`. Nenhuma coluna extra de dono nas tabelas do delta. Decisão de dono sai daqui e entra no DDL de personalização quando ele for implementado.

## Fora de escopo (v1)

- CSRF nos forms (app hoje não tem; mesma exposição de antes).
- Rate limiting de login / 2FA.
- **Recomendação paralela:** ativar a policy de Access no Cloudflare Zero Trust (e-mail do Bruno) — o login do app é a 2ª camada; a 1ª camada (quem chega no hostname) fica com o Cloudflare.
