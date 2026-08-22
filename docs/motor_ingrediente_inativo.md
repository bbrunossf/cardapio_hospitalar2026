# Prato com ingrediente desativado ou apagado — regra do motor

Status: PROPOSTA (22/08/2026)
Escopo: `carregar_dados_otimizacao` / `criar_modelo_otimizacao` (`api/otimizacao.py`)
Schema: sem mudança (não gera DDL)

## Contexto

- Prática definida: nunca apagar pratos/ingredientes — marcar `desativado = 1` (coluna já existe em `pratos`, `ingredientes` e `prato_composicao`).
- Incidente 21/08: deleção via DBeaver (FK OFF) orfanou 18 linhas em `prato_composicao` (6 ingredientes apagados: 42, 184, 277, 311, 313, 314).
- Gap atual: o motor filtra só `pratos.desativado = 0`. Um prato cuja composição ativa referencia ingrediente **desativado** (ou **apagado**) continua entrando como candidato, com o cálculo nutricional baseado nos dados do ingrediente problemático.

## Regra proposta

**Prato é excluído do motor se tiver ao menos uma linha de composição ATIVA (`pc.desativado = 0`) referenciando ingrediente apagado ou desativado.**

- Exclusão determinística, no carregamento (antes do PuLP) — não é restrição do modelo.
- O prato entra na lista de excluídos com o motivo (padrão `excluidos_null`), visível no log do motor e no payload.
- Caso extremo: linha órfã (ingrediente apagado) cai no mesmo caminho — a regra protege o cardápio mesmo com o dado ainda sujo no banco.

### SQL de detecção (canônico)

```sql
SELECT DISTINCT pc.prato_id
FROM prato_composicao pc
LEFT JOIN ingredientes i ON i.id = pc.ingrediente_id
WHERE pc.desativado = 0
  AND (i.id IS NULL OR i.desativado = 1);
```

### Esboço de implementação

```python
# em carregar_dados_otimizacao, antes de montar o modelo:
ids_excluidos_ing = {r[0] for r in db.session.execute(text("""
    SELECT DISTINCT pc.prato_id
    FROM prato_composicao pc
    LEFT JOIN ingredientes i ON i.id = pc.ingrediente_id
    WHERE pc.desativado = 0 AND (i.id IS NULL OR i.desativado = 1)
""")).all()}
# filtra os candidatos e registra em excluidos_ingrediente_inativo (log + payload)
```

## Decisões

- **D1 — Excluir, não sinalizar:** prato incompleto não deve ser candidato (gerar cardápio com dado errado é pior que ausência). Badge de aviso na Ficha Técnica fica como melhoria separada de UI.
- **D2 — Linha de composição desativada não conta:** `pc.desativado = 1` é soft-delete da própria linha; só referência ruim em linha ativa exclui o prato.
- **D3 — Apagado e desativado, mesmo caminho:** ambos viram exclusão; o apagado é o caso extremo (dado irrecuperável sem backup).
- **D4 — Sem schema novo:** nenhum DDL; regra vive só no loader.
- **D5 — Transparência:** lista entra no `motor_log` (métrica `excluidos_ingrediente_inativo`) e no payload da resposta, seguindo o padrão de `excluidos_null`.
- **D6 — Fora de escopo:** pratos sem composição ativa (34 hoje) continuam como estão; tratar separado se o motor os aceitar com nutrição nula.

## Validação

1. Rodar o SQL de detecção antes e depois — conjunto de pratos excluídos deve bater.
2. Teste E2E em banco temporário: desativar um ingrediente → prato some do cardápio gerado; log lista o motivo.
3. Conferir no payload `excluidos_ingrediente_inativo` com `MOTOR_DEBUG=1`.

## Pendências relacionadas

- Limpeza dos 18 órfãos de 21/08 (SQL de repoint entregue: 313/314→310, 311→312, 277→278, 42→41, 184→183) — independente desta regra; a regra protege o cardápio enquanto o dado não for corrigido.
