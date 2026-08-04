"""Controle de duplicidade de alimentos industrializados (seção 8)."""
from rapidfuzz import fuzz
from sqlalchemy import func
from extensions import db
from models_rotulo import AlimentoIndustrializado


LIMIAR_SIMILARIDADE = 88


def buscar_por_ean(ean: str) -> AlimentoIndustrializado | None:
    """Busca alimento pelo código de barras (exato)."""
    ean_limpo = "".join(c for c in str(ean) if c.isdigit())
    if not ean_limpo:
        return None
    return (
        db.session.query(AlimentoIndustrializado)
        .filter(AlimentoIndustrializado.codigo_barras == ean_limpo)
        .filter(AlimentoIndustrializado.desativado == False)
        .first()
    )


def buscar_duplicatas(dados: dict) -> list[dict]:
    """
    Busca duplicatas por EAN (exato) ou fuzzy (nome + marca + peso).
    Retorna lista de dicts {id, nome, marca, peso_liquido, similaridade}.
    """
    ean = dados.get("codigo_barras")
    if ean:
        existente = buscar_por_ean(ean)
        if existente:
            return [_formatar_duplicata(existente, 1.0)]

    nome_novo = (dados.get("nome") or "").strip()
    marca_nova = (dados.get("marca") or "").strip().lower()
    peso_novo = _parse_peso(dados.get("peso_liquido"))

    if not nome_novo:
        return []

    candidatos = (
        db.session.query(AlimentoIndustrializado)
        .filter(AlimentoIndustrializado.desativado == False)
        .all()
    )

    duplicatas = []
    for cand in candidatos:
        nome_cand = (cand.nome or "").strip()
        if not nome_cand:
            continue

        similaridade = fuzz.token_set_ratio(nome_novo.lower(), nome_cand.lower())
        if similaridade < LIMIAR_SIMILARIDADE:
            continue

        marca_cand = (cand.marca or "").strip().lower()
        if marca_nova and marca_cand and marca_nova != marca_cand:
            continue

        # Se houver peso líquido nos dois, exige diferença ≤ 10%
        peso_cand = float(cand.peso_liquido) if cand.peso_liquido is not None else None
        if peso_novo is not None and peso_cand is not None:
            if peso_cand == 0 or abs(peso_novo - peso_cand) / peso_cand > 0.10:
                continue

        duplicatas.append(_formatar_duplicata(cand, similaridade / 100.0))

    # Ordena por similaridade decrescente
    duplicatas.sort(key=lambda x: x["similaridade"], reverse=True)
    return duplicatas


def _formatar_duplicata(alimento: AlimentoIndustrializado, similaridade: float) -> dict:
    peso = float(alimento.peso_liquido) if alimento.peso_liquido is not None else None
    return {
        "id": alimento.id,
        "nome": alimento.nome,
        "marca": alimento.marca,
        "peso_liquido": peso,
        "similaridade": round(similaridade, 2),
    }


def _parse_peso(peso: dict | None) -> float | None:
    if not peso:
        return None
    valor = peso.get("valor")
    if valor is None:
        return None
    try:
        return float(valor)
    except (ValueError, TypeError):
        return None
