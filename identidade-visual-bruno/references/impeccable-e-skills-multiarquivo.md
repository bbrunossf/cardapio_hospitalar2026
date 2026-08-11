# Impeccable + instalação de skills multi-arquivo (avaliado ago/2026)

## O que é a Impeccable

- Repo: `pbakaus/impeccable` · site: impeccable.style · skill de DESIGN para agentes de código (v4.x).
- 1 skill, 23 comandos (`init`, `craft`, `shape`, `critique`, `audit`, `polish`, `bolder`, `colorize`...), ~59 regras determinísticas anti-"AI slop" (Inter demais, gradientes genéricos).
- Descendente da `frontend-design` da Anthropic.
- **Decisão do Bruno: NÃO usar** — consome MUITOS tokens (DESIGN.md entra em todo subcomando + iteração no browser + passes múltiplos). É skill de craft genérico, NÃO de identidade pessoal. Para identidade com gostos próprios, a skill `identidade-visual-bruno` + DESIGN.md é o caminho barato.
- Se um dia for instalar: requer Node (`scripts/context.mjs`).

## Instalar skill MULTI-ARQUIVO (SKILL.md + references/ + scripts/)

⚠️ `hermes skills install <url>` baixa UM arquivo só — quebra skills cujo SKILL.md referencia `references/*.md` / `scripts/*` (caso da Impeccable, que tem 23 arquivos de referência). Instalação correta via clone + cópia:

```bash
cd /tmp
git clone --depth 1 https://github.com/pbakaus/impeccable.git
mkdir -p ~/.hermes/skills/creative/impeccable
cp -r impeccable/.agents/skills/impeccable/* ~/.hermes/skills/creative/impeccable/
```

- Localização típica no repo: `.agents/skills/<nome>/` (também pode ser `skills/`, `.claude/skills/`, `.cursor/skills/`).
- Depois: `/reload-skills` (ou nova sessão — loader cacheado).
- Verificar estrutura antes de instalar: listar a árvore do repo (GitHub API `git/trees/<branch>?recursive=1`) e procurar `SKILL.md` + conferir se o conteúdo referencia arquivos irmãos.

## `hermes skills install <url>` — quando serve

Só para skills de arquivo único (hub ou URL direta de SKILL.md autocontido). Sempre checar se o SKILL.md tem links relativos (`reference/...`, `scripts/...`) antes.
