"""
GET — Gasto Energético Total (kcal/dia).

GET = TMB × fator de atividade física.

Níveis (mesmos do formulário do paciente):
  sedentario 1.2 | leve 1.375 | moderado 1.55 | intenso 1.725 | atleta 1.9
"""
from __future__ import annotations

FATORES_ATIVIDADE = {
    "sedentario": 1.2,
    "leve": 1.375,
    "moderado": 1.55,
    "intenso": 1.725,
    "atleta": 1.9,
}

NIVEIS_VALIDOS = tuple(FATORES_ATIVIDADE.keys())


def fator_atividade(nivel: str | None) -> float:
    """Fator do nível de atividade (default: moderado 1.55)."""
    chave = (nivel or "moderado").strip().lower()
    if chave not in FATORES_ATIVIDADE:
        raise ValueError(
            f"nível de atividade inválido: {chave!r} (disponíveis: {NIVEIS_VALIDOS})")
    return FATORES_ATIVIDADE[chave]


def calcular_get(tmb: float, nivel: str | None = "moderado") -> float:
    """GET = TMB × fator de atividade."""
    if not tmb or tmb <= 0:
        raise ValueError(f"tmb inválida: {tmb!r}")
    return tmb * fator_atividade(nivel)
