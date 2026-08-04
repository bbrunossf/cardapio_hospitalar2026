"""Interfaces abstratas dos providers do módulo de rótulo."""
from abc import ABC, abstractmethod


class BarcodeProvider(ABC):
    @abstractmethod
    def buscar(self, ean: str) -> dict | None:
        """Busca produto por EAN/UPC. Retorna dict no formato do schema ou None."""


class LabelVisionProvider(ABC):
    @abstractmethod
    def extrair(self, imagem_bytes: bytes) -> dict:
        """Envia imagem ao LLM multimodal. Retorna dict conforme JSON schema."""


class OcrProvider(ABC):
    @abstractmethod
    def extrair_texto(self, imagem_bytes: bytes) -> str:
        """OCR puro. Retorna texto bruto para o parser."""
