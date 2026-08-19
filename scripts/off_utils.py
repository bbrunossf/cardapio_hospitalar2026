#!/usr/bin/env python3
"""Utilitários compartilhados pelos scripts de Open Food Facts (novo_cardapio).

Cobre os formatos reais do CSV filtrado pelo Bruno:
- delimitador ';' ou ',' (auto-detect no header)
- números com vírgula decimal pt-BR ("380,00") ou ponto ("20.5")
- encoding UTF-8 / CP1252 / CP850 (auto-detect) — CSVs do Excel BR saem em CP850/CP1252
- trailing delimiter ("campo;") — normaliza campo vazio final
"""
import csv
import io

MOJIBAKE = set("¢‚„†‡‰Š‹ŒŽ™š›œžŸ")


def parse_num(raw):
    """float tolerante a formato pt-BR (vírgula decimal) e negativo = None."""
    s = str(raw or "").strip()
    if not s:
        return None
    if "," in s:
        # 1.000,50 -> 1000.50 ; 380,00 -> 380.00
        s = s.replace(".", "").replace(",", ".")
    try:
        v = float(s)
    except ValueError:
        return None
    return None if v < 0 else v


def detectar_delimitador(linha_header):
    """'a;b;c' -> ';' ; 'a,b,c' -> ','. Conteúdo do header não tem vírgulas no OFF."""
    pv = linha_header.count(";")
    vg = linha_header.count(",")
    return ";" if pv >= vg and pv > 0 else ","


def detectar_encoding(path):
    """utf-8 se válido; senão cp1252 vs cp850 — escolhe o com menos mojibake (ex.: '¢','‚')."""
    with open(path, "rb") as f:
        amostra = f.read(8192)
    try:
        amostra.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        pass
    candidatos = []
    for enc in ("cp1252", "cp850"):
        try:
            texto = amostra.decode(enc)
        except UnicodeDecodeError:
            continue
        candidatos.append((enc, sum(1 for ch in texto if ch in MOJIBAKE)))
    if not candidatos:
        return "cp1252"
    return min(candidatos, key=lambda x: x[1])[0]


def parse_linha(linha, n_colunas, delimitador):
    """Uma linha do CSV pode ter quotes quebradas (dump OFF) e trailing delimiter.
    Retorna lista de campos (truncada se o trailing gerar campos vazios) ou None."""
    try:
        campos = next(csv.reader(io.StringIO(linha), delimiter=delimitador))
    except csv.Error:
        return None
    if len(campos) == n_colunas:
        return campos
    # trailing delimiter: 'a;b;' -> ['a','b',''] -> aceitar truncando
    if len(campos) > n_colunas and all(c == "" for c in campos[n_colunas:]):
        return campos[:n_colunas]
    return None
