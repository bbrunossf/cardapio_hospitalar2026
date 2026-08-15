# Busca de Alimentos Semelhantes (busca semântica)

Página independente do "Posso Comer?": o usuário consulta o banco de
ingredientes por **texto livre** e recebe os alimentos mais semelhantes
(semântica via banco vetorial), sem precisar passar pelo fluxo de impacto
nutricional do dia.

## Como funciona

1. **Embedding da query** — texto livre → vetor 1536d via `POST /embed` da API
   isolada de interpretação (`POSSO_COMER_API_URL`, porta 5010). A chave
   OpenAI continua fora do app.
2. **Busca por similaridade** — query na coleção `ingredientes_embeddings` do
   `chroma_db/` (323 vetores, text-embedding-3-small), top_k = 1..10.
3. **Enriquecimento** — kcal e `tipo_alimento` vindos do banco relacional
   (os metadados do chroma não guardam energia).

Estrutura inspirada na função `buscar_ingredientes_semelhantes()` do Bruno
(adaptada: embedding via API isolada + kcal do SQL; mesma query do chroma com
`include=['documents','distances','metadatas']`).

## Arquivos

- `api/busca_semelhantes.py` — blueprint `busca_semelhantes_bp`:
  `GET /busca-semelhantes` (página) e `POST /api/busca-semelhantes`
  (JSON `{query, top_k}` → `{query, top_k, resultados:[{id, nome, tipo,
  kcal_100g, distancia, texto_semantico}]}`). Reusa `_get_chroma` e
  `_chamar_api` de `api.posso_comer`
- `templates/busca_semelhantes.html` — campo de texto + seletor de top_k
  (3/5/10) + botão; cards com nome, badge de tipo, kcal/100g, distância
  (menor = mais próximo) e o texto semântico
- `static/js/busca_semelhantes.js` — fetch + render; Enter dispara a busca
- `app2.py` — registro do blueprint; `admin_views.py` — MenuLink
  "Alimentos Semelhantes" (Ferramentas)

## Exemplos validados (15/08/2026)

- "fruta tropical" → Abacaxi, Polpa de fruta, Polpa de maracujá congelada,
  Manga Tommy Atkins, Abacaxi cru
- "bolo de chocolate" → Pudim de chocolate, Achocolatado, Achocolatado em pó

## Observações

- A distância exibida é a do espaço do banco (coleção criada sem espaço
  explícito → L2); menor = mais próximo. Uma recriação com o script
  (`scripts/gerar_embeddings_alimentos.py`, espaço COSINE) normalizaria os
  valores — cosmético, não funcional
- Falha da API de interpretação → HTTP 502 com mensagem; banco vetorial
  indisponível → HTTP 502
