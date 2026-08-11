# DESIGN.md — Linter Pitfalls (validado em ago/2026 no projeto cardápio)

Comandos (Node via npx, sem instalação global):

```bash
npx -y @google/design.md lint DESIGN.md
npx -y @google/design.md export --format tailwind DESIGN.md > tailwind.theme.json
npx -y @google/design.md export --format dtcg DESIGN.md > tokens.json
```

## Pitfalls que apareceram na prática

1. **`layout:` NÃO é chave reconhecida no frontmatter.** O linter avisa "looks like a design-token map but is not a recognized schema key... silently ignored by export". Sintoma: erro `Reference {layout.sidebar-width} does not resolve`. Correção: remover o bloco `layout:` do frontmatter; valores de layout vão na prosa do corpo OU como valor literal no componente (ex: `sidebar: width: 240px`).

2. **Badges de tom claro falham WCAG AA raspando.** Texto sobre tint claro costuma dar ~4.2-4.4:1 (mínimo 4.5:1). Corrigir escurecendo o TEXTO, não o fundo. Valores que passaram (verificados):
   - success: bg `#DDF0EE`, texto `#065F5A` (4.38→5.0+)
   - warning: bg `#FBF0DC`, texto `#7A5300` (4.15→4.5+)
   - danger: bg `#F9E4DC`, texto `#9A3309` (4.23→4.5+)

3. **Warnings "orphaned-tokens" são inofensivas.** "colors.text-muted is defined but never referenced by any component" — normal para cores utilitárias que o CSS consome diretamente. Não bloquear por isso; objetivo é 0 erros, warnings aceitáveis.

4. **Hex colors SEMPRE como string** (`"#005EB8"`), senão o YAML engole o `#`.

5. **Dimensões negativas com aspas**: `letterSpacing: "-0.02em"`.

6. **Variantes de componente são chaves irmãs**, não aninhadas: `button-primary-hover`, nunca `button-primary.hover`.

7. **Token references por caminho pontilhado**: `{colors.primary}` funciona; `{primary}` não.

8. **Ordem canônica de seções é imposta**: Overview → Colors → Typography → Layout → Elevation & Depth → Shapes → Components → Do's and Don'ts. Título duplicado rejeita o arquivo.

## Output de um lint limpo

```
ERRORS: 0  (meta: 1 erro comum = reference quebrada)
WARNINGS: n (orphaned-tokens OK)
```
