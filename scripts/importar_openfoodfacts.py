#!/usr/bin/env python3
"""Importa produtos do dump CSV do Open Food Facts para alimentos_industrializados.

Plano: docs/importacao_openfoodfacts.md (18/08/2026) — mapeamento OFF->tabela,
conversão 100g -> porção do rótulo, filtros e políticas.

Idempotente: produtos já existentes (mesmo codigo_barras) são pulados; o script
NUNCA faz UPDATE/DELETE/ALTER — só INSERT. Re-executar não duplica.

Uso:
    cd /home/plena/novo_cardapio
    ~/.venv/bin/python scripts/importar_openfoodfacts.py --csv dump.csv --seco --limite 500
    ~/.venv/bin/python scripts/importar_openfoodfacts.py --csv dump.csv --sugerir-tipos
"""
import argparse
import csv
import io
import json
import re
import sqlite3
import sys
from pathlib import Path

from off_utils import detectar_delimitador, detectar_encoding, parse_linha, parse_num

REPO = Path(__file__).resolve().parent.parent
DEFAULT_DB = REPO / "cardapio_hospitalar.db"

# ── Mapeamento OFF (100g) -> coluna da tabela (porção) ─────────────────────
# valor_porcao = valor_100g * serving_quantity / 100
NUTRIENTES_OFF = [
    ("energy-kcal_100g", "energia_kcal"),
    ("carbohydrates_100g", "carboidratos_g"),
    ("sugars_100g", "acucares_totais_g"),
    ("added-sugars_100g", "acucares_adicionados_g"),
    ("proteins_100g", "proteinas_g"),
    ("fat_100g", "gorduras_totais_g"),
    ("saturated-fat_100g", "gorduras_saturadas_g"),
    ("trans-fat_100g", "gorduras_trans_g"),
    ("fiber_100g", "fibras_g"),
    ("sodium_100g", "sodio_mg"),
]

# ── Tradução de alérgenos comuns (OFF em inglês -> PT) ─────────────────────
ALERGENOS_PT = {
    "gluten": "glúten",
    "wheat": "trigo",
    "milk": "leite",
    "egg": "ovos",
    "eggs": "ovos",
    "soy": "soja",
    "soybean": "soja",
    "soybeans": "soja",
    "peanut": "amendoim",
    "peanuts": "amendoim",
    "tree nuts": "castanhas",
    "nuts": "castanhas",
    "fish": "peixe",
    "shellfish": "crustáceos",
    "crustaceans": "crustáceos",
    "molluscs": "moluscos",
    "sesame": "gergelim",
    "lupin": "tremoço",
    "mustard": "mostarda",
    "celery": "aipo",
    "sulphur dioxide": "dióxido de enxofre",
    "sulfites": "sulfitos",
}

# ── Sugestão de tipo_prato_id (docs/importacao_openfoodfacts.md seção 5) ───
# (palavras-chave, nome do tipo em tipos_preparacoes). Primeira coincidência vence.
SUGESTOES_TIPO = [
    (("biscoito", "bolacha", "cookie", "biscuit", "cracker", "wafer", "waffer"), "SD - Guarnição"),
    (("iogurte", "yogurt", "yoghurt", "queijo", "cheese", "requeijao", "requeijão", "manteiga", "butter", "cream cheese", "petit suisse"), "DP - Laticínios"),
    (("suco", "juice", "nectar", "néctar", "refresco"), "JC - Suco"),
    (("fruta", "frutas", "fruit", "banana", "maça", "maçã", "laranja", "uva", "apple", "orange", "grape"), "FT - Fruta"),
    (("arroz", "rice"), "RC - Arroz"),
    (("feijao", "feijão", "bean", "lentilha", "lentil", "grao de bico", "grão de bico", "chickpea"), "BE - Feijão"),
    (("chocolate", "pudim", "pudding", "gelatina", "jelly", "sorvete", "ice cream", "doce", "candy", "bolo", "cake", "sobremesa", "dessert"), "DS - Sobremesa"),
    (("cereal", "granola", "aveia", "oat", "muesli", "corn flakes"), "BC1 - Cereal (Café)"),
]

FONTE = "barcode"  # único valor compatível com o CHECK da tabela (ver doc seção 6.3)


def float_or_none(raw):
    """OFF usa string vazia p/ ausente; valores negativos = erro de edição -> None.
    Aceita vírgula decimal pt-BR (\"380,00\") via off_utils.parse_num."""
    return parse_num(raw)


def norm_name(raw, limite):
    s = str(raw or "").strip()
    return s[:limite] if s else None


def so_digitos(raw):
    return re.sub(r"\D", "", str(raw or ""))


def alergenos_json(raw):
    """allergens_en (ex.: 'Milk, Gluten') -> JSON array em PT, deduplicado."""
    if not raw:
        return None
    itens = []
    for parte in re.split(r"[,;]", str(raw)):
        tok = parte.strip().lower().removeprefix("en:").strip()
        if not tok:
            continue
        nome = ALERGENOS_PT.get(tok, tok)
        if nome not in itens:
            itens.append(nome)
    return json.dumps(itens, ensure_ascii=False) if itens else None


def sugerir_tipo(linha, mapa_tipos):
    """Busca palavras-chave em categories/pnns/product_name. Retorna id ou None."""
    campos = " ".join([
        linha.get("categories_en") or "",
        linha.get("categories_tags") or "",
        linha.get("pnns_groups_1") or "",
        linha.get("product_name") or "",
    ]).lower()
    for palavras, nome_tipo in SUGESTOES_TIPO:
        if any(p in campos for p in palavras):
            return mapa_tipos.get(nome_tipo)
    return None


def converter(linha, col_off, fator):
    v = float_or_none(linha.get(col_off))
    return None if v is None else round(v * fator, 2)


def importar(args):
    db = sqlite3.connect(args.db)
    db.execute("PRAGMA foreign_keys = ON")
    tabela_cols = {r[1] for r in db.execute("PRAGMA table_info(alimentos_industrializados)")}
    obrig = {"codigo_barras", "nome", "porcao_qtd", "porcao_unidade"}
    faltando = obrig - tabela_cols
    if faltando:
        sys.exit(f"ERRO: tabela alimentos_industrializados sem colunas {sorted(faltando)} — "
                 f"rodar o DDL da seção 5.2 do docs/especificacao_modulo_rotulo.md")

    tem_colunas_motor = {"porcao_padrao_g", "tipo_prato_id"} <= tabela_cols

    mapa_tipos = {}
    if tem_colunas_motor:
        mapa_tipos = {nome: tid for tid, nome in
                      db.execute("SELECT id, nome FROM tipos_preparacoes")}
        if args.sugerir_tipos and not mapa_tipos:
            sys.exit("ERRO: --sugerir-tipos mas tipos_preparacoes vazia ou sem nome")

    # produtos já existentes (idempotência)
    existentes = {r[0] for r in db.execute(
        "SELECT codigo_barras FROM alimentos_industrializados WHERE codigo_barras IS NOT NULL")}

    # colunas extras do motor (presentes só se o DDL de industrializados_no_motor.sql rodou)
    extras_cols = []
    if tem_colunas_motor:
        extras_cols = ["porcao_padrao_g", "tipo_prato_id"]
    cols = ["codigo_barras", "nome", "marca", "fabricante", "peso_liquido",
            "unidade_peso", "porcao_qtd", "porcao_unidade",
            "energia_kcal", "carboidratos_g", "acucares_totais_g",
            "acucares_adicionados_g", "proteinas_g", "gorduras_totais_g",
            "gorduras_saturadas_g", "gorduras_trans_g", "fibras_g", "sodio_mg",
            "ingredientes_lista", "alergenos", "fonte", "versao", "desativado"] + extras_cols
    ins_sql = (f"INSERT INTO alimentos_industrializados ({', '.join(cols)}) "
               f"VALUES ({', '.join('?' * len(cols))})")

    contadores = {"importados": 0, "ja_existente": 0, "codigo_invalido": 0,
                  "pais": 0, "sem_nutri": 0, "sem_energia": 0, "sem_porcao": 0,
                  "sem_nome": 0, "linha_invalida": 0}
    alertas_sanidade = []
    sugestoes = 0
    exemplos = []
    linhas_lidas = 0
    encoding = args.encoding or detectar_encoding(args.csv)

    with open(args.csv, encoding=encoding, errors="replace", newline="") as f:
        primeiro = True
        header = None
        delimitador = None
        for linha_bruta in f:
            if args.limite and linhas_lidas >= args.limite:
                break
            linhas_lidas += 1
            linha = linha_bruta.rstrip("\n").rstrip("\r")
            if not linha.strip():
                continue
            if primeiro:
                primeiro = False
                delimitador = detectar_delimitador(linha)
                # headers também podem ter quote quebrada; tratar igual
                header = parse_linha(linha, 0, delimitador)
                if header is None:
                    header = next(csv.reader(io.StringIO(linha), delimiter=delimitador))
                header = [h.strip() for h in header]
                if "code" not in header:
                    sys.exit(f"ERRO: CSV sem coluna 'code' (headers: {header[:8]}...)")
                n_colunas = len(header)
                tem_pais = any(c in header for c in ("countries", "countries_tags", "countries_en"))
                if not tem_pais:
                    print("AVISO: sem colunas de país no header — filtro de país desativado "
                          "(assume que a extração já filtrou Brazil)")
                continue
            campos = parse_linha(linha, n_colunas, delimitador)
            if campos is None:
                contadores["linha_invalida"] += 1
                continue
            row = dict(zip(header, campos))

            # 1. código
            codigo = so_digitos(row.get("code"))
            if not (8 <= len(codigo) <= 14):
                contadores["codigo_invalido"] += 1
                continue
            # 2. país Brasil (só se o CSV tiver as colunas — filtrado antes pode não ter)
            if tem_pais:
                paises = " ".join([row.get("countries_tags") or "",
                                   row.get("countries_en") or "",
                                   row.get("countries") or ""]).lower()
                if "brazil" not in paises:
                    contadores["pais"] += 1
                    continue
            # 3. tem tabela nutricional
            if str(row.get("no_nutrition_data") or "").strip() == "1":
                contadores["sem_nutri"] += 1
                continue
            # 4. energia
            energia = float_or_none(row.get("energy-kcal_100g"))
            if energia is None or energia <= 0:
                contadores["sem_energia"] += 1
                continue
            # 5. porção
            porcao = float_or_none(row.get("serving_quantity"))
            if porcao is None or porcao <= 0:
                contadores["sem_porcao"] += 1
                continue
            # 6. nome
            nome = norm_name(row.get("product_name") or row.get("abbreviated_product_name")
                             or row.get("generic_name"), 200)
            if not nome:
                contadores["sem_nome"] += 1
                continue
            # 7. idempotência
            if codigo in existentes:
                contadores["ja_existente"] += 1
                continue

            # conversão 100g -> porção
            fator = porcao / 100.0
            valores = [converter(row, off, fator) for off, _ in NUTRIENTES_OFF]

            # sanidade Atwater (base 100g, quando os 3 macros existem)
            carb = float_or_none(row.get("carbohydrates_100g"))
            prot = float_or_none(row.get("proteins_100g"))
            fat = float_or_none(row.get("fat_100g"))
            if carb is not None and prot is not None and fat is not None:
                esperado = 4 * carb + 4 * prot + 9 * fat
                if esperado > 0 and abs(energia - esperado) / esperado > 0.25:
                    alertas_sanidade.append((codigo, nome))

            # porção em ml? (liquidos: '1 xícara (240 ml)')
            tamanho = str(row.get("serving_size") or "").lower()
            unidade_porcao = "ml" if re.search(r"\bml\b", tamanho) else "g"

            # peso líquido
            peso = float_or_none(row.get("product_quantity"))
            unidade_peso = None
            if peso is None:
                m = re.search(r"([\d.,]+)\s*(g|ml|kg|l)\b", str(row.get("quantity") or "").lower())
                if m:
                    try:
                        peso = float(m.group(1).replace(",", "."))
                    except ValueError:
                        peso = None
                    if peso is not None:
                        un = m.group(2)
                        if un == "kg":
                            peso, unidade_peso = peso * 1000.0, "g"
                        elif un == "l":
                            peso, unidade_peso = peso * 1000.0, "ml"
                        else:
                            unidade_peso = un
            else:
                unidade_peso = "g"

            marca = norm_name((row.get("brands") or "").split(",")[0].strip(), 100)
            fabricante = norm_name(row.get("brand_owner"), 150)
            lista_ing = str(row.get("ingredients_text") or "").strip() or None
            alergenos = alergenos_json(row.get("allergens_en"))

            if tem_colunas_motor:
                sugestao = sugerir_tipo(row, mapa_tipos)
                if sugestao:
                    sugestoes += 1
                extras = [round(porcao, 2), sugestao if args.sugerir_tipos else None]
            else:
                extras = []

            valores_linha = [
                codigo, nome, marca, fabricante, peso, unidade_peso,
                round(porcao, 2), unidade_porcao,
            ] + valores + [lista_ing, alergenos, FONTE, 1, 0] + extras

            if not args.seco:
                db.execute(ins_sql, valores_linha)
            contadores["importados"] += 1
            if len(exemplos) < 5:
                exemplos.append((codigo, nome, marca, valores[0]))
            if not args.seco:
                existentes.add(codigo)

    if not args.seco:
        db.commit()
    db.close()
    return contadores, alertas_sanidade, exemplos, sugestoes, linhas_lidas


def main():
    ap = argparse.ArgumentParser(description="Importa dump CSV do Open Food Facts "
                                             "para alimentos_industrializados (doc: docs/importacao_openfoodfacts.md)")
    ap.add_argument("--csv", required=True, help="caminho do dump CSV do OFF")
    ap.add_argument("--db", default=str(DEFAULT_DB), help="banco SQLite (default: cardapio_hospitalar.db)")
    ap.add_argument("--limite", type=int, default=0, help="testar só as N primeiras linhas (0 = todas)")
    ap.add_argument("--seco", action="store_true", help="dry-run: nenhum INSERT; só relatório")
    ap.add_argument("--sugerir-tipos", action="store_true",
                    help="grava tipo_prato_id sugerido (sem a flag, sugestões só aparecem no relatório)")
    ap.add_argument("--encoding", default=None,
                    help="forçar encoding do CSV (default: auto-detect utf-8/cp1252/cp850)")
    args = ap.parse_args()

    c, alertas, exemplos, sugestoes, linhas = importar(args)

    print(f"Linhas lidas: {linhas}")
    print(f"Importados: {c['importados']}  |  Já existentes: {c['ja_existente']}")
    print("Descartados: "
          f"pais={c['pais']} sem_nutri={c['sem_nutri']} sem_energia={c['sem_energia']} "
          f"sem_porcao={c['sem_porcao']} codigo_invalido={c['codigo_invalido']} "
          f"sem_nome={c['sem_nome']} linha_invalida={c['linha_invalida']}")
    print(f"Sugestões tipo_prato: {sugestoes}"
          + (" (aplicadas)" if args.sugerir_tipos else " (use --sugerir-tipos para gravar)"))
    if alertas:
        print(f"Alertas sanidade kcal (>25% vs Atwater): {len(alertas)} — ex.:")
        for cod, nome in alertas[:5]:
            print(f"  {cod} {nome}")
    if exemplos:
        print("Exemplos importados:")
        for cod, nome, marca, kcal in exemplos:
            print(f"  {cod} | {nome} | {marca or '-'} | {kcal} kcal/porção")


if __name__ == "__main__":
    main()
