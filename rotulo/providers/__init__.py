"""Providers do módulo de rótulo."""
from .base import BarcodeProvider, LabelVisionProvider, OcrProvider
from .barcode_openfoodfacts import OpenFoodFactsProvider
from .vision_openai_compat import VisionOpenAICompatProvider
from .ocr_tesseract import TesseractOcrProvider

__all__ = [
    "BarcodeProvider",
    "LabelVisionProvider",
    "OcrProvider",
    "OpenFoodFactsProvider",
    "VisionOpenAICompatProvider",
    "TesseractOcrProvider",
]
