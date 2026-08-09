"""
Cliente WolframAlpha para parâmetros dietéticos personalizados (Módulo 8).

APIs utilizadas (documentação oficial — products.wolframalpha.com):
  - Short Answers API: GET https://api.wolframalpha.com/v1/result?appid=..&i=..&units=metric
      → TMB, GET, meta calórica, estimativa de prazo (1 valor por consulta, texto puro)
  - Full Results API:  GET https://api.wolframalpha.com/v2/query?appid=..&input=..
                        &format=plaintext&includepodid=Result&output=json&units=metric
      → distribuição de macronutrientes (vários valores num pod "Result")

Fallbacks locais (RT-003) quando a API falha ou o parse é impossível:
  - TMB:   Mifflin-St Jeor
  - GET:   TMB × fator de atividade
  - Meta:  déficit total (diff_kg × 7700 kcal/kg) ÷ prazo_dias   [corrigido: usa prazo, não ÷7]
  - Macros: distribuição padrão por perfil (30/40/30 etc.)

Chave: lida de WOLFRAM_ALPHA_APP_ID (ou WOLFRAM_APPID) do ambiente.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time

import requests

logger = logging.getLogger("wolfram")

SHORT_ANSWERS_URL = "https://api.wolframalpha.com/v1/result"
FULL_RESULTS_URL = "https://api.wolframalpha.com/v2/query"

FATORES_ATIVIDADE = {
    "sedentario": 1.2,
    "leve": 1.375,
    "moderado": 1.55,
    "intenso": 1.725,
}
ATIVIDADE_EN = {
    "sedentario": "sedentary",
    "leve": "light",
    "moderado": "moderate",
    "intenso": "intense",
}
ATIVIDADE_PT = {v: k for k, v in ATIVIDADE_EN.items()}

# Rótulos exatos que a Wolfram usa na tabela do pod EnergyExpenditure
NIVEL_PARA_ROTULO_WOLFRAM = {
    "sedentario": "sedentary",
    "leve": "lightly active",
    "moderado": "moderately active",
    "intenso": "very active",
    "atleta": "extra active",
}

# Percentuais padrão por perfil (fallback RF-806 / RT-003): (prot, carb, lip)
PERFIS_MACRO = {
    "equilibrado": (30, 40, 30),
    "hipocalorico": (30, 30, 40),   # low carb
    "hiperproteico": (35, 35, 30),
    "hipolipidico": (25, 50, 25),
}
PERFIL_EN = {
    "equilibrado": "balanced diet",
    "hipocalorico": "low carbohydrate",
    "hiperproteico": "high protein",
    "hipolipidico": "low fat",
}

# Déficit/superávit padrão (kcal/dia) quando não informado — perda ≈ 0,5 kg/semana
DEFICIT_PADRAO = {"perder": -500.0, "ganhar": 300.0, "manter": 0.0}

KCAL_POR_KG = 7700.0  # energia aproximada p/ alterar 1 kg de massa corporal


class ErroWolframAlpha(Exception):
    pass


class ErroConfiguracao(ErroWolframAlpha):
    pass


class ErroAPI(ErroWolframAlpha):
    pass


class ErroParsing(ErroWolframAlpha):
    pass


def _extrair_numero(texto: str, padrao: str | None = None) -> float | None:
    """Extrai o 1º número de um texto. Se padrao for dado, exige-o antes de 'cal'."""
    if not texto:
        return None
    t = texto.lower().replace("~=", "").replace("about", "").strip()
    if padrao:
        m = re.search(rf"({padrao})\s*(?:k?cal|calories|kilocalories)", t)
        if m:
            try:
                return float(m.group(1).replace(",", "."))
            except ValueError:
                return None
    m = re.search(r"(\d+(?:[.,]\d+)?)", t)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", "."))
    except ValueError:
        return None


def _extrair_prazo_dias(texto: str) -> int | None:
    """Extrai prazo de respostas como '10 weeks', '69 days', '2.3 months'."""
    if not texto:
        return None
    t = texto.lower()
    m = re.search(r"(\d+(?:\.\d+)?)\s*(weeks?|days?|months?|years?)", t)
    if not m:
        return None
    valor = float(m.group(1))
    unidade = m.group(2)
    dias = {
        "week": 7, "weeks": 7,
        "day": 1, "days": 1,
        "month": 30, "months": 30,
        "year": 365, "years": 365,
    }[unidade]
    return max(1, int(round(valor * dias)))


class WolframDietClient:
    """Cliente de integração com a WolframAlpha (RF-801 a RF-807, RF-812)."""

    def __init__(self, api_key: str | None = None, timeout: int = 12,
                 cache_enabled: bool = True, cache_ttl: int = 3600,
                 max_retries: int = 2):
        self.api_key = api_key or os.environ.get("WOLFRAM_ALPHA_APP_ID") or os.environ.get("WOLFRAM_APPID")
        if not self.api_key:
            raise ErroConfiguracao("AppID WolframAlpha não configurado (WOLFRAM_ALPHA_APP_ID).")
        self.timeout = timeout
        self.max_retries = max_retries
        self.cache_enabled = cache_enabled
        self.cache_ttl = cache_ttl
        self._cache: dict[str, tuple[float, str]] = {}
        # Acumula as consultas da última operação p/ persistência (wolfram_consultas)
        self.consultas: list[dict] = []

    # ══════════════════════════════════════════════════════════════
    # API pública
    # ══════════════════════════════════════════════════════════════

    def calcular_tmb(self, dados: dict) -> float | None:
        """RF-802: TMB via Short Answers; fallback Mifflin-St Jeor."""
        query = self._query_tmb(dados)
        texto = self._short_answer(query)
        if texto is None:
            return self._fallback_tmb(dados)
        valor = _extrair_numero(texto, r"\d+(?:\.\d+)?")
        return valor if valor else self._fallback_tmb(dados)

    def calcular_get(self, dados: dict) -> float | None:
        """
        RF-803: GET via Full Results (pod EnergyExpenditure — tabela por nível
        de atividade); fallback TMB × fator.

        A Wolfram não interpreta "total daily energy expenditure" como query
        própria (501), mas a query "energy expenditure ..." devolve um pod com
        a tabela de gasto para os 5 níveis de atividade — escolhemos a linha
        correspondente ao nível do paciente.
        """
        query = self._query_get(dados)
        texto = self._full_results(query, pod_ids="EnergyExpenditure")
        if texto is not None:
            valor = self._parse_energy_expenditure(texto, dados.get("nivel_atividade_fisica"))
            if valor:
                return valor
        return self._fallback_get(dados)

    def calcular_meta(self, dados: dict, meta: dict) -> dict:
        """
        RF-804/805: meta calórica diária + déficit/superávit + prazo.

        Entrada meta: {objetivo, peso_alvo_kg, prazo_dias?, deficit_diario_kcal?}
        Regras:
          - Objetivo 'perder' com prazo → Full Results
            "calories to lose weight at X kg per week ..." (pod
            SuggestedCaloricIntake). A Wolfram não aceita "lose 5 kg in 8
            weeks" direto (501) — precisa da taxa semanal.
          - Objetivo 'ganhar' → a Wolfram não interpreta ganho de peso
            (501 em todas as variações testadas) → fallback local
            (7700 kcal/kg ÷ prazo) com alerta.
          - Sem prazo → meta = GET + déficit (informado ou padrão); prazo
            estimado pela API (query inversa) ou localmente.
        """
        objetivo = meta["objetivo"]
        peso_atual = float(dados["peso_kg"])
        peso_alvo = float(meta.get("peso_alvo_kg") or peso_atual)
        diff_kg = abs(peso_alvo - peso_atual)

        get = self.calcular_get(dados) or self._fallback_get(dados)

        prazo_dias = meta.get("prazo_dias")
        deficit = meta.get("deficit_diario_kcal")
        if deficit is not None:
            deficit = float(deficit)
        elif objetivo == "manter":
            deficit = 0.0
        else:
            deficit = DEFICIT_PADRAO.get(objetivo, 0.0)

        resultado = {"get_kcal": round(get, 0), "fonte_meta": "wolfram", "alertas": []}

        if prazo_dias:
            prazo_dias = int(prazo_dias)
            if objetivo == "perder":
                # Taxa semanal: diff_kg ÷ semanas (ex: 5kg em 8 sem → 0.625 kg/sem)
                semanas = max(1, prazo_dias / 7)
                taxa_semanal = diff_kg / semanas
                query = self._query_meta(dados, objetivo, taxa_semanal, semanas)
                texto = self._full_results(query, pod_ids="SuggestedCaloricIntake")
                if texto is not None:
                    meta_kcal = _extrair_numero(texto, r"\d+(?:\.\d+)?")
                    if meta_kcal:
                        resultado["meta_kcal"] = round(meta_kcal, 0)
                        resultado["deficit_diario_kcal"] = round(get - meta_kcal, 0)
                        resultado["prazo_dias"] = prazo_dias
                        return resultado
                resultado["alertas"].append(
                    "Meta via Wolfram indisponível; fallback local (7700 kcal/kg ÷ prazo).")
            else:
                resultado["alertas"].append(
                    "Wolfram não calcula ganho de peso; fallback local (7700 kcal/kg ÷ prazo).")
            # fallback com prazo
            deficit_calc = -(diff_kg * KCAL_POR_KG / prazo_dias) if objetivo == "perder" \
                else (diff_kg * KCAL_POR_KG / prazo_dias) if objetivo == "ganhar" else 0.0
            resultado["deficit_diario_kcal"] = round(deficit_calc, 0)
            resultado["meta_kcal"] = round(get + deficit_calc, 0)
            resultado["prazo_dias"] = prazo_dias
            resultado["fonte_meta"] = "fallback"
            return resultado

        # Sem prazo: usa déficit (informado ou padrão) e estima o prazo
        meta_kcal = get + deficit
        prazo, fonte_prazo = self._estimar_prazo(dados, diff_kg, deficit, objetivo)
        resultado["deficit_diario_kcal"] = round(deficit, 0)
        resultado["meta_kcal"] = round(meta_kcal, 0)
        resultado["prazo_dias"] = prazo
        if fonte_prazo == "fallback":
            resultado["alertas"].append("Prazo estimado via fallback local (7700 kcal/kg ÷ déficit).")
        return resultado

    def estimar_prazo(self, dados: dict, diff_kg: float, deficit: float, objetivo: str) -> int | None:
        """Estimativa de tempo até o objetivo (RF-805 inverso)."""
        dias, _ = self._estimar_prazo(dados, diff_kg, deficit, objetivo)
        return dias

    def distribuir_macros(self, meta_kcal: float, perfil: str = "equilibrado") -> dict:
        """RF-806: distribuição de macros via Full Results; fallback por perfil."""
        query = self._query_macros(meta_kcal, perfil)
        texto = self._full_results(query)
        macros = self._parse_macros(texto) if texto else None
        if macros and macros.get("total_pct") and abs(macros["total_pct"] - 100) <= 5:
            return macros
        return self._fallback_macros(meta_kcal, perfil)

    def calcular_plano_completo(self, dados: dict, meta: dict) -> dict:
        """
        Orquestração: TMB → GET → Meta → Macros (RF-807).
        Retorna dict pronto para persistir em planos_nutricionais.
        """
        self.consultas = []
        alertas: list[str] = []

        tmb = self.calcular_tmb(dados)
        if tmb is None:
            tmb = self._fallback_tmb(dados)
            alertas.append("TMB calculado via fallback local (Mifflin-St Jeor).")

        get = self.calcular_get(dados)
        fonte_get = "wolfram"
        if get is None:
            get = self._fallback_get(dados)
            fonte_get = "fallback"
            alertas.append("GET calculado via fallback local (TMB × fator de atividade).")

        meta_calc = self.calcular_meta(dados, meta)
        alertas.extend(meta_calc.get("alertas", []))
        fonte_meta = meta_calc.get("fonte_meta", "wolfram")

        macros = self.distribuir_macros(meta_calc["meta_kcal"], meta.get("perfil_macro", "equilibrado"))
        fonte_macros = macros.get("fonte", "wolfram")
        if fonte_macros == "fallback":
            alertas.append("Macros calculados via fallback local (distribuição padrão do perfil).")

        fonte = "wolfram" if fonte_get == "wolfram" and fonte_meta == "wolfram" and fonte_macros == "wolfram" else "fallback"

        return {
            "tmb_kcal": round(tmb, 0),
            "get_kcal": round(get, 0),
            "meta_kcal": round(meta_calc["meta_kcal"], 0),
            "deficit_diario_kcal": round(meta_calc["deficit_diario_kcal"], 0),
            "prazo_dias": meta_calc["prazo_dias"],
            "proteinas_g": macros.get("proteinas_g"),
            "carboidratos_g": macros.get("carboidratos_g"),
            "lipidios_g": macros.get("lipidios_g"),
            "proteinas_pct": macros.get("proteinas_pct"),
            "carboidratos_pct": macros.get("carboidratos_pct"),
            "lipidios_pct": macros.get("lipidios_pct"),
            "fonte": fonte,
            "alertas": alertas,
        }

    # ══════════════════════════════════════════════════════════════
    # Montagem de queries
    # ══════════════════════════════════════════════════════════════

    def _sexo_en(self, sexo: str) -> str:
        return "male" if str(sexo or "M").upper() == "M" else "female"

    def _atividade_en(self, nivel: str | None) -> str:
        return ATIVIDADE_EN.get((nivel or "moderado").lower(), "moderate")

    def _query_tmb(self, d: dict) -> str:
        return (f"basal metabolic rate {self._sexo_en(d.get('sexo'))} "
                f"{int(d['idade'])} years {int(d['altura_cm'])}cm {int(d['peso_kg'])}kg")

    def _query_get(self, d: dict) -> str:
        # A Wolfram só reconhece "energy expenditure" (sem o "total daily") —
        # e devolve a tabela por nível de atividade no pod EnergyExpenditure.
        return (f"energy expenditure {self._sexo_en(d.get('sexo'))} "
                f"{int(d['idade'])} years {int(d['altura_cm'])}cm {int(d['peso_kg'])}kg")

    def _query_meta(self, d: dict, objetivo: str, taxa_semanal: float, semanas: float) -> str:
        # Wolfram não aceita "lose 5 kg in 8 weeks" (501) — precisa da taxa
        # semanal explícita: "calories to lose weight at 0.6 kg per week ..."
        return (f"calories to lose weight at {taxa_semanal:.2f} kg per week "
                f"{self._sexo_en(d.get('sexo'))} {int(d['idade'])} years "
                f"{int(d['altura_cm'])}cm {int(d['peso_kg'])}kg")

    def _query_prazo(self, d: dict, diff_kg: float, deficit: float, objetivo: str) -> str:
        direcao = "lose" if objetivo == "perder" else "gain"
        return (f"how long to {direcao} {diff_kg:g} kg at {abs(deficit):.0f} kcal/day "
                f"{'deficit' if objetivo == 'perder' else 'surplus'}")

    def _query_macros(self, meta_kcal: float, perfil: str) -> str:
        perfil_en = PERFIL_EN.get(perfil, "balanced diet")
        return f"macronutrient distribution {meta_kcal:.0f} kcal {perfil_en}"

    # ══════════════════════════════════════════════════════════════
    # Execução das chamadas (com cache + retry + auditoria)
    # ══════════════════════════════════════════════════════════════

    def _chave_cache(self, url: str, params: dict) -> str:
        raw = url + "?" + "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        return hashlib.md5(raw.encode()).hexdigest()

    def _get_com_cache(self, url: str, params: dict, extra: str = "") -> str | None:
        chave = self._chave_cache(url, params) + extra
        if self.cache_enabled and chave in self._cache:
            ts, valor = self._cache[chave]
            if time.time() - ts < self.cache_ttl:
                return valor
            del self._cache[chave]

        valor = None
        ok = False
        for tentativa in range(self.max_retries + 1):
            try:
                r = requests.get(url, params=params, timeout=self.timeout)
                if r.status_code == 403:
                    raise ErroAPI("AppID inválida ou quota excedida (HTTP 403).")
                if r.status_code == 501:
                    logger.warning("Wolfram 501 (query não interpretável): %s", params.get("input") or params.get("i"))
                    break
                r.raise_for_status()
                valor = r.text.strip()
                ok = True
                break
            except requests.Timeout:
                logger.warning("Timeout Wolfram (tentativa %d): %s", tentativa + 1, params.get("input") or params.get("i"))
                time.sleep(2 ** tentativa)
            except requests.ConnectionError:
                logger.warning("Erro de conexão Wolfram (tentativa %d)", tentativa + 1)
                time.sleep(2 ** tentativa)
            except ErroAPI:
                raise

        if self.cache_enabled and valor is not None:
            self._cache[chave] = (time.time(), valor)

        self.consultas.append({
            "query": str(params.get("input") or params.get("i") or ""),
            "api": "short_answers" if url == SHORT_ANSWERS_URL else "full_results",
            "resposta": valor,
            "ok": ok,
        })
        return valor

    def _short_answer(self, query: str) -> str | None:
        params = {"appid": self.api_key, "i": query, "units": "metric"}
        return self._get_com_cache(SHORT_ANSWERS_URL, params)

    def _full_results(self, query: str, pod_ids: str | None = None) -> str | None:
        params = {
            "appid": self.api_key,
            "input": query,
            "format": "plaintext",
            "output": "json",
            "units": "metric",
        }
        if pod_ids:
            params["includepodid"] = pod_ids
        texto = self._get_com_cache(FULL_RESULTS_URL, params)
        if texto is None:
            return None
        try:
            data = json.loads(texto)
            pods = (data.get("queryresult") or {}).get("pods") or []
            # Se pedimos um pod específico, retorna o texto dele
            if pod_ids:
                alvos = set(pod_ids.split(","))
                for pod in pods:
                    if pod.get("id") in alvos:
                        subs = pod.get("subpods") or []
                        if subs:
                            return subs[0].get("plaintext") or ""
                return ""
            # fallback: primeiro subpod com plaintext
            for pod in pods:
                for sub in pod.get("subpods") or []:
                    if sub.get("plaintext"):
                        return sub["plaintext"]
            return ""
        except (ValueError, AttributeError):
            return None

    # ══════════════════════════════════════════════════════════════
    # Parsing
    # ══════════════════════════════════════════════════════════════

    def _parse_macros(self, texto: str) -> dict | None:
        """Ex: '40% carbohydrates (180g), 30% protein (135g), 30% fat (60g)'."""
        if not texto:
            return None
        t = texto.lower()
        def _extrair(padrao_nome: str):
            m = re.search(rf"(\d+(?:\.\d+)?)%\s*{padrao_nome}.*?(\d+(?:\.\d+)?)\s*g", t)
            return (float(m.group(1)), float(m.group(2))) if m else (None, None)
        p_pct, p_g = _extrair(r"prot")
        c_pct, c_g = _extrair(r"carb")
        l_pct, l_g = _extrair(r"fat")
        if p_pct is None and c_pct is None and l_pct is None:
            return None
        return {
            "proteinas_pct": p_pct, "carboidratos_pct": c_pct, "lipidios_pct": l_pct,
            "proteinas_g": p_g, "carboidratos_g": c_g, "lipidios_g": l_g,
            "total_pct": (p_pct or 0) + (c_pct or 0) + (l_pct or 0),
        }

    def _parse_energy_expenditure(self, texto: str, nivel: str | None) -> float | None:
        """
        Parseia a tabela do pod EnergyExpenditure e devolve o gasto do nível
        de atividade do paciente.

        Formato do texto (plaintext, subpod único):
            activity level | energy expenditure
            sedentary | 2225 Cal/d
            lightly active | 2549 Cal/d
            moderately active | 2874 Cal/d
            very active | 3198 Cal/d
            extra active | 3523 Cal/d
        """
        if not texto:
            return None
        rotulo = NIVEL_PARA_ROTULO_WOLFRAM.get((nivel or "moderado").lower())
        melhor_valor: float | None = None
        for linha in texto.splitlines():
            if "|" not in linha:
                continue
            nome, valor = linha.split("|", 1)
            nome = nome.strip().lower()
            m = re.search(r"(\d+(?:\.\d+)?)", valor)
            if not m:
                continue
            numero = float(m.group(1))
            # Match exato do nível do paciente tem prioridade
            if rotulo and rotulo == nome:
                return numero
            # Fallback progressivo: se não achou o nível exato, guarda o 3º
            # (moderately active) que é o default clínico razoável
            if nome.startswith("moderately"):
                melhor_valor = numero
        return melhor_valor

    # ══════════════════════════════════════════════════════════════
    # Fallbacks locais (RT-003)
    # ══════════════════════════════════════════════════════════════

    def _fallback_tmb(self, d: dict) -> float:
        peso, altura, idade = float(d["peso_kg"]), float(d["altura_cm"]), int(d["idade"])
        if str(d.get("sexo") or "M").upper() == "M":
            return (10 * peso) + (6.25 * altura) - (5 * idade) + 5
        return (10 * peso) + (6.25 * altura) - (5 * idade) - 161

    def _fallback_get(self, d: dict) -> float:
        tmb = self._fallback_tmb(d)
        fator = FATORES_ATIVIDADE.get((d.get("nivel_atividade_fisica") or "moderado").lower(), 1.55)
        return tmb * fator

    def _estimar_prazo(self, d: dict, diff_kg: float, deficit: float, objetivo: str) -> tuple[int | None, str | None]:
        if diff_kg <= 0 or deficit == 0 or objetivo == "manter":
            return None, None
        query = self._query_prazo(d, diff_kg, deficit, objetivo)
        texto = self._short_answer(query)
        if texto is not None:
            dias = _extrair_prazo_dias(texto)
            if dias:
                return dias, "wolfram"
        # Fallback local: 7700 kcal/kg ÷ déficit diário
        dias = int(round(diff_kg * KCAL_POR_KG / abs(deficit)))
        return max(1, dias), "fallback"

    def _fallback_macros(self, meta_kcal: float, perfil: str) -> dict:
        p_pct, c_pct, l_pct = PERFIS_MACRO.get(perfil, PERFIS_MACRO["equilibrado"])
        return {
            "proteinas_pct": p_pct, "carboidratos_pct": c_pct, "lipidios_pct": l_pct,
            "proteinas_g": round(meta_kcal * p_pct / 100 / 4, 1),
            "carboidratos_g": round(meta_kcal * c_pct / 100 / 4, 1),
            "lipidios_g": round(meta_kcal * l_pct / 100 / 9, 1),
            "fonte": "fallback",
        }
