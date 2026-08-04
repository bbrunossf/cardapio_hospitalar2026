"""Configuração e fábrica de providers do módulo de rótulo."""
import os

from .providers import (
    OpenFoodFactsProvider,
    VisionOpenAICompatProvider,
    TesseractOcrProvider,
)


def get_barcode_provider():
    """Retorna provider de código de barras configurado."""
    provider = os.getenv("ROTULO_BARCODE_PROVIDER", "openfoodfacts").lower()
    if provider == "openfoodfacts":
        return OpenFoodFactsProvider()
    raise ValueError(f"Provider de barcode não suportado: {provider}")


def get_vision_provider():
    """Retorna provider de visão configurado."""
    provider = os.getenv("ROTULO_VISION_PROVIDER", "openai_compat").lower()
    if provider == "openai_compat":
        base_url = os.getenv("ROTULO_VISION_BASE_URL")
        api_key = os.getenv("ROTULO_VISION_API_KEY")
        model = os.getenv("ROTULO_VISION_MODEL")
        confianca = float(os.getenv("ROTULO_CONFIANCA_MINIMA", "0.80"))

        if not base_url or not api_key or not model:
            raise ValueError(
                "Configuração de visão incompleta: defina "
                "ROTULO_VISION_BASE_URL, ROTULO_VISION_API_KEY e ROTULO_VISION_MODEL"
            )

        return VisionOpenAICompatProvider(
            api_key=api_key,
            base_url=base_url,
            model=model,
            confianca_minima=confianca,
        )
    raise ValueError(f"Provider de visão não suportado: {provider}")


def get_ocr_provider():
    """Retorna provider OCR configurado."""
    provider = os.getenv("ROTULO_OCR_PROVIDER", "tesseract").lower()
    if provider == "tesseract":
        return TesseractOcrProvider(tesseract_cmd=os.getenv("TESSERACT_CMD"))
    raise ValueError(f"Provider OCR não suportado: {provider}")
