# Motor de Otimização — histórico de versões

Documentação **versionada** do motor de cardápio (PuLP/CBC). Cada versão tem
seu próprio doc; o arquivo correspondente da versão antiga está em `legado/`.

> **Fluxo do código (passo a passo):** [fluxo-do-motor.md](fluxo-do-motor.md) —
> como o motor recebe os dados, quais variáveis cria e quais regras aplica,
> sem entrar nos detalhes do algoritmo PuLP.

| Versão | Arquivo | Data | Objetivo | Variáveis | Refeições |
|---|---|---|---|---|---|
| [v1](v1-motor_otimizacao.md) | `legado/motor_otimizacao.py` | 03/08/2026 | minimizar lipídios | `X[p, t, d]` (prato, tipo, dia) | não |
| [v2](v2-motor_otimizacao2.md) | `legado/motor_otimizacao2.py` | 08/08/2026 | maximizar energia | `X[p, d]` (prato, dia) | não |
| [v3](v3-api_otimizacao.md) | `api/otimizacao.py` | 03/08 → 18/08 (atual) | max energia / target | `X[p, r, d]` (prato, refeição, dia) | sim |

## Resumo da evolução

- **v1 → v2 (schema v5):** nutrientes deixaram de vir das colunas de `pratos`
  e passaram a ser calculados pela `vw_pratos_nutricional` (composição × 100g);
  objetivo virou maximizar energia; elegibilidade por dieta implementada;
  timeout do solver introduzido (180s + gap 10%)
- **v2 → v3 (refeições):** a variável ganhou a dimensão **refeição**
  (`X[p, r, d]`) — antes o modelo agregava por tipo no dia inteiro e não
  conseguia montar o cardápio por refeição; migração para SQLAlchemy dentro de
  um blueprint Flask; composição por refeição com bloqueio de tipos não
  autorizados; overrides do plano; regra sensorial `sem_quentes`; log do motor
  (JSONL + `MOTOR_DEBUG`); objetivo `target` (desvio absoluto da meta) para o
  fluxo de planos
- **v3 é a única versão viva.** v1/v2 não são importadas por nenhum código
  ativo (confirmado por grep + import-map do Understand-Anything)

## Pendências do motor (v3)

- **Industrializados no motor** — DDL executado (18/08), código pendente
  (`docs/industrializados_no_motor.md`): a função `carregar_alimentos_industrializados`
  existe, mas `criar_modelo_otimizacao` ainda não os usa
- **Objetivo genérico max/min** — proposta documentada, aguardando aprovação
  (`docs/objetivo_generico.md`); hoje só `max_energia` e `target`
- **Regras de variedade** — carregadas (`regras_variedade`) mas **não
  aplicadas** no modelo (desde a v2, comentadas por conflito com composição)
- **Sensoriais** — só `sem_quentes` implementada; `max_cores_iguais` e
  `consistencia_unica` permanecem inertes
