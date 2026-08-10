"""
Distribuição de macronutrientes por perfil.

Percentuais (prot, carb, lip) e conversão para gramas:
  proteína/carboidrato: 4 kcal/g · lipídio: 9 kcal/g
"""
from __future__ import annotations

PERFIS_MACRO = {
    "equilibrado": (30, 40, 30),
    "hipocalorico": (30, 30, 40),     # low carb
    "hiperproteico": (35, 35, 30),
    "hipolipidico": (25, 50, 25),
}

KCAL_POR_G = {"proteina": 4.0, "carboidrato": 4.0, "lipidio": 9.0}


def distribuir_macros(meta_kcal: float, perfil: str = "equilibrado") -> dict:
    """
    Calcula gramas e percentuais de macros para a meta calórica.

    Retorno:
      {
        'proteinas_pct': float, 'carboidratos_pct': float, 'lipidios_pct': float,
        'proteinas_g': float, 'carboidratos_g': float, 'lipidios_g': float,
        'fonte': 'local',
      }
    """
    if not meta_kcal or meta_kcal <= 0:
        raise ValueError(f"meta_kcal inválida: {meta_kcal!r}")
    perfil = (perfil or "equilibrado").strip().lower()
    if perfil not in PERFIS_MACRO:
        raise ValueError(f"perfil inválido: {perfil!r} (disponíveis: {sorted(PERFIS_MACRO)})")

    p_pct, c_pct, l_pct = PERFIS_MACRO[perfil]
    return {
        "proteinas_pct": p_pct,
        "carboidratos_pct": c_pct,
        "lipidios_pct": l_pct,
        "proteinas_g": round(meta_kcal * p_pct / 100 / KCAL_POR_G["proteina"], 1),
        "carboidratos_g": round(meta_kcal * c_pct / 100 / KCAL_POR_G["carboidrato"], 1),
        "lipidios_g": round(meta_kcal * l_pct / 100 / KCAL_POR_G["lipidio"], 1),
        "fonte": "local",
    }
