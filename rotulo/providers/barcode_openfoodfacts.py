"""Provider de código de barras via Open Food Facts."""
import requests
from .base import BarcodeProvider
from ..schemas import limpar_ean, criar_campo_nutricional


class OpenFoodFactsProvider(BarcodeProvider):
    """Busca produtos na base mundial Open Food Facts (API v2)."""

    BASE_URL = "https://world.openfoodfacts.org/api/v2/product"

    def __init__(self, timeout: int = 15):
        self.timeout = timeout

    def buscar(self, ean: str) -> dict | None:
        ean_limpo = limpar_ean(ean)
        if not ean_limpo:
            return None

        url = f"{self.BASE_URL}/{ean_limpo}.json"
        try:
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()
        except requests.RequestException:
            return None

        data = response.json()
        if data.get("status") != 1:
            return None

        produto = data.get("product", {})
        if not produto:
            return None

        return self._mapear_produto(produto, ean_limpo)

    def _mapear_produto(self, produto: dict, ean: str) -> dict:
        nutriments = produto.get("nutriments", {})

        def _nut(chave: str, unidade_padrao: str = "g"):
            valor = nutriments.get(chave)
            if valor is None:
                return criar_campo_nutricional(None, unidade_padrao, presente=False)
            try:
                return criar_campo_nutricional(float(valor), unidade_padrao, presente=True)
            except (ValueError, TypeError):
                return criar_campo_nutricional(None, unidade_padrao, presente=False)

        porcao_str = produto.get("serving_size") or ""
        porcao_valor, porcao_unidade = self._parse_porcao(porcao_str)

        peso_str = produto.get("product_quantity") or produto.get("net_weight_value") or ""
        peso_valor, peso_unidade = self._parse_peso(peso_str)

        return {
            "codigo_barras": ean,
            "nome": self._primeiro_nao_vazio(
                produto.get("product_name"),
                produto.get("generic_name"),
            ),
            "marca": produto.get("brands") or None,
            "fabricante": produto.get("manufacturing_places") or None,
            "peso_liquido": {
                "valor": peso_valor,
                "unidade": peso_unidade,
            },
            "porcao": {
                "valor": porcao_valor,
                "unidade": porcao_unidade,
            },
            "nutrientes": {
                "energia_kcal": _nut("energy-kcal_serving", "kcal"),
                "carboidratos_g": _nut("carbohydrates_serving", "g"),
                "acucares_totais_g": _nut("sugars_serving", "g"),
                "acucares_adicionados_g": _nut("added-sugars_serving", "g"),
                "proteinas_g": _nut("proteins_serving", "g"),
                "gorduras_totais_g": _nut("fat_serving", "g"),
                "gorduras_saturadas_g": _nut("saturated-fat_serving", "g"),
                "gorduras_trans_g": _nut("trans-fat_serving", "g"),
                "fibras_g": _nut("fiber_serving", "g"),
                "sodio_mg": _nut("sodium_serving", "mg"),
            },
            "ingredientes_lista": produto.get("ingredients_text") or None,
            "alergenos": self._parse_alergenos(produto.get("allergens_tags", [])),
            "confianca_global": 1.0,
            "campos_baixa_confianca": [],
        }

    def _primeiro_nao_vazio(self, *valores) -> str | None:
        for v in valores:
            if v and str(v).strip():
                return str(v).strip()
        return None

    def _parse_porcao(self, texto: str) -> tuple[float | None, str]:
        return self._parse_quantidade_unidade(texto)

    def _parse_peso(self, texto: str | float | int) -> tuple[float | None, str]:
        if isinstance(texto, (int, float)):
            return float(texto), "g"
        return self._parse_quantidade_unidade(str(texto))

    def _parse_quantidade_unidade(self, texto: str) -> tuple[float | None, str]:
        import re

        texto = (texto or "").strip().lower().replace(",", ".")
        if not texto:
            return None, ""

        match = re.search(r"(\d+(?:\.\d+)?)\s*([a-zA-Záéíóúãõç]+)?", texto)
        if not match:
            return None, ""

        try:
            valor = float(match.group(1))
        except ValueError:
            return None, ""

        unidade = (match.group(2) or "g").strip().lower()
        unidade = self._normalizar_unidade(unidade)
        return valor, unidade

    def _normalizar_unidade(self, unidade: str) -> str:
        mapa = {
            "gram": "g",
            "grama": "g",
            "gramas": "g",
            "kg": "kg",
            "kilo": "kg",
            "kilogram": "kg",
            "kilograma": "kg",
            "ml": "ml",
            "milliliter": "ml",
            "mililitro": "ml",
            "l": "L",
            "liter": "L",
            "litro": "L",
            "litros": "L",
        }
        return mapa.get(unidade, unidade)

    def _parse_alergenos(self, allergens_tags: list) -> list[str]:
        resultado = []
        for tag in allergens_tags:
            if isinstance(tag, str):
                # Open Food Facts retorna tags como "en:gluten", "pt:leite"
                partes = tag.split(":")
                nome = partes[-1] if partes else tag
                nome = nome.lower().strip()
                if nome:
                    resultado.append(nome)
        return resultado
