"""
Validação clínica — faixas plausíveis + alertas.

Não bloqueia o cálculo (usa defaults), apenas acumula alertas que vão para o
campo `alertas` do plano — o nutricionista vê o aviso e decide.
"""
from __future__ import annotations

IMC_MIN = 10.0
IMC_MAX = 60.0
META_KCAL_MIN = 800.0
META_KCAL_MAX = 5000.0
DEFICIT_MAX = -1000.0
SUPERAVIT_MAX = 1000.0
PRAZO_MIN_PARA_VARIACAO = 14


def validar_dados(peso_kg: float, altura_cm: float, idade: int, sexo: str = "M",
                  objetivo: str = "manter", prazo_dias: int | None = None) -> list[str]:
    """
    Retorna lista de alertas clínicos (vazia se tudo plausível).
    """
    alertas: list[str] = []

    if not peso_kg or peso_kg <= 0:
        alertas.append("Peso ausente/zerado — TMB/GET calculados com peso 0 (resultado inválido).")
        return alertas
    if not altura_cm or altura_cm <= 0:
        alertas.append("Altura ausente/zerada — TMB/GET calculados com altura 0 (resultado inválido).")
        return alertas

    imc = peso_kg / ((altura_cm / 100) ** 2)
    if imc < IMC_MIN or imc > IMC_MAX:
        alertas.append(f"IMC {imc:.1f} fora da faixa plausível ({IMC_MIN:.0f}–{IMC_MAX:.0f}) — "
                       "confira peso/altura cadastrados.")

    if not idade or idade < 1 or idade > 120:
        alertas.append(f"Idade {idade!r} fora da faixa plausível (1–120) — usado default 30.")

    if objetivo == "perder" and imc < 18.5:
        alertas.append("Paciente com IMC baixo para objetivo de perda — avaliar clinicamente.")
    if objetivo == "ganhar" and imc > 30:
        alertas.append("Paciente com IMC alto para objetivo de ganho — avaliar clinicamente.")

    if prazo_dias is not None and prazo_dias < PRAZO_MIN_PARA_VARIACAO and objetivo != "manter":
        alertas.append(f"Prazo de {prazo_dias} dias é curto — déficit/superávit diário "
                       "provavelmente agressivo.")

    return alertas


def validar_meta(meta_kcal: float, get_kcal: float, deficit: float | None = None) -> list[str]:
    """
    Alertas sobre a meta calórica calculada (chamado após calcular_meta).
    """
    alertas: list[str] = []

    if meta_kcal < META_KCAL_MIN:
        alertas.append(
            f"Meta de {meta_kcal:.0f} kcal/dia está abaixo do mínimo recomendado "
            f"({META_KCAL_MIN:.0f}) — risco de déficit excessivo.")
    if meta_kcal > META_KCAL_MAX:
        alertas.append(
            f"Meta de {meta_kcal:.0f} kcal/dia está acima do máximo recomendado "
            f"({META_KCAL_MAX:.0f}).")

    if deficit is not None:
        if deficit < DEFICIT_MAX:
            alertas.append(
                f"Déficit de {deficit:.0f} kcal/dia é agressivo (recomendado ≥ {DEFICIT_MAX:.0f}).")
        if deficit > SUPERAVIT_MAX and get_kcal > 0:
            alertas.append(
                f"Superávit de {deficit:.0f} kcal/dia é agressivo (recomendado ≤ {SUPERAVIT_MAX:.0f}).")

    return alertas
