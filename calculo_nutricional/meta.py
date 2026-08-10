"""
Meta calórica, déficit/superávit, prazo e projeção de peso.

Regra de energia: 1 kg de massa corporal ≈ 7700 kcal (Wishnofsky).

Comportamento espelha o fallback local que a Wolfram usava (RT-003), agora como
fonte primária determinística:
  - Com prazo:      deficit = ∓(diff_kg × 7700 ÷ prazo_dias);  meta = GET + deficit
  - Sem prazo:      deficit informado ou padrão (perder −500, ganhar +300, manter 0);
                    meta = GET + deficit; prazo = round(diff_kg × 7700 ÷ |deficit|)
  - Manter:         deficit = 0; meta = GET
"""
from __future__ import annotations

KCAL_POR_KG = 7700.0

DEFICIT_PADRAO = {"perder": -500.0, "ganhar": 300.0, "manter": 0.0}


def _round_int(valor: float) -> int:
    return max(1, int(round(valor)))


def estimar_prazo(diff_kg: float, deficit: float, objetivo: str = "perder") -> int | None:
    """
    Dias até o objetivo: diff_kg × 7700 ÷ |deficit|.
    Retorna None se diff_kg <= 0 ou deficit == 0 (ou objetivo 'manter').
    """
    if objetivo == "manter" or diff_kg <= 0 or deficit == 0:
        return None
    return _round_int(diff_kg * KCAL_POR_KG / abs(deficit))


def calcular_meta(objetivo: str, get_kcal: float, peso_atual: float,
                  peso_alvo: float | None = None, prazo_dias: int | None = None,
                  deficit_diario_kcal: float | None = None) -> dict:
    """
    Calcula meta calórica diária + déficit/superávit + prazo.

    Retorno:
      {
        'meta_kcal': float, 'deficit_diario_kcal': float, 'prazo_dias': int|None,
        'alertas': [str, ...], 'fonte': 'local',
      }
    """
    alertas: list[str] = []
    objetivo = (objetivo or "").strip().lower()
    if objetivo not in DEFICIT_PADRAO:
        raise ValueError(f"objetivo inválido: {objetivo!r} (perder|ganhar|manter)")

    peso_atual = float(peso_atual or 0)
    peso_alvo = float(peso_alvo) if peso_alvo is not None else peso_atual
    diff_kg = abs(peso_alvo - peso_atual)

    deficit: float
    if deficit_diario_kcal is not None:
        deficit = float(deficit_diario_kcal)
    elif objetivo == "manter":
        deficit = 0.0
    else:
        deficit = DEFICIT_PADRAO[objetivo]

    # Manter: sempre meta = GET
    if objetivo == "manter":
        return {
            "meta_kcal": round(get_kcal, 0),
            "deficit_diario_kcal": 0.0,
            "prazo_dias": None,
            "alertas": [],
            "fonte": "local",
        }

    # Com prazo explícito → déficit derivado do prazo (7700 kcal/kg)
    if prazo_dias:
        prazo_dias = int(prazo_dias)
        if prazo_dias < 1:
            raise ValueError(f"prazo_dias inválido: {prazo_dias}")
        deficit_calc = -(diff_kg * KCAL_POR_KG / prazo_dias) if objetivo == "perder" \
            else (diff_kg * KCAL_POR_KG / prazo_dias)
        meta_kcal = get_kcal + deficit_calc
        if diff_kg > 0 and prazo_dias < 14:
            alertas.append(
                f"Prazo curto ({prazo_dias} dias) para variação de {diff_kg:.1f} kg — "
                "déficit/superávit agressivo; avaliar risco.")
        return {
            "meta_kcal": round(meta_kcal, 0),
            "deficit_diario_kcal": round(deficit_calc, 0),
            "prazo_dias": prazo_dias,
            "alertas": alertas,
            "fonte": "local",
        }

    # Sem prazo → déficit (informado ou padrão) e prazo estimado
    meta_kcal = get_kcal + deficit
    prazo = estimar_prazo(diff_kg, deficit, objetivo)
    if diff_kg > 0 and deficit < -1000:
        alertas.append(
            f"Déficit de {deficit:.0f} kcal/dia é agressivo (recomendado ≥ -1000).")
    if diff_kg > 0 and deficit > 1000:
        alertas.append(
            f"Superávit de {deficit:.0f} kcal/dia é agressivo (recomendado ≤ 1000).")
    return {
        "meta_kcal": round(meta_kcal, 0),
        "deficit_diario_kcal": round(deficit, 0),
        "prazo_dias": prazo,
        "alertas": alertas,
        "fonte": "local",
    }


def projecao_peso(peso_inicial: float, meta_kcal: float, get_kcal: float,
                  dias: int, passo_dias: int = 7) -> list[dict]:
    """
    Série temporal de peso projetado (para o simulador d3, Fase 2).

    peso(dia) = peso_inicial + (meta_kcal − get_kcal) × dia ÷ 7700

    Retorna [{dia, peso_kg, meta_kcal, get_kcal}, ...] a cada passo_dias
    (default: semanal), incluindo o dia 0 (estado inicial).
    """
    if dias < 1:
        raise ValueError(f"dias inválido: {dias}")
    if passo_dias < 1:
        raise ValueError(f"passo_dias inválido: {passo_dias}")
    delta_diario = (float(meta_kcal) - float(get_kcal)) / KCAL_POR_KG
    serie = [{"dia": 0, "peso_kg": round(float(peso_inicial), 2),
              "meta_kcal": float(meta_kcal), "get_kcal": float(get_kcal)}]
    dia = passo_dias
    while dia <= dias:
        serie.append({
            "dia": dia,
            "peso_kg": round(float(peso_inicial) + delta_diario * dia, 2),
            "meta_kcal": float(meta_kcal),
            "get_kcal": float(get_kcal),
        })
        dia += passo_dias
    if serie[-1]["dia"] != dias:
        serie.append({
            "dia": dias,
            "peso_kg": round(float(peso_inicial) + delta_diario * dias, 2),
            "meta_kcal": float(meta_kcal),
            "get_kcal": float(get_kcal),
        })
    return serie
