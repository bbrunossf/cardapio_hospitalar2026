"""Orquestrador do cadastro de alimentos por rótulo (seção 3 e 10.2)."""
import json
from sqlalchemy import func
from extensions import db
from models_rotulo import AlimentoIndustrializado, AlimentoVersao
from .config import get_barcode_provider, get_vision_provider, get_ocr_provider
from .schemas import normalizar_resposta, NUTRIENTES_NOMES
from .validacao import validar_dados, campos_baixa_confianca
from .duplicidade import buscar_duplicatas, buscar_por_ean


# Mapeamento de campos do schema para colunas do modelo
MAPA_NUTRIENTES = {
    "energia_kcal": "energia_kcal",
    "carboidratos_g": "carboidratos_g",
    "acucares_totais_g": "acucares_totais_g",
    "acucares_adicionados_g": "acucares_adicionados_g",
    "proteinas_g": "proteinas_g",
    "gorduras_totais_g": "gorduras_totais_g",
    "gorduras_saturadas_g": "gorduras_saturadas_g",
    "gorduras_trans_g": "gorduras_trans_g",
    "fibras_g": "fibras_g",
    "sodio_mg": "sodio_mg",
}


def cadastrar_por_codigo(ean: str):
    """Fluxo de cadastro a partir do código de barras."""
    provider = get_barcode_provider()
    dados = provider.buscar(ean)

    if not dados:
        return {
            "status": "nao_encontrado",
            "dados": None,
            "duplicatas": [],
            "avisos": [],
            "campos_revisao": [],
        }

    dados = normalizar_resposta(dados)
    dados["_fonte"] = "barcode"
    return _preparar_resposta(dados)


def cadastrar_por_imagem(imagem_bytes: bytes):
    """Fluxo de cadastro a partir da foto do rótulo."""
    # 1. Tenta LLM multimodal
    vision = get_vision_provider()
    dados = vision.extrair(imagem_bytes)

    status_interno = dados.get("_status", "falhou")

    if status_interno == "ok" and _campos_essenciais_presentes(dados):
        dados = normalizar_resposta(dados)
        dados["_fonte"] = "ia"
        return _preparar_resposta(dados, status="ia")

    # 2. Fallback OCR
    ocr = get_ocr_provider()
    dados_ocr = ocr.extrair(imagem_bytes)

    if _campos_essenciais_presentes(dados_ocr):
        dados_ocr = normalizar_resposta(dados_ocr)
        dados_ocr["_fonte"] = "ocr"
        return _preparar_resposta(dados_ocr, status="ocr")

    # 3. Falhou: retorna o melhor resultado possível para formulário manual
    merge = _merge_dados(dados, dados_ocr)
    merge = normalizar_resposta(merge)
    merge["_fonte"] = "manual"
    return _preparar_resposta(merge, status="falhou")


def _campos_essenciais_presentes(dados: dict) -> bool:
    """Campos essenciais: nome + (energia OU carboidratos)."""
    if not dados.get("nome"):
        return False
    nutrientes = dados.get("nutrientes", {})
    energia = nutrientes.get("energia_kcal", {}).get("valor")
    carboidratos = nutrientes.get("carboidratos_g", {}).get("valor")
    return energia is not None or carboidratos is not None


def _merge_dados(dados_ia: dict, dados_ocr: dict) -> dict:
    """Combina resultados da IA e OCR, priorizando campos presentes."""
    merge = {}
    for chave in ["codigo_barras", "nome", "marca", "fabricante", "ingredientes_lista"]:
        merge[chave] = dados_ia.get(chave) or dados_ocr.get(chave)

    for chave in ["peso_liquido", "porcao"]:
        ia = dados_ia.get(chave, {})
        ocr = dados_ocr.get(chave, {})
        merge[chave] = {
            "valor": ia.get("valor") or ocr.get("valor"),
            "unidade": ia.get("unidade") or ocr.get("unidade"),
        }

    nutrientes_merge = {}
    nutrientes_ia = dados_ia.get("nutrientes", {})
    nutrientes_ocr = dados_ocr.get("nutrientes", {})
    for nome in NUTRIENTES_NOMES:
        ia_campo = nutrientes_ia.get(nome, {})
        ocr_campo = nutrientes_ocr.get(nome, {})
        if ia_campo.get("presente") and ia_campo.get("valor") is not None:
            nutrientes_merge[nome] = ia_campo
        elif ocr_campo.get("presente") and ocr_campo.get("valor") is not None:
            nutrientes_merge[nome] = ocr_campo
        else:
            nutrientes_merge[nome] = ia_campo
    merge["nutrientes"] = nutrientes_merge

    merge["alergenos"] = list(set(dados_ia.get("alergenos", []) + dados_ocr.get("alergenos", [])))
    merge["confianca_global"] = max(
        dados_ia.get("confianca_global", 0.0) or 0.0,
        dados_ocr.get("confianca_global", 0.0) or 0.0,
    )
    merge["campos_baixa_confianca"] = list(
        set(dados_ia.get("campos_baixa_confianca", []) + dados_ocr.get("campos_baixa_confianca", []))
    )
    return merge


def _preparar_resposta(dados: dict, status: str | None = None) -> dict:
    """Valida, busca duplicatas e monta resposta padrão."""
    dados, erros, avisos = validar_dados(dados)
    revisao = campos_baixa_confianca(dados)

    if status is None:
        status = dados.get("_fonte", "manual")

    # Se houver erros bloqueantes, ajusta status para revisão
    if erros:
        status = "revisao"
        avisos = erros + avisos

    duplicatas = buscar_duplicatas(dados)

    return {
        "status": status,
        "dados": dados,
        "duplicatas": duplicatas,
        "avisos": avisos,
        "campos_revisao": revisao,
    }


def confirmar_cadastro(payload: dict) -> dict:
    """
    Confirma cadastro ou atualização de alimento.
    payload esperado: dados (schema) + acao ('criar'|'atualizar') + alimento_id (se atualizar)
    """
    acao = payload.get("acao", "criar")
    dados = payload.get("dados", {})
    dados, erros, avisos = validar_dados(dados)

    if erros:
        return {"sucesso": False, "erros": erros, "avisos": avisos, "alimento_id": None}

    alimento_id = payload.get("alimento_id")

    if acao == "atualizar" and alimento_id:
        existente = (
            db.session.query(AlimentoIndustrializado)
            .filter(AlimentoIndustrializado.id == alimento_id)
            .first()
        )
        if not existente:
            return {"sucesso": False, "erros": ["Alimento não encontrado."], "alimento_id": None}
        _criar_versao(existente)
        _atualizar_alimento(existente, dados)
        db.session.commit()
        return {"sucesso": True, "erros": [], "avisos": avisos, "alimento_id": existente.id}

    # Verifica duplicidade novamente no momento da confirmação
    duplicatas = buscar_duplicatas(dados)
    if duplicatas:
        return {
            "sucesso": False,
            "erros": ["Existem duplicatas. Escolha atualizar o existente."],
            "duplicatas": duplicatas,
            "avisos": avisos,
            "alimento_id": None,
        }

    alimento = _novo_alimento(dados)
    db.session.add(alimento)
    db.session.commit()
    return {"sucesso": True, "erros": [], "avisos": avisos, "alimento_id": alimento.id}


def _novo_alimento(dados: dict) -> AlimentoIndustrializado:
    return AlimentoIndustrializado(
        codigo_barras=dados.get("codigo_barras"),
        nome=dados["nome"],
        marca=dados.get("marca"),
        fabricante=dados.get("fabricante"),
        peso_liquido=_get_valor(dados.get("peso_liquido", {}), "valor"),
        unidade_peso=dados.get("peso_liquido", {}).get("unidade"),
        porcao_qtd=_get_valor(dados.get("porcao", {}), "valor"),
        porcao_unidade=dados.get("porcao", {}).get("unidade"),
        ingredientes_lista=dados.get("ingredientes_lista"),
        alergenos=json.dumps(dados.get("alergenos", [])) if dados.get("alergenos") else None,
        fonte=dados.get("_fonte", "manual"),
        **_valores_nutrientes(dados.get("nutrientes", {})),
    )


def _atualizar_alimento(alimento: AlimentoIndustrializado, dados: dict) -> None:
    alimento.nome = dados["nome"]
    alimento.marca = dados.get("marca")
    alimento.fabricante = dados.get("fabricante")
    alimento.peso_liquido = _get_valor(dados.get("peso_liquido", {}), "valor")
    alimento.unidade_peso = dados.get("peso_liquido", {}).get("unidade")
    alimento.porcao_qtd = _get_valor(dados.get("porcao", {}), "valor")
    alimento.porcao_unidade = dados.get("porcao", {}).get("unidade")
    alimento.ingredientes_lista = dados.get("ingredientes_lista")
    alimento.alergenos = json.dumps(dados.get("alergenos", [])) if dados.get("alergenos") else None
    alimento.fonte = dados.get("_fonte", alimento.fonte)
    alimento.versao = (alimento.versao or 1) + 1

    for nome, coluna in MAPA_NUTRIENTES.items():
        setattr(alimento, coluna, _get_valor(dados.get("nutrientes", {}).get(nome, {}), "valor"))


def _criar_versao(alimento: AlimentoIndustrializado, motivo: str = "correcao") -> None:
    snapshot = {
        "codigo_barras": alimento.codigo_barras,
        "nome": alimento.nome,
        "marca": alimento.marca,
        "fabricante": alimento.fabricante,
        "peso_liquido": {"valor": float(alimento.peso_liquido) if alimento.peso_liquido else None, "unidade": alimento.unidade_peso},
        "porcao": {"valor": float(alimento.porcao_qtd) if alimento.porcao_qtd else None, "unidade": alimento.porcao_unidade},
        "nutrientes": {
            nome: {"valor": float(getattr(alimento, coluna)) if getattr(alimento, coluna) is not None else None, "unidade": "mg" if nome == "sodio_mg" else "kcal" if nome == "energia_kcal" else "g"}
            for nome, coluna in MAPA_NUTRIENTES.items()
        },
        "ingredientes_lista": alimento.ingredientes_lista,
        "alergenos": json.loads(alimento.alergenos) if alimento.alergenos else [],
        "fonte": alimento.fonte,
    }
    versao = AlimentoVersao(
        alimento_id=alimento.id,
        versao=alimento.versao or 1,
        dados_json=json.dumps(snapshot, ensure_ascii=False),
        motivo=motivo,
    )
    db.session.add(versao)


def _valores_nutrientes(nutrientes: dict) -> dict:
    return {
        coluna: _get_valor(nutrientes.get(nome, {}), "valor")
        for nome, coluna in MAPA_NUTRIENTES.items()
    }


def _get_valor(campo: dict | None, chave: str):
    if not campo:
        return None
    valor = campo.get(chave)
    if valor is None:
        return None
    try:
        return float(valor)
    except (ValueError, TypeError):
        return None
