"""
Gerador do banco vetorial de alimentos (ChromaDB) — versão versionada.

Recria a coleção `ingredientes_embeddings` em `chroma_db/` a partir dos
ingredientes ativos do cardapio_hospitalar.db:

- Descrição textual de cada ingrediente, em 3 modos:
    * `llm`      — GPT-4o-mini escreve descrição rica em PT-BR (qualidade do
                   índice original de 04/08; ~centavos por recriação)
    * `template` — descrição determinística a partir dos dados nutricionais
                   (zero custo, offline, 100% reproduzível)
    * `auto`     — tenta LLM; se a chamada falhar, usa template do item (default)
- Embeddings via OpenAI text-embedding-3-small (1536 dims)
- Cache das descrições em JSON (reutilizado entre execuções — sem regerar,
  sem custo) — caminho: scripts/descricoes_llm_cache.json (gitignorado)

Uso:
    ~/.venv/bin/python scripts/gerar_embeddings_alimentos.py            # auto
    ~/.venv/bin/python scripts/gerar_embeddings_alimentos.py --modo llm
    ~/.venv/bin/python scripts/gerar_embeddings_alimentos.py --modo template
    ~/.venv/bin/python scripts/gerar_embeddings_alimentos.py --recriar
    ~/.venv/bin/python scripts/gerar_embeddings_alimentos.py --ids 1,48 --somente-descricoes
    ~/.venv/bin/python scripts/gerar_embeddings_alimentos.py --dry-run

Dependências (já no requirements.txt): chromadb==1.5.9, httpx, python-dotenv.
OPENAI_API_KEY: .env do projeto ou variável de ambiente (só necessária nos
modos llm/auto — para template, desnecessária).
"""
import argparse
import json
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "cardapio_hospitalar.db"
CHROMA_PATH = BASE_DIR / "chroma_db"
CACHE_PATH = Path(__file__).resolve().parent / "descricoes_llm_cache.json"
COLECAO = "ingredientes_embeddings"
MODELO_EMBEDDING = "text-embedding-3-small"
MODELO_LLM = "gpt-4o-mini"
BATCH_EMBED = 50
BATCH_LLM = 10

# Chave: .env do projeto (dotenv) ou variável de ambiente
from dotenv import load_dotenv  # noqa: E402
load_dotenv(BASE_DIR / ".env")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()


# ------------------------------------------------------------------ descrições
def descricao_template(r):
    """Descrição determinística do alimento a partir dos dados nutricionais."""
    p = [f"{r['nome']} é um alimento do tipo {r['tipo_alimento'] or 'não classificado'}."]
    if r["energia_kcal"] is not None:
        p.append(f"Apresenta cerca de {r['energia_kcal']:.0f} kcal por 100 gramas.")
    macros = []
    if r["carboidrato_g"] is not None:
        macros.append(f"{r['carboidrato_g']:.1f} g de carboidratos")
    if r["proteina_g"] is not None:
        macros.append(f"{r['proteina_g']:.1f} g de proteínas")
    if r["lipidios_g"] is not None:
        macros.append(f"{r['lipidios_g']:.1f} g de lipídios")
    if macros:
        p.append("Contém " + ", ".join(macros) + " por 100 g.")
    if r["fibra_alimentar_g"] is not None:
        p.append(f"Oferece {r['fibra_alimentar_g']:.1f} g de fibras.")
    if r["sodio_mg"] is not None:
        p.append(f"Teor de sódio de {r['sodio_mg']:.0f} mg por 100 g.")
    return " ".join(p)


def _dados_para_prompt(r):
    return (f"- {r['id']}: {r['nome']} | tipo: {r['tipo_alimento'] or 'n/a'} | "
            f"kcal/100g: {r['energia_kcal']} | carboidratos: {r['carboidrato_g']} g | "
            f"proteínas: {r['proteina_g']} g | lipídios: {r['lipidios_g']} g | "
            f"fibras: {r['fibra_alimentar_g']} g | sódio: {r['sodio_mg']} mg/100g")


def descricao_llm_batch(rows):
    """Descrições ricas (GPT-4o-mini) para até BATCH_LLM ingredientes; retorna
    {id: descricao}. Lança exceção em falha (o chamador decide o fallback)."""
    import httpx

    itens = "\n".join(_dados_para_prompt(r) for r in rows)
    prompt = (
        "Você é um nutricionista escrevendo textos de busca de um sistema de cardápio "
        "hospitalar. Para CADA alimento listado, escreva UMA descrição curta "
        "(1-2 frases, em PT-BR) em linguagem natural, com características úteis para "
        "busca: o que é, categoria, uso típico, e quando fizer sentido textura/sabor. "
        "NÃO invente informações fora dos dados fornecidos. "
        "Responda APENAS com JSON no formato "
        '{"descricoes": [{"id": <id>, "descricao": "<texto>"}, ...]}.\n\n'
        f"Alimentos:\n{itens}"
    )
    resp = httpx.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
        json={
            "model": MODELO_LLM,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
            "temperature": 0.7,
        },
        timeout=120,
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    dados = json.loads(content)
    return {int(d["id"]): d["descricao"] for d in dados.get("descricoes", [])}


def gerar_descricoes(ingredientes, modo, cache_path, somente_descricoes=False):
    """Retorna lista de descrições na MESMA ordem de `ingredientes`."""
    if modo == "template":
        return [descricao_template(r) for r in ingredientes]

    if not OPENAI_API_KEY:
        if modo == "llm":
            sys.exit("Modo llm exige OPENAI_API_KEY (no .env do novo_cardapio ou exportada).")
        print("[aviso] sem OPENAI_API_KEY — usando template", flush=True)
        return [descricao_template(r) for r in ingredientes]

    cache = {}
    if cache_path.exists():
        try:
            cache = json.loads(cache_path.read_text())
            print(f"cache carregado: {len(cache)} descrições", flush=True)
        except Exception:
            cache = {}

    faltando = [r for r in ingredientes if str(r["id"]) not in cache]
    if faltando:
        import httpx

        print(f"gerando {len(faltando)} descrições via {MODELO_LLM} "
              f"(batches de {BATCH_LLM})...", flush=True)
        for i in range(0, len(faltando), BATCH_LLM):
            batch = faltando[i:i + BATCH_LLM]
            novo = {}
            try:
                novo = descricao_llm_batch(batch)  # 1ª tentativa
            except Exception as e:
                try:
                    novo = descricao_llm_batch(batch)  # retry
                except Exception as e2:
                    print(f"[aviso] batch {i // BATCH_LLM + 1} falhou: {e2}", flush=True)
                    novo = {}
            for r in batch:
                d = novo.get(r["id"])
                if d:
                    cache[str(r["id"])] = d
                elif modo == "llm":
                    sys.exit(f"Falha gerando descrição do id {r['id']} (modo llm sem fallback).")
                else:
                    cache[str(r["id"])] = descricao_template(r)  # fallback auto
            print(f"  batch {i // BATCH_LLM + 1}: +{len(batch)} (total no cache {len(cache)})",
                  flush=True)
        cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2))
        print(f"cache salvo em {cache_path}", flush=True)

    if somente_descricoes:
        return [cache[str(r["id"])] for r in ingredientes]
    return [cache[str(r["id"])] for r in ingredientes]


# -------------------------------------------------------------------- banco
def carregar_ingredientes(ids_filtro=None):
    import sqlite3

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    sql = """
        SELECT id, nome, tipo_alimento, energia_kcal, carboidrato_g, proteina_g,
               lipidios_g, fibra_alimentar_g, sodio_mg, custo_por_100g
        FROM ingredientes WHERE desativado = 0
    """
    params = ()
    if ids_filtro:
        sql += f" AND id IN ({','.join('?' * len(ids_filtro))})"
        params = tuple(ids_filtro)
    sql += " ORDER BY id"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def embed_batch(textos):
    import httpx

    resp = httpx.post(
        "https://api.openai.com/v1/embeddings",
        headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
        json={"model": MODELO_EMBEDDING, "input": textos},
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()["data"]
    data.sort(key=lambda x: x["index"])
    return [d["embedding"] for d in data]


# ---------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modo", choices=["auto", "llm", "template"], default="auto",
                    help="auto: LLM com fallback p/ template (default); llm: só LLM; "
                         "template: determinístico (offline)")
    ap.add_argument("--recriar", action="store_true", help="apaga e recria a coleção")
    ap.add_argument("--ids", default="", help="filtra por ids (vírgula) — p/ testes")
    ap.add_argument("--cache", default=str(CACHE_PATH), help="caminho do cache de descrições")
    ap.add_argument("--somente-descricoes", action="store_true",
                    help="só imprime as descrições (revisão), sem chamar a API de embedding")
    ap.add_argument("--dry-run", action="store_true",
                    help="mostra o plano sem chamar nenhuma API")
    args = ap.parse_args()

    if not DB_PATH.exists():
        sys.exit(f"Banco não encontrado: {DB_PATH}")

    ids_filtro = [int(x) for x in args.ids.split(",") if x.strip()] if args.ids else None
    ingredientes = carregar_ingredientes(ids_filtro)
    print(f"{len(ingredientes)} ingredientes ativos em {DB_PATH.name}"
          + (f" (filtro ids={ids_filtro})" if ids_filtro else ""))

    if args.dry_run:
        print("DRY-RUN: sem chamadas a nenhuma API. Plano:")
        print(f"  modo descrições: {args.modo} (cache: {args.cache})")
        print(f"  coleção: {COLECAO} em {CHROMA_PATH}")
        print(f"  modelo embedding: {MODELO_EMBEDDING} | batches de {BATCH_EMBED}"
              f" | total {len(ingredientes)}")
        return

    descricoes = gerar_descricoes(ingredientes, args.modo, Path(args.cache),
                                  somente_descricoes=args.somente_descricoes)

    if args.somente_descricoes:
        for r, texto in zip(ingredientes, descricoes):
            print(f"--- {r['id']} {r['nome']}\n{texto}\n")
        return

    if not OPENAI_API_KEY:
        sys.exit("OPENAI_API_KEY não encontrada (necessária para embeddings). "
                 "Coloque no .env do novo_cardapio ou exporte. "
                 "Para revisar descrições sem chave: --somente-descricoes")

    import chromadb

    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    if args.recriar:
        try:
            client.delete_collection(COLECAO)
            print("coleção antiga removida")
        except Exception:
            pass
    col = client.get_or_create_collection(
        COLECAO, metadata={"hnsw:space": "cosine"})

    total = 0
    for i in range(0, len(descricoes), BATCH_EMBED):
        fatia = ingredientes[i:i + BATCH_EMBED]
        fatia_ids = [str(r["id"]) for r in fatia]
        fatia_metas = [{
            "nome": r["nome"],
            "tipo": r["tipo_alimento"] or "",
            "custo": str(r["custo_por_100g"] or ""),
            "proteina": str(r["proteina_g"] or ""),
            "carboidrato": str(r["carboidrato_g"] or ""),
            "texto_original": descricoes[i + k],
        } for k, r in enumerate(fatia)]
        vetores = embed_batch(descricoes[i:i + BATCH_EMBED])
        col.upsert(ids=fatia_ids, embeddings=vetores, metadatas=fatia_metas)
        total += len(vetores)
        print(f"  batch {i // BATCH_EMBED + 1}: +{len(vetores)} (total {total})")

    print(f"\nOK: coleção '{COLECAO}' com {col.count()} embeddings "
          f"({MODELO_EMBEDDING}, {len(vetores)} dims)")


if __name__ == "__main__":
    main()
