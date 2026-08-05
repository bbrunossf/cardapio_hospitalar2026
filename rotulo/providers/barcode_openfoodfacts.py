"""Provider de código de barras via Open Food Facts."""
import requests
from .base import BarcodeProvider
from ..schemas import limpar_ean, criar_campo_nutricional


class OpenFoodFactsProvider(BarcodeProvider):
    """Busca produtos na base mundial Open Food Facts (API v3.6)."""

    BASE_URL = "https://world.openfoodfacts.net/api/v3.6/product"

    def __init__(self, timeout: int = 15):
        self.timeout = timeout

    def buscar(self, ean: str) -> dict | None:
        ean_limpo = limpar_ean(ean)
        if not ean_limpo:
            return None

        url = f"{self.BASE_URL}/{ean_limpo}.json"
        try:
            print(f"buscando {ean_limpo} na Open Food Facts na url {url}...")
            response = requests.get(url, timeout=self.timeout)
            print(f"status: {response.status_code}")
            response.raise_for_status()
        except requests.RequestException:
            return None

        data = response.json()
        print(data)
        # v2 retorna status: 1, v3 retorna status: "success"
        status = data.get("status")
        if status not in (1, "success"):
            return None

        produto = data.get("product", {})
        if not produto:
            return None

        return self._mapear_produto(produto, ean_limpo)

    def _mapear_produto(self, produto: dict, ean: str) -> dict:
        # Determina fonte de nutrientes (legacy nutriments vs v3 nutrition.aggregated_set)
        nutriments = produto.get("nutriments", {})
        nutrition = produto.get("nutrition", {})
        aggregated = nutrition.get("aggregated_set", {}).get("nutrients", {})

        # Usa formato legacy se nutriments tiver valores diretos (não-dict)
        if nutriments and any(not isinstance(v, dict) for v in nutriments.values()):
            fonte = nutriments
            formato = "legacy"
        elif aggregated:
            fonte = aggregated
            formato = "v3"
        else:
            fonte = {}
            formato = "none"

        def _nut(chave_legacy: str, chave_v3: str, unidade_padrao: str = "g"):
            # Formato legacy: valor direto
            if formato == "legacy":
                valor = fonte.get(chave_legacy)
                if valor is not None:
                    try:
                        return criar_campo_nutricional(float(valor), unidade_padrao, presente=True)
                    except (ValueError, TypeError):
                        pass
            
            # Formato v3: dict com value/unit
            if formato == "v3":
                info = fonte.get(chave_v3)
                if isinstance(info, dict):
                    valor = info.get("value")
                    unit = info.get("unit", unidade_padrao)
                    # Fallback para value_computed se value for None
                    if valor is None and "value_computed" in info:
                        valor = info.get("value_computed")
                    if valor is not None:
                        try:
                            valor = float(valor)
                            # Converter g -> mg se necessário
                            if unit == "g" and unidade_padrao == "mg":
                                valor = valor * 1000
                                unit = "mg"
                            return criar_campo_nutricional(valor, unit, presente=True)
                        except (ValueError, TypeError):
                            pass
            
            return criar_campo_nutricional(None, unidade_padrao, presente=False)

        # Porção: preferir campos estruturados, fallback para string
        serving_qty = produto.get("serving_quantity")
        serving_unit = produto.get("serving_quantity_unit")
        if serving_qty is not None and serving_unit:
            try:
                porcao_valor = float(serving_qty)
                porcao_unidade = self._normalizar_unidade(str(serving_unit).lower())
            except (ValueError, TypeError):
                porcao_str = produto.get("serving_size") or ""
                porcao_valor, porcao_unidade = self._parse_porcao(porcao_str)
        else:
            porcao_str = produto.get("serving_size") or ""
            porcao_valor, porcao_unidade = self._parse_porcao(porcao_str)

        # Peso líquido: preferir campos estruturados, fallback para string
        prod_qty = produto.get("product_quantity")
        prod_unit = produto.get("product_quantity_unit")
        if prod_qty is not None and prod_unit:
            try:
                peso_valor = float(prod_qty)
                peso_unidade = self._normalizar_unidade(str(prod_unit).lower())
            except (ValueError, TypeError):
                peso_valor, peso_unidade = None, ""
        else:
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
                "energia_kcal": _nut("energy-kcal_serving", "energy-kcal", "kcal"),
                "carboidratos_g": _nut("carbohydrates_serving", "carbohydrates", "g"),
                "acucares_totais_g": _nut("sugars_serving", "sugars", "g"),
                "acucares_adicionados_g": _nut("added-sugars_serving", "added-sugars", "g"),
                "proteinas_g": _nut("proteins_serving", "proteins", "g"),
                "gorduras_totais_g": _nut("fat_serving", "fat", "g"),
                "gorduras_saturadas_g": _nut("saturated-fat_serving", "saturated-fat", "g"),
                "gorduras_trans_g": _nut("trans-fat_serving", "trans-fat", "g"),
                "fibras_g": _nut("fiber_serving", "fiber", "g"),
                "sodio_mg": _nut("sodium_serving", "sodium", "mg"),
            },
            "ingredientes_lista": produto.get("ingredients_text") or None,
            "alergenos": self._parse_alergenos(produto.get("allergens_tags", [])),
            "confianca_global": 1.0,
            "campos_baixa_confianca": [],
            "imagens": self._extrair_imagens(produto),
        }

    def _extrair_imagens(self, produto: dict) -> dict:
        """Extrai URLs de imagens do produto (frontal, ingredientes, nutrição)."""
        imagens = {}
        selected = produto.get("selected_images", {})

        # Frontal
        front = selected.get("front", {})
        for size in ("display", "small", "thumb"):
            url = self._primeira_imagem_idioma(front, size)
            if url:
                imagens["front"] = url
                break

        # Ingredientes
        ing = selected.get("ingredients", {})
        for size in ("display", "small", "thumb"):
            url = self._primeira_imagem_idioma(ing, size)
            if url:
                imagens["ingredients"] = url
                break

        # Nutrição
        nut = selected.get("nutrition", {})
        for size in ("display", "small", "thumb"):
            url = self._primeira_imagem_idioma(nut, size)
            if url:
                imagens["nutrition"] = url
                break

        # Fallback para URLs diretas
        if not imagens.get("front") and produto.get("image_front_url"):
            imagens["front"] = produto.get("image_front_url")
        if not imagens.get("ingredients") and produto.get("image_ingredients_url"):
            imagens["ingredients"] = produto.get("image_ingredients_url")
        if not imagens.get("nutrition") and produto.get("image_nutrition_url"):
            imagens["nutrition"] = produto.get("image_nutrition_url")

        return imagens

    def _primeira_imagem_idioma(self, secao: dict, tamanho: str) -> str | None:
        """Pega a primeira URL disponível para um tamanho, independente do idioma."""
        tamanho_dict = secao.get(tamanho, {})
        if not tamanho_dict:
            return None
        for url in tamanho_dict.values():
            if url:
                return url
        return None

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
