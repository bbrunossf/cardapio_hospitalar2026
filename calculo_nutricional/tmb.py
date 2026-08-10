"""
TMB — Taxa Metabólica Basal (kcal/dia).

Fórmulas implementadas:
  - Mifflin-St Jeor (1990)         — padrão clínico atual (default)
  - Harris-Benedict revisada (1984)
  - Harris-Benedict original (1919)
  - Katch-McArdle                  — usa massa magra (precisa % gordura ou LBM)

Referências:
  Mifflin MD et al. Am J Clin Nutr 1990;51(2):241-7.
  Roza AM, Shizgal HM. Am J Clin Nutr 1984;40(1):168-82.
  Katch FI, McArdle WD. Nutrition, Weight Control, and Exercise. 1983.
"""
from __future__ import annotations

import math

METODOS_TMB = ("mifflin_st_jeor", "harris_benedict_1984", "harris_benedict_1919", "katch_mcardle")


def _validar_entradas(peso_kg: float, altura_cm: float, idade: int) -> None:
    if not peso_kg or peso_kg <= 0 or peso_kg > 500:
        raise ValueError(f"peso_kg inválido: {peso_kg!r}")
    if not altura_cm or altura_cm <= 0 or altura_cm > 250:
        raise ValueError(f"altura_cm inválida: {altura_cm!r}")
    if not idade or idade < 1 or idade > 120:
        raise ValueError(f"idade inválida: {idade!r}")


def _eh_homem(sexo: str) -> bool:
    return str(sexo or "M").upper() == "M"


def calcular_tmb_mifflin(sexo: str, peso_kg: float, altura_cm: float, idade: int) -> float:
    """
    Mifflin-St Jeor (1990).

    Homens: 10×peso + 6.25×altura − 5×idade + 5
    Mulheres: 10×peso + 6.25×altura − 5×idade − 161
    """
    _validar_entradas(peso_kg, altura_cm, idade)
    base = (10 * peso_kg) + (6.25 * altura_cm) - (5 * idade)
    return base + 5 if _eh_homem(sexo) else base - 161


def calcular_tmb_harris_benedict(sexo: str, peso_kg: float, altura_cm: float, idade: int,
                                 revisada: bool = True) -> float:
    """
    Harris-Benedict.

    Revisada (1984):
      M: 88.362 + 13.397×peso + 4.799×altura − 5.677×idade
      F: 447.593 + 9.247×peso + 3.098×altura − 4.330×idade
    Original (1919):
      M: 66.473 + 13.7516×peso + 5.0033×altura − 6.755×idade
      F: 655.0955 + 9.5634×peso + 1.8496×altura − 4.6756×idade
    """
    _validar_entradas(peso_kg, altura_cm, idade)
    if _eh_homem(sexo):
        if revisada:
            return 88.362 + (13.397 * peso_kg) + (4.799 * altura_cm) - (5.677 * idade)
        return 66.473 + (13.7516 * peso_kg) + (5.0033 * altura_cm) - (6.755 * idade)
    if revisada:
        return 447.593 + (9.247 * peso_kg) + (3.098 * altura_cm) - (4.330 * idade)
    return 655.0955 + (9.5634 * peso_kg) + (1.8496 * altura_cm) - (4.6756 * idade)


def calcular_tmb_katch_mcardle(massa_magra_kg: float) -> float:
    """
    Katch-McArdle: 370 + 21.6 × massa_magra_kg.

    Precisa da massa magra (LBM). Se tiver % gordura, LBM = peso × (1 − %gordura/100).
    """
    if not massa_magra_kg or massa_magra_kg <= 0 or massa_magra_kg > 300:
        raise ValueError(f"massa_magra_kg inválida: {massa_magra_kg!r}")
    return 370 + (21.6 * massa_magra_kg)


def calcular_tmb(sexo: str, peso_kg: float, altura_cm: float, idade: int,
                 metodo: str = "mifflin_st_jeor", massa_magra_kg: float | None = None) -> float:
    """
    TMB genérica — escolhe a equação pelo nome.

    metodo:
      'mifflin_st_jeor' (default), 'harris_benedict_1984',
      'harris_benedict_1919', 'katch_mcardle' (exige massa_magra_kg).
    """
    metodo = (metodo or "mifflin_st_jeor").lower()
    if metodo == "mifflin_st_jeor":
        return calcular_tmb_mifflin(sexo, peso_kg, altura_cm, idade)
    if metodo == "harris_benedict_1984":
        return calcular_tmb_harris_benedict(sexo, peso_kg, altura_cm, idade, revisada=True)
    if metodo == "harris_benedict_1919":
        return calcular_tmb_harris_benedict(sexo, peso_kg, altura_cm, idade, revisada=False)
    if metodo == "katch_mcardle":
        if massa_magra_kg is None:
            raise ValueError("katch_mcardle exige massa_magra_kg")
        return calcular_tmb_katch_mcardle(massa_magra_kg)
    raise ValueError(f"metodo de TMB desconhecido: {metodo!r} (disponíveis: {METODOS_TMB})")


# Conveniência: LBM a partir de % gordura
def massa_magra(peso_kg: float, percentual_gordura: float) -> float:
    """Massa magra = peso × (1 − %gordura/100)."""
    if percentual_gordura is None or percentual_gordura < 0 or percentual_gordura >= 100:
        raise ValueError(f"percentual_gordura inválido: {percentual_gordura!r}")
    return round(peso_kg * (1 - percentual_gordura / 100), 2)
