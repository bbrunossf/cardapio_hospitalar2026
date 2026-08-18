#!/usr/bin/env python3
"""Extrai do dump CSV do Open Food Facts só produtos do Brasil, com o subconjunto
de colunas usado pelo importador e SEM linhas inúteis (mesma taxonomia de filtros
de scripts/importar_openfoodfacts.py).

Plano: docs/importacao_openfoodfacts.md (18/08/2026).

Pré-filtros aplicados aqui (linhas descartadas com contagem por motivo):
    pais        countries* não contém "brazil"
    sem_nutri   no_nutrition_data = 1
    sem_energia energy-kcal_100g ausente/inválida
    sem_porcao  serving_quantity ausente/inválida
    sem_nome    sem product_name/abbreviated/generic
    linha_invalida  linha com quotes quebradas ou número de campos ≠ header

Campos que continuarem vazios na saída ficam vazios — o importador grava NULL
(nunca estima). Produtos com lacunas parciais (ex.: sódio ausente) entram no banco
e a política NULL do motor trata o resto (ver doc seção 6).

Uso:
    cd /home/plena/novo_cardapio
    ~/.venv/bin/python scripts/extrair_off_brasil.py --origem dump.csv --destino off_brasil.csv
    ~/.venv/bin/python scripts/extrair_off_brasil.py --origem dump.csv --destino off_brasil.csv --limite 10000
"""
import argparse
import csv
import io
import sys
from pathlib import Path

# Subconjunto exato de colunas usado pelo importador (docs/importacao_openfoodfacts.md seção 3)
COLUNAS_OFF = [
    "code",
    "product_name",
    "abbreviated_product_name",
    "generic_name",
    "quantity",
    "product_quantity",
    "brands",
    "brand_owner",
    "serving_size",
    "serving_quantity",
    "no_nutrition_data",
    "countries",
    "countries_tags",
    "countries_en",
    "energy-kcal_100g",
    "carbohydrates_100g",
    "sugars_100g",
    "added-sugars_100g",
    "proteins_100g",
    "fat_100g",
    "saturated-fat_100g",
    "trans-fat_100g",
    "fiber_100g",
    "sodium_100g",
    "ingredients_text",
    "allergens_en",
    "categories_en",
    "categories_tags",
    "pnns_groups_1",
]


def parse_linha(linha, n_colunas):
    """Uma linha do dump OFF pode ter quotes quebradas (conhecido). None = irrecuperável."""
    try:
        campos = next(csv.reader(io.StringIO(linha)))
    except csv.Error:
        return None
    if len(campos) != n_colunas:
        return None
    return campos


def float_val(raw):
    s = str(raw or "").strip()
    if not s:
        return None
    try:
        v = float(s)
    except ValueError:
        return None
    return None if v < 0 else v


def motivo_descarte(row):
    """Retorna o motivo do descarte ou None se a linha aproveita."""
    paises = " ".join([row.get("countries_tags") or "",
                       row.get("countries_en") or "",
                       row.get("countries") or ""]).lower()
    if "brazil" not in paises:
        return "pais"
    if str(row.get("no_nutrition_data") or "").strip() == "1":
        return "sem_nutri"
    e = float_val(row.get("energy-kcal_100g"))
    if e is None or e <= 0:
        return "sem_energia"
    p = float_val(row.get("serving_quantity"))
    if p is None or p <= 0:
        return "sem_porcao"
    nome = str(row.get("product_name") or row.get("abbreviated_product_name")
               or row.get("generic_name") or "").strip()
    if not nome:
        return "sem_nome"
    return None


def extrair(args):
    contadores = {"pais": 0, "sem_nutri": 0, "sem_energia": 0, "sem_porcao": 0,
                  "sem_nome": 0, "linha_invalida": 0, "aproveitadas": 0}
    linhas = 0
    primeiro = True
    header = None

    with open(args.origem, encoding="utf-8", errors="replace", newline="") as fin, \
         open(args.destino, "w", encoding="utf-8", newline="") as fout:
        w = csv.DictWriter(fout, fieldnames=COLUNAS_OFF)
        w.writeheader()
        for bruta in fin:
            if args.limite and linhas >= args.limite:
                break
            linhas += 1
            linha = bruta.rstrip("\r\n")
            if not linha.strip():
                continue
            if primeiro:
                primeiro = False
                header = parse_linha(linha, 0) or next(csv.reader(io.StringIO(linha)))
                header = [h.strip() for h in header]
                if "code" not in header:
                    sys.exit(f"ERRO: dump sem coluna 'code' (headers: {header[:8]}...)")
                n_colunas = len(header)
                continue
            campos = parse_linha(linha, n_colunas)
            if campos is None:
                contadores["linha_invalida"] += 1
                continue
            row = dict(zip(header, campos))
            motivo = motivo_descarte(row)
            if motivo:
                contadores[motivo] += 1
                continue
            w.writerow({c: row.get(c, "") for c in COLUNAS_OFF})
            contadores["aproveitadas"] += 1

    return contadores, linhas


def main():
    ap = argparse.ArgumentParser(description="Extrai produtos do Brasil do dump OFF "
                                             "(doc: docs/importacao_openfoodfacts.md)")
    ap.add_argument("--origem", required=True, help="dump CSV completo do OFF")
    ap.add_argument("--destino", required=True, help="CSV filtrado de saída")
    ap.add_argument("--limite", type=int, default=0, help="testar só as N primeiras linhas")
    args = ap.parse_args()

    c, linhas = extrair(args)
    util = c["aproveitadas"]
    pct = 100.0 * util / linhas if linhas else 0.0
    print(f"Linhas lidas: {linhas}")
    print(f"Aproveitadas: {util} ({pct:.1f}%)")
    print("Descartadas: "
          f"pais={c['pais']} sem_nutri={c['sem_nutri']} sem_energia={c['sem_energia']} "
          f"sem_porcao={c['sem_porcao']} sem_nome={c['sem_nome']} linha_invalida={c['linha_invalida']}")
    print(f"Saída: {args.destino}")


if __name__ == "__main__":
    main()
