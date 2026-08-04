"""Provider OCR local via Tesseract + parser regex de rótulos."""
import re
from .base import OcrProvider
from ..schemas import (
    NUTRIENTES_NOMES,
    normalizar_resposta,
    normalizar_unidade_massa_volume,
)


try:
    from PIL import Image
    import pytesseract
    PYTESSERACT_DISPONIVEL = True
except ImportError:
    PYTESSERACT_DISPONIVEL = False


class TesseractOcrProvider(OcrProvider):
    """OCR local com Tesseract e parser regex para rótulos nutricionais."""

    def __init__(self, tesseract_cmd: str | None = None):
        if tesseract_cmd and PYTESSERACT_DISPONIVEL:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    def extrair_texto(self, imagem_bytes: bytes) -> str:
        if not PYTESSERACT_DISPONIVEL:
            return ""
        try:
            from io import BytesIO

            imagem = Image.open(BytesIO(imagem_bytes))
            texto = pytesseract.image_to_string(imagem, lang="por")
            return texto or ""
        except Exception:
            return ""

    def extrair(self, imagem_bytes: bytes) -> dict:
        """Executa OCR e tenta parser estruturado do rótulo."""
        texto = self.extrair_texto(imagem_bytes)
        if not texto.strip():
            return self._resposta_vazia()

        dados = self._parse_texto(texto)
        return normalizar_resposta(dados)

    def _parse_texto(self, texto: str) -> dict:
        texto_lower = texto.lower()

        def _buscar(regex: str, flags: int = 0) -> str | None:
            match = re.search(regex, texto_lower, flags)
            return match.group(1).strip() if match else None

        # Nome do produto: primeira linha não vazia, se não houver outro indicador
        linhas = [l.strip() for l in texto.splitlines() if l.strip()]
        nome = None
        if linhas:
            # Tenta achar uma linha que pareça nome de produto (não contém números nutricionais)
            for linha in linhas[:5]:
                if not any(p in linha for p in ["kcal", "g ", "mg", "valor", "nutricional"]):
                    nome = linha
                    break
            if not nome:
                nome = linhas[0]

        # Peso líquido
        peso_match = re.search(r"peso l[ií]quido[^\d]*(\d+(?:[.,]\d+)?)\s*(g|ml|kg|l)", texto_lower)
        if not peso_match:
            peso_match = re.search(r"cont[eé]udo[^\d]*(\d+(?:[.,]\d+)?)\s*(g|ml|kg|l)", texto_lower)
        if not peso_match:
            peso_match = re.search(r"(\d+(?:[.,]\d+)?)\s*(g|ml|kg|l)\s*$", texto_lower, re.MULTILINE)

        peso_valor = float(peso_match.group(1).replace(",", ".")) if peso_match else None
        peso_unidade = normalizar_unidade_massa_volume(peso_match.group(2)) if peso_match else "g"

        # Porção
        porcao_match = re.search(
            r"por[cç][aã]o[^\d]*?(\d+(?:[.,]\d+)?)\s*(g|ml|mg|kg|l|fatia|unidade|x[ií]cara|colher)",
            texto_lower,
        )
        porcao_valor = float(porcao_match.group(1).replace(",", ".")) if porcao_match else None
        porcao_unidade = porcao_match.group(2) if porcao_match else "g"

        nutrientes = {}

        # Energia
        energia = self._extrair_nutriente(texto_lower, r"(?:energia|valor energ[eé]tico)", r"(\d+(?:[.,]\d+)?)\s*kcal")
        nutrientes["energia_kcal"] = {"valor": energia, "unidade": "kcal", "presente": energia is not None}

        # Carboidratos / Hidratos de carbono
        carb = self._extrair_nutriente(texto_lower, r"(?:carboidratos|hidratos de carbono)", r"(\d+(?:[.,]\d+)?)\s*g")
        nutrientes["carboidratos_g"] = {"valor": carb, "unidade": "g", "presente": carb is not None}

        # Açúcares totais
        acuc_tot = self._extrair_nutriente(texto_lower, r"a[cç][uú]cares totais", r"(\d+(?:[.,]\d+)?)\s*g")
        nutrientes["acucares_totais_g"] = {"valor": acuc_tot, "unidade": "g", "presente": acuc_tot is not None}

        # Açúcares adicionados
        acuc_add = self._extrair_nutriente(texto_lower, r"a[cç][uú]cares adicionados", r"(\d+(?:[.,]\d+)?)\s*g")
        nutrientes["acucares_adicionados_g"] = {"valor": acuc_add, "unidade": "g", "presente": acuc_add is not None}

        # Proteínas
        prot = self._extrair_nutriente(texto_lower, r"prote[ií]nas", r"(\d+(?:[.,]\d+)?)\s*g")
        nutrientes["proteinas_g"] = {"valor": prot, "unidade": "g", "presente": prot is not None}

        # Gorduras totais
        gord_tot = self._extrair_nutriente(texto_lower, r"gorduras totais", r"(\d+(?:[.,]\d+)?)\s*g")
        nutrientes["gorduras_totais_g"] = {"valor": gord_tot, "unidade": "g", "presente": gord_tot is not None}

        # Gorduras saturadas
        gord_sat = self._extrair_nutriente(texto_lower, r"gorduras saturadas", r"(\d+(?:[.,]\d+)?)\s*g")
        nutrientes["gorduras_saturadas_g"] = {"valor": gord_sat, "unidade": "g", "presente": gord_sat is not None}

        # Gorduras trans
        gord_trans = self._extrair_nutriente(texto_lower, r"gorduras trans", r"(\d+(?:[.,]\d+)?)\s*g")
        nutrientes["gorduras_trans_g"] = {"valor": gord_trans, "unidade": "g", "presente": gord_trans is not None}

        # Fibras
        fibras = self._extrair_nutriente(texto_lower, r"fibras", r"(\d+(?:[.,]\d+)?)\s*g")
        nutrientes["fibras_g"] = {"valor": fibras, "unidade": "g", "presente": fibras is not None}

        # Sódio
        sodio = self._extrair_nutriente(texto_lower, r"s[oó]dio", r"(\d+(?:[.,]\d+)?)\s*mg")
        nutrientes["sodio_mg"] = {"valor": sodio, "unidade": "mg", "presente": sodio is not None}

        # Ingredientes
        ingredientes = _buscar(r"ingredientes[\s:]*(.+?)(?:\n\n|alerg|contém|modo de|conservar|validade)", re.DOTALL)

        # Alergenos
        alergenos = []
        alerg_texto = _buscar(r"cont[eé]m\s*[:\-]?\s*(.+?)(?:\n|$)")
        if alerg_texto:
            alergenos = [a.strip().lower() for a in re.split(r"[,;]", alerg_texto) if a.strip()]

        return {
            "codigo_barras": None,
            "nome": nome,
            "marca": _buscar(r"marca[\s:]*(.+?)(?:\n|$)"),
            "fabricante": _buscar(r"fabricad[oa][\s:]*(.+?)(?:\n|$)"),
            "peso_liquido": {"valor": peso_valor, "unidade": peso_unidade or "g"},
            "porcao": {"valor": porcao_valor, "unidade": porcao_unidade or "g"},
            "nutrientes": nutrientes,
            "ingredientes_lista": ingredientes,
            "alergenos": alergenos,
            "confianca_global": 0.5,
            "campos_baixa_confianca": [],
        }

    def _extrair_nutriente(self, texto: str, padrao_nome: str, padrao_valor: str) -> float | None:
        """Busca valor numérico de um nutriente no texto."""
        # Procura linha que contenha o nome do nutriente e depois um valor
        linhas = texto.splitlines()
        for linha in linhas:
            if re.search(padrao_nome, linha, re.IGNORECASE):
                match = re.search(padrao_valor, linha, re.IGNORECASE)
                if match:
                    try:
                        return float(match.group(1).replace(",", "."))
                    except ValueError:
                        return None
        return None

    def _resposta_vazia(self) -> dict:
        return {
            "codigo_barras": None,
            "nome": None,
            "marca": None,
            "fabricante": None,
            "peso_liquido": {"valor": None, "unidade": "g"},
            "porcao": {"valor": None, "unidade": "g"},
            "nutrientes": {
                nome: {"valor": None, "unidade": "mg" if nome == "sodio_mg" else "kcal" if nome == "energia_kcal" else "g", "presente": False}
                for nome in NUTRIENTES_NOMES
            },
            "ingredientes_lista": None,
            "alergenos": [],
            "confianca_global": 0.0,
            "campos_baixa_confianca": [],
            "_status": "falhou",
        }
