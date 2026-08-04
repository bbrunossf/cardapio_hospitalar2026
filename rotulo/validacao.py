"""Regras de validação e consistência do módulo de rótulo (seção 7)."""
from .schemas import (
    NUTRIENTES_NOMES,
    normalizar_resposta,
    parse_valor_numerico,
    normalizar_unidade_massa_volume,
    normalizar_unidade_porcao,
)


def validar_dados(dados: dict) -> tuple[dict, list[str], list[str]]:
    """
    Valida dados do schema e retorna:
      - dados normalizados
      - lista de erros (bloqueantes)
      - lista de avisos (não bloqueantes)
    """
    dados = normalizar_resposta(dados)
    erros = []
    avisos = []

    # 1. Tipos básicos
    if not dados.get("nome"):
        erros.append("Nome do produto é obrigatório.")

    # Código de barras
    if dados.get("codigo_barras") is not None:
        if not dados["codigo_barras"].isdigit() or not (8 <= len(dados["codigo_barras"]) <= 14):
            erros.append("Código de barras deve conter entre 8 e 14 dígitos.")

    # 2. Unidades
    peso_unidade = normalizar_unidade_massa_volume(dados.get("peso_liquido", {}).get("unidade"))
    if dados.get("peso_liquido", {}).get("valor") is not None and not peso_unidade:
        erros.append("Unidade de peso líquido inválida.")

    porcao = dados.get("porcao", {})
    porcao_unidade = normalizar_unidade_porcao(porcao.get("unidade"))
    porcao_valor = parse_valor_numerico(porcao.get("valor"))
    if porcao_valor is not None and porcao_valor <= 0:
        erros.append("Quantidade da porção deve ser maior que zero.")

    # 3. Não negatividade
    for nome in NUTRIENTES_NOMES:
        campo = dados.get("nutrientes", {}).get(nome, {})
        valor = parse_valor_numerico(campo.get("valor"))
        if valor is not None and valor < 0:
            erros.append(f"{nome} não pode ser negativo.")

    # 4. Consistência entre campos (apenas avisos)
    nutrientes = dados.get("nutrientes", {})

    acuc_add = _get_valor(nutrientes, "acucares_adicionados_g")
    acuc_tot = _get_valor(nutrientes, "acucares_totais_g")
    if acuc_add is not None and acuc_tot is not None and acuc_add > acuc_tot:
        avisos.append("Açúcares adicionados maior que açúcares totais (verificar leitura).")

    gord_sat = _get_valor(nutrientes, "gorduras_saturadas_g")
    gord_trans = _get_valor(nutrientes, "gorduras_trans_g")
    gord_tot = _get_valor(nutrientes, "gorduras_totais_g")
    if gord_sat is not None and gord_trans is not None and gord_tot is not None:
        if gord_sat + gord_trans > gord_tot:
            avisos.append("Soma de gorduras saturadas + trans maior que gorduras totais.")

    energia = _get_valor(nutrientes, "energia_kcal")
    prot = _get_valor(nutrientes, "proteinas_g")
    carb = _get_valor(nutrientes, "carboidratos_g")
    gord = _get_valor(nutrientes, "gorduras_totais_g")
    if energia is not None and prot is not None and carb is not None and gord is not None:
        esperado = 4 * prot + 4 * carb + 9 * gord
        if esperado > 0 and abs(energia - esperado) / esperado > 0.30:
            avisos.append(
                f"Energia ({energia} kcal) diverge mais de 30% do esperado "
                f"({esperado:.1f} kcal). Verificar rótulo."
            )

    # 5. Plausibilidade básica (bloqueante)
    if energia is not None and energia >= 2000:
        erros.append("Energia ≥ 2000 kcal/100g é improvável; verificar leitura do rótulo.")

    return dados, erros, avisos


def _get_valor(nutrientes: dict, nome: str) -> float | None:
    campo = nutrientes.get(nome, {})
    return parse_valor_numerico(campo.get("valor"))


def campos_baixa_confianca(dados: dict) -> list[str]:
    """Retorna lista de campos que precisam de revisão manual."""
    revisao = list(dados.get("campos_baixa_confianca", []) or [])
    nutrientes = dados.get("nutrientes", {})
    for nome in NUTRIENTES_NOMES:
        campo = nutrientes.get(nome, {})
        if campo.get("presente") and campo.get("valor") is None:
            if nome not in revisao:
                revisao.append(nome)
    return revisao
