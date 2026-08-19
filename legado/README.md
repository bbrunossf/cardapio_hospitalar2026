# legado/

Arquivos antigos/mortos fora do app ativo — arquivados em 19/08/2026
(consolidação da documentação). **Nenhum é importado pelo código ativo**
(confirmado por grep + import-map do Understand-Anything). Mantidos para
consulta/histórico; remoção definitiva fica a critério do Bruno.

## Arquivos

| Arquivo | O que era | Substituído por |
|---|---|---|
| `app.py` | App Flask antigo | `app2.py` |
| `app2 - Copia.py` | Cópia de backup do app2.py | `app2.py` |
| `motor_otimizacao.py` | Versão antiga do motor PuLP | `api/otimizacao.py` |
| `motor_otimizacao2.py` | Versão antiga do motor PuLP | `api/otimizacao.py` |
| `diagnostico_modelo.py` | Script de diagnóstico do motor | — (avulso) |
| `diagnostico_modelo2.py` | Script de diagnóstico do motor | — (avulso) |
| `cardapio_por_refeicao.py` | Script antigo de geração por refeição | motor em `api/otimizacao.py` |
| `teste_consulta_openfoodfacts.py` | Teste avulso da consulta Open Food Facts | `scripts/importar_openfoodfacts.py` |
| `scripts_iniciais/` | Scripts iniciais do projeto (projeto1, regras, classificador de alimentos) | módulos em `api/` e `calculo_nutricional/` |
| `scripts-aplicados/` | DDLs do schema v5 **já aplicados** (`prato_composicao` + `vw_pratos_nutricional`; tabela `pacientes`) + `popular tabela pratos.xlsx` (fonte de dados original dos pratos) | schema vigente no banco |

## reference/ — design descartado "Vitalis Clinical"

**Design system DESCARTADO** (pré-regra de acessibilidade do Bruno):
- `DESIGN.md` — tokens "Vitalis Clinical": paleta com **verde primário**
  (`#006d37`/`#2ECC71`) + Inter — viola a regra de daltonismo (nunca depender de
  vermelho/verde; preferir Blues)
- `code.html` — mockup "NutriClin - Anamnesis" (Tailwind CDN + Material Symbols)
- `screen.png` — screenshot do mockup (1600×1521)

**Design vigente:** `DESIGN.md` na raiz — "Cardapio Plena", NHS Blue `#005EB8`,
IBM Plex Sans, off-white, semântica acessível (teal/âmbar/laranja).
