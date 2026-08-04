"""Módulo de cadastro de alimentos por rótulo nutricional."""
from .servico import cadastrar_por_codigo, cadastrar_por_imagem, confirmar_cadastro
from .duplicidade import buscar_duplicatas, buscar_por_ean
from .validacao import validar_dados, campos_baixa_confianca

__all__ = [
    "cadastrar_por_codigo",
    "cadastrar_por_imagem",
    "confirmar_cadastro",
    "buscar_duplicatas",
    "buscar_por_ean",
    "validar_dados",
    "campos_baixa_confianca",
]
