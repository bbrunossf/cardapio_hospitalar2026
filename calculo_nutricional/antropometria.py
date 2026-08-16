"""
Antropometria — IMC, peso ideal e percentual de gordura.

Fórmulas:
  IMC = peso ÷ altura²  (classificação OMS: <18.5 baixo, 18.5–24.9 normal,
                         25–29.9 sobrepeso, ≥30 obesidade)
  Peso ideal (Devine): M 50 + 0.91×(altura−152.4) · F 45.5 + 0.91×(altura−152.4)
  % gordura (Deurenberg): 1.20×IMC + 0.23×idade − 10.8×sexo − 5.4  (M=1, F=0)
"""
from __future__ import annotations

CLASSIFICACOES_IMC = (
    ("baixo_peso", 0, 18.5),
    ("normal", 18.5, 25.0),
    ("sobrepeso", 25.0, 30.0),
    ("obesidade", 30.0, float("inf")),
)


def calcular_imc(peso_kg: float, altura_cm: float) -> float:
    """IMC = peso (kg) ÷ altura² (m)."""
    if not peso_kg or peso_kg <= 0:
        raise ValueError(f"peso_kg inválido: {peso_kg!r}")
    if not altura_cm or altura_cm <= 0:
        raise ValueError(f"altura_cm inválida: {altura_cm!r}")
    altura_m = altura_cm / 100
    return round(peso_kg / (altura_m ** 2), 1)


def classificar_imc(imc: float) -> str:
    """Classificação OMS do IMC."""
    for nome, lim_inf, lim_sup in CLASSIFICACOES_IMC:
        if lim_inf <= imc < lim_sup:
            return nome
    return "obesidade"


def peso_ideal(sexo: str, altura_cm: float) -> float:
    """
    Peso ideal pela fórmula de Devine.
    M: 50 + 0.91×(altura−152.4) · F: 45.5 + 0.91×(altura−152.4)
    """
    if not altura_cm or altura_cm <= 0 or altura_cm > 250:
        raise ValueError(f"altura_cm inválida: {altura_cm!r}")
    if str(sexo or "M").upper() == "M":
        return round(50 + 0.91 * (altura_cm - 152.4), 1)
    return round(45.5 + 0.91 * (altura_cm - 152.4), 1)


def percentual_gordura(sexo: str, imc: float, idade: int) -> float:
    """
    % de gordura pela fórmula de Deurenberg (1991):
    1.20×IMC + 0.23×idade − 10.8×sexo − 5.4   (homem sexo=1, mulher sexo=0)
    """
    if not imc or imc <= 0:
        raise ValueError(f"imc inválido: {imc!r}")
    if not idade or idade < 1 or idade > 120:
        raise ValueError(f"idade inválida: {idade!r}")
    sexo_num = 1 if str(sexo or "M").upper() == "M" else 0
    return round(1.20 * imc + 0.23 * idade - 10.8 * sexo_num - 5.4, 1)
