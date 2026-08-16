"""
Cálculos nutricionais locais — substituto determinístico da WolframAlpha.

Pacote puro Python (stdlib) com fórmulas fechadas, públicas e estáveis:

  tmb.py           — Mifflin-St Jeor, Harris-Benedict, Katch-McArdle
  get.py           — GET = TMB × fator de atividade
  meta.py          — déficit/superávit, prazo, meta_kcal, projeção de peso
  macros.py        — distribuição por perfil (30/40/30 etc.)
  antropometria.py — IMC, peso ideal (Devine), % gordura (Deurenberg)
  validador.py     — faixas clínicas plausíveis + alertas

Uso principal (mesmo contrato do WolframDietClient.calcular_plano_completo):

    from calculo_nutricional import calcular_plano_completo
    resultado = calcular_plano_completo(dados, meta)
"""
from __future__ import annotations

from .antropometria import calcular_imc, classificar_imc, percentual_gordura, peso_ideal
from .get import FATORES_ATIVIDADE, calcular_get, fator_atividade
from .macros import PERFIS_MACRO, distribuir_macros
from .meta import KCAL_POR_KG, calcular_meta, estimar_prazo, projecao_peso
from .tmb import (METODOS_TMB, calcular_tmb, calcular_tmb_harris_benedict,
                  calcular_tmb_katch_mcardle, calcular_tmb_mifflin)
from .validador import validar_dados

__all__ = [
    "calcular_plano_completo",
    # tmb
    "calcular_tmb", "calcular_tmb_mifflin", "calcular_tmb_harris_benedict",
    "calcular_tmb_katch_mcardle", "METODOS_TMB",
    # get
    "calcular_get", "fator_atividade", "FATORES_ATIVIDADE",
    # meta
    "calcular_meta", "estimar_prazo", "projecao_peso", "KCAL_POR_KG",
    # macros
    "distribuir_macros", "PERFIS_MACRO",
    # antropometria
    "calcular_imc", "classificar_imc", "peso_ideal", "percentual_gordura",
    # validador
    "validar_dados",
]


def calcular_plano_completo(dados: dict, meta: dict) -> dict:
    """
    Orquestra TMB → GET → Meta → Macros com cálculo 100% local.

    Contrato de entrada (idêntico ao WolframDietClient):
      dados: {sexo: 'M'|'F', idade: int, altura_cm: float, peso_kg: float,
              nivel_atividade_fisica: str}
      meta:  {objetivo: 'perder'|'ganhar'|'manter', peso_alvo_kg?: float,
              prazo_dias?: int, deficit_diario_kcal?: float, perfil_macro?: str}

    Retorno (mesmo formato do cliente Wolfram, pronto para planos_nutricionais):
      tmb_kcal, get_kcal, meta_kcal, deficit_diario_kcal, prazo_dias,
      proteinas_g, carboidratos_g, lipidios_g,
      proteinas_pct, carboidratos_pct, lipidios_pct,
      fonte='local', alertas=[...],
      consultas=[{query, api:'local', resposta, ok}, ...]  # auditoria
      metodo_tmb='mifflin_st_jeor'
    """
    alertas: list[str] = []
    consultas: list[dict] = []

    # ── Entradas com defaults seguros ────────────────────────────────
    sexo = str(dados.get("sexo") or "M")
    idade = int(dados.get("idade") or 30)
    altura_cm = float(dados.get("altura_cm") or 0)
    peso_kg = float(dados.get("peso_kg") or 0)
    nivel = (dados.get("nivel_atividade_fisica") or "moderado").strip().lower()

    objetivo = str(meta.get("objetivo") or "").strip().lower()
    peso_alvo = float(meta.get("peso_alvo_kg") or peso_kg)
    prazo_dias = meta.get("prazo_dias")
    deficit = meta.get("deficit_diario_kcal")
    perfil = (meta.get("perfil_macro") or "equilibrado").strip().lower()

    # ── Pré-validação clínica ─────────────────────────────────────────
    alertas.extend(validar_dados(
        peso_kg=peso_kg, altura_cm=altura_cm, idade=idade,
        sexo=sexo, objetivo=objetivo, prazo_dias=prazo_dias,
    ))

    # ── TMB (Mifflin-St Jeor, padrão clínico) ─────────────────────────
    tmb = calcular_tmb(sexo=sexo, peso_kg=peso_kg, altura_cm=altura_cm, idade=idade)
    consultas.append({
        "query": f"tmb_mifflin_st_jeor {sexo} {idade}y {altura_cm:g}cm {peso_kg:g}kg",
        "api": "local", "resposta": f"{tmb:.2f}", "ok": True,
    })

    # ── GET (TMB × fator de atividade) ────────────────────────────────
    get = calcular_get(tmb=tmb, nivel=nivel)
    consultas.append({
        "query": f"get_tmb_x_fator nivel={nivel}",
        "api": "local", "resposta": f"{get:.2f}", "ok": True,
    })

    # ── Meta calórica + déficit + prazo ───────────────────────────────
    meta_calc = calcular_meta(
        objetivo=objetivo,
        get_kcal=get,
        peso_atual=peso_kg,
        peso_alvo=peso_alvo,
        prazo_dias=prazo_dias,
        deficit_diario_kcal=deficit,
    )
    alertas.extend(meta_calc["alertas"])
    consultas.append({
        "query": f"meta objetivo={objetivo} get={get:.0f} alvo={peso_alvo:g}",
        "api": "local",
        "resposta": (f"meta={meta_calc['meta_kcal']:.0f} "
                     f"deficit={meta_calc['deficit_diario_kcal']:.0f} "
                     f"prazo={meta_calc['prazo_dias']}"),
        "ok": True,
    })

    # ── Macros (distribuição por perfil) ──────────────────────────────
    macros = distribuir_macros(meta_kcal=meta_calc["meta_kcal"], perfil=perfil)
    consultas.append({
        "query": f"macros perfil={perfil} meta={meta_calc['meta_kcal']:.0f}",
        "api": "local",
        "resposta": (f"P {macros['proteinas_pct']}% ({macros['proteinas_g']}g) "
                     f"C {macros['carboidratos_pct']}% ({macros['carboidratos_g']}g) "
                     f"L {macros['lipidios_pct']}% ({macros['lipidios_g']}g)"),
        "ok": True,
    })

    return {
        "tmb_kcal": round(tmb, 0),
        "get_kcal": round(get, 0),
        "meta_kcal": round(meta_calc["meta_kcal"], 0),
        "deficit_diario_kcal": round(meta_calc["deficit_diario_kcal"], 0),
        "prazo_dias": meta_calc["prazo_dias"],
        "proteinas_g": macros["proteinas_g"],
        "carboidratos_g": macros["carboidratos_g"],
        "lipidios_g": macros["lipidios_g"],
        "proteinas_pct": macros["proteinas_pct"],
        "carboidratos_pct": macros["carboidratos_pct"],
        "lipidios_pct": macros["lipidios_pct"],
        "fonte": "local",
        "alertas": alertas,
        "consultas": consultas,
        "metodo_tmb": "mifflin_st_jeor",
    }
