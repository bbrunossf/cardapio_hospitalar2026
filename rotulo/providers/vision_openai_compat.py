"""Provider de visão via API OpenAI-compatível (Moonshot, Gemini, OpenAI, etc.)."""
import json
import base64
import requests
from .base import LabelVisionProvider
from ..schemas import NUTRIENTES_NOMES, normalizar_resposta, schema_valido


class VisionOpenAICompatProvider(LabelVisionProvider):
    """Extrai informações nutricionais de imagens usando LLM multimodal."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        confianca_minima: float = 0.80,
        timeout: int = 60,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.confianca_minima = confianca_minima
        self.timeout = timeout

    def extrair(self, imagem_bytes: bytes) -> dict:
        if not imagem_bytes:
            return self._resposta_falha("Imagem vazia.")

        prompt = self._montar_prompt()
        imagem_b64 = base64.b64encode(imagem_bytes).decode("utf-8")

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{imagem_b64}"
                            },
                        },
                    ],
                }
            ],
            "response_format": {"type": "json_object"},
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            return self._resposta_falha(f"Erro de comunicação com LLM: {exc}")

        try:
            resposta_json = response.json()
            conteudo = resposta_json["choices"][0]["message"]["content"]
            dados = json.loads(conteudo)
        except (KeyError, json.JSONDecodeError, IndexError) as exc:
            return self._resposta_falha(f"Resposta do LLM inválida: {exc}")

        return self._processar_resposta(dados)

    def _processar_resposta(self, dados: dict) -> dict:
        valido, erros = schema_valido(dados)
        if not valido:
            return self._resposta_falha(f"Schema inválido: {'; '.join(erros)}")

        normalizado = normalizar_resposta(dados)
        confianca = normalizado.get("confianca_global", 0.0) or 0.0

        if confianca < self.confianca_minima:
            normalizado["_status"] = "baixa_confianca"
        else:
            normalizado["_status"] = "ok"

        return normalizado

    def _resposta_falha(self, motivo: str) -> dict:
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
            "_erro": motivo,
            "_status": "falhou",
        }

    def _montar_prompt(self) -> str:
        schema_exemplo = {
            "codigo_barras": "7891234567890",
            "nome": "Biscoito integral de aveia e mel",
            "marca": "Marca Exemplo",
            "fabricante": "Indústria Exemplo S.A.",
            "peso_liquido": {"valor": 200, "unidade": "g"},
            "porcao": {"valor": 30, "unidade": "g"},
            "nutrientes": {
                "energia_kcal": {"valor": 120, "unidade": "kcal", "presente": True},
                "carboidratos_g": {"valor": 20.0, "unidade": "g", "presente": True},
                "acucares_totais_g": {"valor": 8.0, "unidade": "g", "presente": True},
                "acucares_adicionados_g": {"valor": 6.0, "unidade": "g", "presente": True},
                "proteinas_g": {"valor": 4.0, "unidade": "g", "presente": True},
                "gorduras_totais_g": {"valor": 3.0, "unidade": "g", "presente": True},
                "gorduras_saturadas_g": {"valor": 1.0, "unidade": "g", "presente": True},
                "gorduras_trans_g": {"valor": None, "unidade": "g", "presente": False},
                "fibras_g": {"valor": 2.5, "unidade": "g", "presente": True},
                "sodio_mg": {"valor": 180, "unidade": "mg", "presente": True},
            },
            "ingredientes_lista": "Farinha de trigo integral, aveia, mel, ...",
            "alergenos": ["gluten", "aveia"],
            "confianca_global": 0.87,
            "campos_baixa_confianca": ["acucares_adicionados_g"],
        }

        return (
            "Extraia as informações do rótulo nutricional da imagem e retorne APENAS um JSON válido "
            "no seguinte formato (sem comentários, sem markdown, sem explicações):\n\n"
            f"{json.dumps(schema_exemplo, indent=2, ensure_ascii=False)}\n\n"
            "Regras:\n"
            "- 'presente' é true apenas se o valor constar explicitamente no rótulo.\n"
            "- Se um nutriente não estiver no rótulo, use {\"valor\": null, \"unidade\": \"...\", \"presente\": false}.\n"
            "- NUNCA invente ou complete valores ausentes.\n"
            "- 'confianca_global' deve ser um número entre 0 e 1.\n"
            "- 'campos_baixa_confianca' lista os campos com leitura incerta.\n"
            "- Normalize unidades para: g, mg, kg, ml, L, kcal.\n"
        )
