"""JSON Schema e funções utilitárias de validação do módulo de rótulo."""
import json
import re
from typing import Any


# Schema base conforme seção 6 do documento de especificação.
# Valores numéricos podem ser float ou null; unidades são strings.
NUTRIENTES_NOMES = [
    "energia_kcal",
    "carboidratos_g",
    "acucares_totais_g",
    "acucares_adicionados_g",
    "proteinas_g",
    "gorduras_totais_g",
    "gorduras_saturadas_g",
    "gorduras_trans_g",
    "fibras_g",
    "sodio_mg",
]

UNIDADES_MASSA_VOLUME = {"mg", "g", "kg", "ml", "L"}
UNIDADES_ENERGIA = {"kcal"}
UNIDADES_PESO_LIQUIDO = {"mg", "g", "kg", "ml", "L"}
UNIDADES_PORCAO = {"mg", "g", "kg", "ml", "L", "fatia", "unidade", "xícara", "colher"}


def criar_campo_nutricional(valor: float | None, unidade: str, presente: bool) -> dict:
    """Cria um campo no padrão {valor, unidade, presente}."""
    return {"valor": valor, "unidade": unidade, "presente": presente}


def criar_campo_vazio(unidade: str = "g") -> dict:
    return criar_campo_nutricional(None, unidade, presente=False)


def limpar_ean(ean: str | None) -> str | None:
    """Remove espaços e valida tamanho do EAN/UPC (8 a 14 dígitos)."""
    if not ean:
        return None
    limpo = re.sub(r"\D", "", str(ean).strip())
    if 8 <= len(limpo) <= 14:
        return limpo
    return None


def normalizar_unidade_massa_volume(unidade: str) -> str | None:
    """Normaliza unidades de massa/volume. Retorna None se não reconhecida."""
    if not unidade:
        return None
    u = str(unidade).strip().lower()
    mapa = {
        "mg": "mg",
        "g": "g",
        "grama": "g",
        "gramas": "g",
        "kg": "kg",
        "kilo": "kg",
        "kilograma": "kg",
        "kilogramas": "kg",
        "ml": "ml",
        "mililitro": "ml",
        "mililitros": "ml",
        "l": "L",
        "litro": "L",
        "litros": "L",
    }
    return mapa.get(u)


def normalizar_unidade_porcao(unidade: str) -> str | None:
    """Normaliza unidade de porção (massa/volume ou unidades livres)."""
    if not unidade:
        return None
    u = str(unidade).strip().lower()
    mv = normalizar_unidade_massa_volume(u)
    if mv:
        return mv
    mapa_livre = {
        "fatia": "fatia",
        "fatias": "fatia",
        "unidade": "unidade",
        "unidades": "unidade",
        "un": "unidade",
        "xícara": "xícara",
        "xicara": "xícara",
        "xícaras": "xícara",
        "xicaras": "xícara",
        "colher": "colher",
        "colheres": "colher",
        "colher de sopa": "colher",
        "colher de chá": "colher",
    }
    return mapa_livre.get(u)


def normalizar_texto(texto: Any) -> str | None:
    """Remove espaços extras e retorna None para textos vazios."""
    if texto is None:
        return None
    limpo = str(texto).strip()
    return limpo if limpo else None


def parse_valor_numerico(valor: Any) -> float | None:
    """Converte valor para float, aceitando vírgula como decimal. Retorna None se inválido."""
    if valor is None:
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    texto = str(valor).strip().replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        return None


def parse_campo_valor_unidade(campo: Any, unidade_padrao: str) -> dict:
    """Garante que um campo esteja no formato {valor, unidade, presente}."""
    if isinstance(campo, dict):
        valor = parse_valor_numerico(campo.get("valor"))
        unidade = normalizar_unidade_massa_volume(campo.get("unidade")) or unidade_padrao
        presente = bool(campo.get("presente", valor is not None))
        return criar_campo_nutricional(valor, unidade, presente)

    # Se veio apenas o valor numérico
    valor = parse_valor_numerico(campo)
    return criar_campo_nutricional(valor, unidade_padrao, valor is not None)


def parse_porcao(porcao: Any) -> dict:
    """Garante que porcao esteja no formato {valor, unidade}."""
    if isinstance(porcao, dict):
        valor = parse_valor_numerico(porcao.get("valor"))
        unidade = normalizar_unidade_porcao(porcao.get("unidade")) or "g"
        return {"valor": valor, "unidade": unidade}
    # Se veio apenas texto
    if isinstance(porcao, str):
        import re

        texto = porcao.strip().lower().replace(",", ".")
        match = re.search(r"(\d+(?:\.\d+)?)\s*([a-zA-Záéíóúãõç]+)?", texto)
        if match:
            valor = parse_valor_numerico(match.group(1))
            unidade = normalizar_unidade_porcao(match.group(2)) or "g"
            return {"valor": valor, "unidade": unidade}
    return {"valor": None, "unidade": "g"}


def parse_peso_liquido(peso: Any) -> dict:
    """Garante que peso_liquido esteja no formato {valor, unidade}."""
    if isinstance(peso, dict):
        valor = parse_valor_numerico(peso.get("valor"))
        unidade = normalizar_unidade_massa_volume(peso.get("unidade")) or "g"
        return {"valor": valor, "unidade": unidade}
    if isinstance(peso, (int, float)):
        return {"valor": float(peso), "unidade": "g"}
    return {"valor": None, "unidade": "g"}


def normalizar_resposta(dados: dict) -> dict:
    """Normaliza uma resposta de provider para o schema padrão."""
    nutrientes_raw = dados.get("nutrientes") or {}
    nutrientes = {}
    for nome in NUTRIENTES_NOMES:
        unidade_padrao = "mg" if nome == "sodio_mg" else "kcal" if nome == "energia_kcal" else "g"
        nutrientes[nome] = parse_campo_valor_unidade(
            nutrientes_raw.get(nome), unidade_padrao
        )

    porcao = parse_porcao(dados.get("porcao"))
    peso_liquido = parse_peso_liquido(dados.get("peso_liquido"))

    alergenos = dados.get("alergenos") or []
    if isinstance(alergenos, str):
        try:
            alergenos = json.loads(alergenos)
        except json.JSONDecodeError:
            alergenos = [a.strip() for a in alergenos.split(",") if a.strip()]
    alergenos = [str(a).lower().strip() for a in alergenos if a]

    return {
        "codigo_barras": limpar_ean(dados.get("codigo_barras")),
        "nome": normalizar_texto(dados.get("nome")),
        "marca": normalizar_texto(dados.get("marca")),
        "fabricante": normalizar_texto(dados.get("fabricante")),
        "peso_liquido": peso_liquido,
        "porcao": porcao,
        "nutrientes": nutrientes,
        "ingredientes_lista": normalizar_texto(dados.get("ingredientes_lista")),
        "alergenos": alergenos,
        "confianca_global": parse_valor_numerico(dados.get("confianca_global")) or 0.0,
        "campos_baixa_confianca": list(dados.get("campos_baixa_confianca", []) or []),
    }


def schema_valido(dados: dict) -> tuple[bool, list[str]]:
    """Valida estrutura básica do schema. Retorna (válido?, erros)."""
    erros = []
    if not isinstance(dados, dict):
        erros.append("Resposta não é um objeto JSON.")
        return False, erros

    if "nutrientes" not in dados or not isinstance(dados.get("nutrientes"), dict):
        erros.append("Campo 'nutrientes' ausente ou inválido.")

    for nome in NUTRIENTES_NOMES:
        campo = dados.get("nutrientes", {}).get(nome)
        if not isinstance(campo, dict):
            erros.append(f"Nutriente '{nome}' não está no formato {{valor, unidade, presente}}.")
            continue
        if "valor" not in campo or "unidade" not in campo or "presente" not in campo:
            erros.append(f"Nutriente '{nome}' incompleto.")

    return len(erros) == 0, erros
