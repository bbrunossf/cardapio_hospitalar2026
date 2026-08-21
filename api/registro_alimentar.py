"""Blueprint "Registro Alimentar 48h" — consumo do paciente ANTES do plano.

Plano: docs/registro_alimentar_48h.md (decidido 19/08/2026, em implementação).

Pipeline (híbrido e auditável):
  1. ESTRUTURAÇÃO — LLM via API isolada (5010) `/estruturar-registro`:
     texto livre → itens {dia, refeicao, descricao, valor, unidade}
     (o LLM NÃO calcula nutrientes nesta etapa)
  2. LOOKUP FORÇADO NO BANCO (determinístico) por item, com precedência
     pratos → industrializados → ingredientes; tokens exatos → fuzzy → semântica
  3. CONVERSÃO de medida (g direto, kg, ml, medidas_caseiras específica/genérica)
  4. CÁLCULO local por origem (prato=view × g/porcao_padrao_g;
     industrializado=rótulo porção × g/porcao_padrao_g; ingrediente=100g × g/100;
     estimado=LLM /estimar — badge)
  5. AGREGAÇÃO por dia (totais auditáveis item a item)

Fluxo em 2 passos (padrão Posso Comer): `/processar` NÃO grava (dry-run, mostra
itens ambíguos/revisar); `/confirmar` re-processa com as resoluções do
nutricionista e GRAVA (status 'processado', v1 grava direto — decisão 19/08).

Escopo: herda por dono via `pacientes.criado_por` (authz.paciente_acessivel).
"""
import os
import re
import unicodedata
from datetime import date, timedelta
from difflib import SequenceMatcher

import httpx
from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user
from sqlalchemy import text

from authz import paciente_acessivel
from extensions import db
from models_registro import RegistroAlimentar, RegistroAlimentarItem

registro_bp = Blueprint("registro_alimentar", __name__)

API_URL = os.getenv("POSSO_COMER_API_URL", "http://127.0.0.1:5010")
API_TIMEOUT = 30

# Nutrientes persistidos em registro_alimentar_itens (ordem de exibição)
NUTRIENTES = [
    "energia_kcal", "carboidratos_g", "proteinas_g", "gorduras_totais_g",
    "fibras_g", "sodio_mg", "calcio_mg", "ferro_mg", "potassio_mg",
    "fosforo_mg", "vit_c_mg",
]

# Mapeamento para as colunas da fonte (nomes singulares no view/ingredientes)
PRATO_MAPA = {  # vw_pratos_nutricional — nutrientes POR PORÇÃO PADRÃO
    "energia_kcal": "energia_kcal", "carboidratos_g": "carboidrato_g",
    "proteinas_g": "proteina_g", "gorduras_totais_g": "lipidios_g",
    "fibras_g": "fibra_alimentar_g", "sodio_mg": "sodio_mg",
    "calcio_mg": "calcio_mg", "ferro_mg": "ferro_mg", "potassio_mg": "potassio_mg",
    "fosforo_mg": "fosforo_mg", "vit_c_mg": "vit_c_mg",
}
ING_MAPA = PRATO_MAPA  # ingredientes: mesmas colunas (100g)
IND_MAPA = {  # alimentos_industrializados — rótulo da PORÇÃO
    "energia_kcal": "energia_kcal", "carboidratos_g": "carboidratos_g",
    "proteinas_g": "proteinas_g", "gorduras_totais_g": "gorduras_totais_g",
    "fibras_g": "fibras_g", "sodio_mg": "sodio_mg",
}

LIMITE_FUZZY = 0.82       # doc registro_alimentar_48h.md
LIMITE_SEMANTICO = 0.45   # distância cosseno máx; validar quando a coleção existir
PRECISAO_MIN_RELAXADO = 0.75  # nome do candidato ≥75% explicado pelos tokens da busca

# Tokens de ruído/preparo removidos na camada relaxada (nunca na camada exata)
STOPWORDS_BUSCA = {
    "de", "da", "do", "das", "dos", "em", "com", "sem", "e", "ou",
    "na", "no", "nas", "nos", "feito", "feita", "feitos", "feitas",
    "caseiro", "caseira", "natural",
}


# ---------------------------------------------------------------- utilidades
def _norm(s):
    """Minúsculas, sem acentos, sem pontuação -> lista de tokens."""
    s = unicodedata.normalize("NFD", s or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9 ]", " ", s.lower()).split()


def _norm_str(s):
    return " ".join(_norm(s))


def _num(v, default=None):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _mul(v, fator):
    if v is None:
        return None
    try:
        return round(float(v) * fator, 2)
    except (TypeError, ValueError):
        return None


def _chamar_api(path, payload):
    resp = httpx.post(f"{API_URL}{path}", json=payload, timeout=API_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------- cache por request
SQL_PRATOS = """
    SELECT p.id, p.nome, p.porcao_padrao_g, v.energia_kcal, v.carboidrato_g,
           v.proteina_g, v.lipidios_g, v.fibra_alimentar_g, v.sodio_mg,
           v.calcio_mg, v.ferro_mg, v.potassio_mg, v.fosforo_mg, v.vit_c_mg
    FROM pratos p
    JOIN vw_pratos_nutricional v ON v.prato_id = p.id
    WHERE p.desativado = 0 AND v.energia_kcal IS NOT NULL
"""
SQL_INDS = """
    SELECT id, nome, marca, porcao_padrao_g, energia_kcal, carboidratos_g,
           proteinas_g, gorduras_totais_g, fibras_g, sodio_mg
    FROM alimentos_industrializados
    WHERE desativado = 0 AND energia_kcal IS NOT NULL AND porcao_padrao_g IS NOT NULL
"""
SQL_INGS = """
    SELECT id, nome, energia_kcal, carboidrato_g, proteina_g, lipidios_g,
           fibra_alimentar_g, sodio_mg, calcio_mg, ferro_mg, potassio_mg,
           fosforo_mg, vit_c_mg
    FROM ingredientes WHERE desativado = 0
"""
SQL_MEDIDAS = """
    SELECT unidade, alimento_padrao, gramas, fonte
    FROM medidas_caseiras WHERE desativado = 0
"""


def _carregar_cache():
    """Dados de lookup carregados UMA vez por request (leitura, nunca escrita)."""
    cache = {"pratos": [], "inds": [], "ings": [], "medidas": {}}
    for r in db.session.execute(text(SQL_PRATOS)).mappings().all():
        d = dict(r)
        d["nome_busca"] = d["nome"]
        d["_toks"] = set(_norm(d["nome_busca"]))
        cache["pratos"].append(d)
    for r in db.session.execute(text(SQL_INDS)).mappings().all():
        d = dict(r)
        d["nome_busca"] = f"{d['nome']} {d['marca'] or ''}".strip()
        d["_toks"] = set(_norm(d["nome_busca"]))
        cache["inds"].append(d)
    for r in db.session.execute(text(SQL_INGS)).mappings().all():
        d = dict(r)
        d["nome_busca"] = d["nome"]
        d["_toks"] = set(_norm(d["nome_busca"]))
        cache["ings"].append(d)
    for r in db.session.execute(text(SQL_MEDIDAS)).mappings().all():
        cache["medidas"].setdefault(r["unidade"], []).append(dict(r))
    return cache


# ---------------------------------------------------------------- lookup (precedência fixa)
def _candidatos_exatos(fonte, descricao, cache):
    tokens = [t for t in _norm(descricao) if len(t) >= 3]
    if not tokens:
        return []
    out = []
    for row in cache[fonte]:
        rt = set(_norm(row["nome_busca"]))
        if all(t in rt for t in tokens):
            out.append(row)
    return out


def _candidatos_fuzzy(fonte, descricao, cache):
    q = _norm_str(descricao)
    qt = set(_norm(descricao))
    if not q:
        return []
    out = []
    for row in cache[fonte]:
        alvo = _norm_str(row["nome_busca"])
        ratio = SequenceMatcher(None, q, alvo).ratio()
        # regra doc (0.82) OU consulta como substring do nome, sempre com ≥1 token em comum
        if ratio >= LIMITE_FUZZY or (
            q in alvo and len(qt) >= 1 and qt & set(_norm(row["nome_busca"]))
        ):
            out.append((ratio, row))
    out.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in out]


def _precisao(row, tokens):
    """Fração do nome do candidato explicada pelos tokens da busca (0..1).
    Alta precisão = o candidato é (quase) exatamente o que foi relatado."""
    if not row["_toks"]:
        return 0.0
    return len(set(tokens) & row["_toks"]) / len(row["_toks"])


def _candidatos_relaxados(fonte, descricao, cache):
    """Camada intermediária entre tokens exatos e fuzzy (análise 20/08):

    2a. tokens exatos SEM stopwords de preparo ("sem óleo", "feito na"...)
    2b. "all-but-one": permite cair 1 token (ex.: "cebola roxa" -> "Cebola"),
        mas só aceita candidato com PRECISÃO >= 0.75 — o nome do candidato
        precisa ser ≥75% explicado pela busca. Isso evita o falso positivo
        "pão de forma" -> "Pão francês" (precisão 0.5) e "cebola roxa" ->
        "Isca de Frango Colorido (Pimentão, Cebola...)" (precisão baixa).
    """
    toks = [t for t in _norm(descricao) if len(t) >= 3 and t not in STOPWORDS_BUSCA]
    if not toks:
        return []

    out = [r for r in cache[fonte] if set(toks) <= r["_toks"]]
    if out:
        return out

    if len(toks) >= 2:
        out = []
        vistos = set()
        for i in range(len(toks)):
            resto = toks[:i] + toks[i + 1:]
            for r in cache[fonte]:
                if (set(resto) <= r["_toks"]
                        and _precisao(r, toks) >= PRECISAO_MIN_RELAXADO
                        and r["id"] not in vistos):
                    vistos.add(r["id"])
                    out.append(r)
        return out
    return []


def _fonte_chroma():
    """Coleção alimentos_embeddings (pode ainda não existir -> None)."""
    try:
        import chromadb
        client = chromadb.PersistentClient(path=os.getenv(
            "CHROMA_DB_PATH",
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "chroma_db"),
        ))
        return client.get_collection("alimentos_embeddings")
    except Exception:
        return None


def _buscar_semantico(descricao, cache):
    """Fallback semântico (chroma). Só roda quando a coleção alimentos_embeddings
    existir — hoje ela NÃO foi gerada (decisão 20/08: discutir formato com o Bruno).
    ids: 'prato_<id>' | 'ind_<id>' | 'ing_<id>'."""
    col = _fonte_chroma()
    if col is None:
        return None
    try:
        emb = _chamar_api("/embed", {"texto": descricao}).get("embedding")
    except httpx.HTTPError:
        return None
    if not emb:
        return None
    try:
        res = col.query(query_embeddings=[emb], n_results=5)
    except Exception:
        return None
    prefixo_origem = {"prato": "pratos", "ind": "inds", "ing": "ings"}
    for mid, dist in zip(res["ids"][0], res["distances"][0]):
        if dist > LIMITE_SEMANTICO:
            continue
        prefixo, _, id_s = str(mid).partition("_")
        origem = prefixo_origem.get(prefixo)
        if not origem:
            continue
        for row in cache[origem]:
            if str(row["id"]) == id_s:
                return {"origem": origem, "row": row, "semantico": True}
    return None


def _buscar_por_id(tipo, id_, cache):
    """Candidato escolhido pelo nutricionista na lista ambígua."""
    chave = {"prato": "pratos", "industrializado": "inds", "ingrediente": "ings"}.get(tipo)
    if not chave:
        return None
    for row in cache[chave]:
        if row["id"] == id_:
            return row
    return None


def buscar_match(descricao, cache, resolucao=None):
    """Retorna {'origem', 'id', 'nome', 'row'} | {'ambiguo', 'candidatos'} | None.

    Precedência de FONTE é regra de aplicação: prato casa primeiro, depois
    industrializado, por último ingrediente (item composto sempre resolve como
    prato do hospital antes de virar ingrediente avulso).
    """
    if resolucao and resolucao.get("candidato_tipo"):
        row = _buscar_por_id(resolucao["candidato_tipo"], resolucao.get("candidato_id"), cache)
        if row:
            return {"origem": resolucao["candidato_tipo"], "row": row}
        return None

    for origem in ("prato", "industrializado", "ingrediente"):
        chave = {"prato": "pratos", "industrializado": "inds", "ingrediente": "ings"}[origem]
        cands = _candidatos_exatos(chave, descricao, cache)
        if len(cands) == 1:
            return {"origem": origem, "row": cands[0]}
        if len(cands) > 1:
            return {"ambiguo": True, "candidatos": cands, "origem": origem}
    for origem in ("prato", "industrializado", "ingrediente"):
        chave = {"prato": "pratos", "industrializado": "inds", "ingrediente": "ings"}[origem]
        cands = _candidatos_relaxados(chave, descricao, cache)
        if len(cands) == 1:
            return {"origem": origem, "row": cands[0]}
        if len(cands) > 1:
            return {"ambiguo": True, "candidatos": cands, "origem": origem}
    for origem in ("prato", "industrializado", "ingrediente"):
        chave = {"prato": "pratos", "industrializado": "inds", "ingrediente": "ings"}[origem]
        cands = _candidatos_fuzzy(chave, descricao, cache)
        if len(cands) == 1:
            return {"origem": origem, "row": cands[0]}
        if len(cands) > 1:
            return {"ambiguo": True, "candidatos": cands, "origem": origem}
    return _buscar_semantico(descricao, cache)


# ---------------------------------------------------------------- conversão de medida
def converter_quantidade(valor, unidade, descricao, medidas):
    """Retorna (quantidade_g, observacao). Sem conversão -> (None, motivo)."""
    if valor is None:
        return None, "quantidade não informada pelo paciente"
    if unidade is None:
        return None, "quantidade sem unidade — informar gramas"

    u = (unidade or "").strip().lower()
    if u in ("g", "grama", "gramas"):
        return round(valor, 2), None
    if u == "kg":
        return round(valor * 1000, 2), None
    if u == "ml":
        return round(valor, 2), "volume (ml) tratado como gramas"

    # medida caseira: normaliza plural ("fatias" -> "fatia", "colheres" -> "colher")
    if u not in medidas:
        if u.endswith("es") and u[:-2] in medidas:
            u = u[:-2]
        elif u.endswith("s") and u[:-1] in medidas:
            u = u[:-1]
    rows = medidas.get(u)
    if not rows:
        return None, f"medida caseira '{unidade}' sem conversão cadastrada"

    toks = set(_norm(descricao))
    for r in rows:  # específico primeiro (ex.: fatia de 'pão de forma')
        alvo = r["alimento_padrao"]
        if alvo and set(_norm(alvo)) and set(_norm(alvo)) <= toks:
            return round(valor * float(r["gramas"]), 2), (
                f"conversão: {u} de '{alvo}' = {r['gramas']} g ({r['fonte']})"
            )
    for r in rows:  # genérico (alimento_padrao NULL)
        if not r["alimento_padrao"]:
            return round(valor * float(r["gramas"]), 2), (
                f"conversão: {u} (medida genérica) = {r['gramas']} g ({r['fonte']})"
            )
    return None, f"medida caseira '{unidade}' sem conversão para este alimento"


# ---------------------------------------------------------------- cálculo por origem
def calcular_nutrientes(origem, row, quantidade_g, descricao):
    """Retorna (nutrientes dict, observacao). origem estimado chama a API 5010."""
    if origem in ("prato", "ingrediente"):
        mapa = PRATO_MAPA if origem == "prato" else ING_MAPA
        fator = quantidade_g / float(row["porcao_padrao_g"]) if origem == "prato" \
            else quantidade_g / 100.0
        return {k: _mul(row.get(col), fator) for k, col in mapa.items()}, None

    if origem == "industrializado":
        porcao = float(row["porcao_padrao_g"]) if row.get("porcao_padrao_g") else 0
        if not porcao:
            return None, "industrializado sem porção padrão — revisar"
        fator = quantidade_g / porcao
        return {k: _mul(row.get(col), fator) for k, col in IND_MAPA.items()}, None

    if origem == "estimado":  # último recurso — badge ESTIMADO na UI
        est = _chamar_api("/estimar", {"descricao": descricao, "porcao_g": quantidade_g})
        return {
            "energia_kcal": _num(est.get("kcal_porcao")),
            "carboidratos_g": _num(est.get("carboidratos_g_porcao")),
            "proteinas_g": _num(est.get("proteinas_g_porcao")),
            "gorduras_totais_g": _num(est.get("gorduras_totais_g_porcao")),
            "fibras_g": _num(est.get("fibras_g_porcao")),
            "sodio_mg": _num(est.get("sodio_mg_porcao")),
        }, "valores estimados — alimento não cadastrado"

    return None, f"origem desconhecida: {origem}"


# ---------------------------------------------------------------- processamento
def _processar_item(raw, resolucao, cache):
    descricao = (raw.get("descricao") or "").strip()
    valor, unidade = raw.get("valor"), raw.get("unidade")
    item = {
        "dia": 1 if raw.get("dia") not in (1, 2) else raw["dia"],
        "refeicao": raw.get("refeicao") or "outro",
        "descricao": descricao,
        "quantidade_texto": (raw.get("quantidade_texto")
                             or (f"{valor} {unidade}".strip() if valor is not None else None)),
        "valor": valor, "unidade": unidade,
        "quantidade_g": None, "origem": None, "nome_encontrado": None,
        "fonte_dados": None, "estimado": False, "observacao": None,
        "revisar": False, "ambiguo": False, "candidatos": [], "nutrientes": None,
        "prato_id": None, "industrializado_id": None, "ingrediente_id": None,
    }
    if not descricao:
        item["revisar"] = True
        item["observacao"] = "item vazio"
        return item

    # 1. quantidade (resolução do nutricionista substitui a conversão)
    if resolucao and resolucao.get("quantidade_g") is not None:
        qg = round(_num(resolucao["quantidade_g"]), 2)
        qobs = "quantidade ajustada pelo nutricionista"
    else:
        qg, qobs = converter_quantidade(valor, unidade, descricao, cache["medidas"])
    item["quantidade_g"] = qg
    item["observacao"] = qobs
    if qg is None:
        item["revisar"] = True

    # 2. match no banco (precedência fixa; resolução força o candidato)
    match = buscar_match(descricao, cache, resolucao)
    if isinstance(match, dict) and match.get("ambiguo"):
        item["ambiguo"] = True
        item["revisar"] = True
        item["candidatos"] = [_candidato_publico(c, match["origem"])
                              for c in match["candidatos"]]
        return item
    if not match:
        # sem match no banco — vira estimado SÓ na confirmação (não gasta LLM no dry-run)
        item["revisar"] = True
        if not item["observacao"]:
            item["observacao"] = "item não encontrado no cadastro — confirmar para estimar"
        return item

    origem = match["origem"]
    item["origem"] = origem
    item["nome_encontrado"] = match["row"]["nome"]
    item["fonte_dados"] = "semântica" if match.get("semantico") else origem
    if origem == "prato":
        item["prato_id"] = match["row"]["id"]
    elif origem == "industrializado":
        item["industrializado_id"] = match["row"]["id"]
    else:
        item["ingrediente_id"] = match["row"]["id"]
    if qg is None:
        item["revisar"] = True
        return item

    # 3. cálculo (determinístico; estimado só quando o item já veio resolvido)
    try:
        nutri, obs = calcular_nutrientes(origem, match["row"], qg, descricao)
    except httpx.HTTPError as e:
        nutri, obs = None, f"API de estimativa indisponível: {e}"
    item["nutrientes"] = nutri
    item["estimado"] = origem == "estimado"
    if obs:
        # preserva a conversão de medida (qobs) junto com a observação do cálculo
        item["observacao"] = "; ".join(
            x for x in (item.get("observacao"), obs) if x)
    return item


def _candidato_publico(row, origem):
    """Candidato para a UI (kcal/100g: prato vem da view por porção padrão)."""
    kcal = None
    if row.get("energia_kcal") is not None:
        if origem == "prato":
            porcao = _num(row.get("porcao_padrao_g")) or 100
            kcal = round(_num(row["energia_kcal"]) * 100 / porcao, 1)
        else:
            kcal = round(_num(row["energia_kcal"]), 1)
    return {"tipo": origem, "id": row["id"], "nome": row["nome_busca"], "kcal_100g": kcal}


def _processar_texto(texto, resolucoes, cache):
    """Estrutura via API 5010 e roda o pipeline; retorna (itens, alertas). NÃO grava."""
    dados = _chamar_api("/estruturar-registro", {"texto": texto})
    itens_raw = dados.get("itens") or []
    return _processar_estruturado(itens_raw, resolucoes, cache)


def _processar_estruturado(itens_raw, resolucoes, cache):
    """Roda o pipeline sobre itens JÁ estruturados (dry-run ou re-processamento
    do /confirmar — lá o texto NÃO é re-estruturado para os índices das
    resoluções do nutricionista continuarem alinhados)."""
    itens = []
    for i, raw in enumerate(itens_raw):
        res = (resolucoes or {}).get(i) or {}
        itens.append(_processar_item(raw, res, cache))

    alertas = []
    if not itens:
        alertas.append("Nenhum item identificado no relato.")
    sem_match = [it for it in itens if it["origem"] is None and not it["ambiguo"]]
    if sem_match and _fonte_chroma() is None:
        alertas.append(
            "Busca semântica indisponível (coleção alimentos_embeddings não gerada) — "
            "itens sem match por tokens/fuzzy serão estimados na confirmação."
        )
    return itens, alertas


def _agregar(itens):
    """Totais consumidos por dia (soma de não-None; sem dado -> None = 'não informado')."""
    por_dia = {}
    for it in itens:
        dia = it["dia"]
        d = por_dia.setdefault(dia, {k: 0.0 for k in NUTRIENTES})
        d["_n_itens"] = d.get("_n_itens", 0) + 1
        for k in NUTRIENTES:
            v = (it.get("nutrientes") or {}).get(k)
            if v is not None:
                d[k] += float(v)
                d["_tem_" + k] = True
    out = []
    for dia in sorted(por_dia):
        d = por_dia[dia]
        totais = {k: (round(d[k], 1) if d.get("_tem_" + k) else None) for k in NUTRIENTES}
        out.append({"dia": dia, "itens": d["_n_itens"], "nutrientes": totais})
    return out


def _item_publico(it):
    return {k: it.get(k) for k in (
        "dia", "refeicao", "descricao", "quantidade_texto", "valor", "unidade",
        "quantidade_g", "origem", "nome_encontrado", "fonte_dados", "estimado",
        "observacao", "revisar", "ambiguo", "candidatos", "nutrientes",
    )}


def _item_db_publico(it):
    """Item persistido (auditoria/CRUD) no formato público da API."""
    nutri = {k: (_num(getattr(it, k)) if getattr(it, k) is not None else None)
             for k in NUTRIENTES}
    return {
        "id": it.id, "dia": it.dia, "refeicao": it.refeicao,
        "descricao": it.descricao, "quantidade_texto": it.quantidade_texto,
        "quantidade_g": _num(it.quantidade_g), "origem": it.origem,
        "estimado": bool(it.estimado), "observacao": it.observacao,
        "nutrientes": nutri,
    }


# ---------------------------------------------------------------- rotas
@registro_bp.route("/registro-alimentar")
def pagina_registro():
    """Página (regra UX: sempre por paciente — seleção no topo)."""
    return render_template("registro_alimentar.html")


@registro_bp.route("/api/registro-alimentar/processar", methods=["POST"])
def api_processar():
    """Dry-run: estrutura + lookup + conversão + cálculo; NÃO grava.

    Body: {paciente_id, texto}. Itens ambíguos/revisar voltam marcados para o
    nutricionista resolver antes de /confirmar.
    """
    data = request.get_json(silent=True) or {}
    paciente_id = data.get("paciente_id")
    texto = (data.get("texto") or "").strip()
    if not paciente_id:
        return jsonify({"erro": "paciente_id obrigatório"}), 400
    if not paciente_acessivel(paciente_id):
        return jsonify({"erro": "Paciente não encontrado."}), 404
    if not texto:
        return jsonify({"erro": "informe o texto do registro alimentar"}), 400
    if len(texto) > 20_000:
        return jsonify({"erro": "texto muito longo (máx 20.000 caracteres)"}), 400

    cache = _carregar_cache()
    try:
        itens, alertas = _processar_texto(texto, None, cache)
    except httpx.HTTPError as e:
        return jsonify({"erro": f"API de estruturação indisponível: {e}"}), 502

    return jsonify({
        "itens": [_item_publico(it) for it in itens],
        "totais_por_dia": _agregar(itens),
        "alertas": alertas,
    })


@registro_bp.route("/api/registro-alimentar/confirmar", methods=["POST"])
def api_confirmar():
    """Re-processa com as resoluções do nutricionista e GRAVA (status processado).

    Body: {paciente_id, texto, itens: [{dia, refeicao, descricao, valor, unidade,
    quantidade_g?, candidato_tipo?, candidato_id?}]}. O servidor é a fonte da
    verdade do cálculo — nunca confia em nutrientes vindos do cliente.
    """
    data = request.get_json(silent=True) or {}
    paciente_id = data.get("paciente_id")
    texto = (data.get("texto") or "").strip()
    itens_raw = data.get("itens") or []
    if not paciente_id:
        return jsonify({"erro": "paciente_id obrigatório"}), 400
    if not paciente_acessivel(paciente_id):
        return jsonify({"erro": "Paciente não encontrado."}), 404
    if not texto:
        return jsonify({"erro": "informe o texto do registro alimentar"}), 400
    if not isinstance(itens_raw, list) or not itens_raw:
        return jsonify({"erro": "itens estruturados obrigatórios (processe o relato antes)"}), 400

    cache = _carregar_cache()
    # Os itens vêm do dry-run (mesma ordem) — o texto NÃO é re-estruturado aqui
    # para as resoluções do nutricionista continuarem alinhadas por índice.
    estruturados = [{
        "dia": it.get("dia", 1),
        "refeicao": it.get("refeicao") or "outro",
        "descricao": it.get("descricao") or "",
        "valor": it.get("valor"),
        "unidade": it.get("unidade"),
        "quantidade_texto": it.get("quantidade_texto"),
    } for it in itens_raw]
    resolucoes = {}
    for i, it in enumerate(itens_raw):
        resolucoes[i] = {
            "candidato_tipo": it.get("candidato_tipo"),
            "candidato_id": it.get("candidato_id"),
            "quantidade_g": it.get("quantidade_g"),
        }
    try:
        itens, alertas = _processar_estruturado(estruturados, resolucoes, cache)
    except httpx.HTTPError as e:
        return jsonify({"erro": f"API de estruturação indisponível: {e}"}), 502

    # itens sem match (não resolvidos pelo nutricionista) viram estimados aqui
    for it in itens:
        if it["origem"] is None and not it["ambiguo"]:
            it["origem"] = "estimado"
            it["estimado"] = True
            it["fonte_dados"] = "estimado"
            if it["quantidade_g"] is not None and it["nutrientes"] is None:
                try:
                    it["nutrientes"], obs = calcular_nutrientes(
                        "estimado", None, it["quantidade_g"], it["descricao"])
                    it["observacao"] = obs or it["observacao"]
                except httpx.HTTPError as e:
                    it["observacao"] = f"estimativa indisponível: {e}"

    hoje = date.today()
    reg = RegistroAlimentar(
        paciente_id=paciente_id,
        data_inicio=hoje - timedelta(days=1),
        data_fim=hoje,
        texto_original=texto,
        status="processado",
        criado_por=current_user.id if current_user.is_authenticated else None,
    )
    db.session.add(reg)
    db.session.flush()
    for ordem, it in enumerate(itens):
        item = RegistroAlimentarItem(
            registro_id=reg.id,
            dia=it["dia"], refeicao=it["refeicao"], ordem=ordem,
            descricao=it["descricao"], quantidade_texto=it["quantidade_texto"],
            quantidade_g=it["quantidade_g"], origem=it["origem"] or "estimado",
            prato_id=it.get("prato_id"), industrializado_id=it.get("industrializado_id"),
            ingrediente_id=it.get("ingrediente_id"), estimado=bool(it["estimado"]),
            observacao=(it["observacao"] or "")[:255],
            **{k: v for k, v in (it["nutrientes"] or {}).items() if v is not None},
        )
        db.session.add(item)
    db.session.commit()

    return jsonify({
        "registro_id": reg.id,
        "itens": [_item_publico(it) for it in itens],
        "totais_por_dia": _agregar(itens),
        "alertas": alertas,
    })


@registro_bp.route("/api/registro-alimentar")
def api_listar():
    """Registros de um paciente (regra UX: sempre por paciente, nunca lista geral)."""
    pid = request.args.get("paciente_id", type=int)
    if not pid:
        return jsonify({"erro": "paciente_id obrigatório"}), 400
    if not paciente_acessivel(pid):
        return jsonify({"erro": "Paciente não encontrado."}), 404
    rows = db.session.execute(text("""
        SELECT r.id, r.data_inicio, r.data_fim, r.status, r.criado_em, r.criado_por,
               u.nome AS criado_por_nome,
               COUNT(i.id) AS n_itens,
               ROUND(SUM(CASE WHEN i.dia = 1 AND i.desativado = 0
                              THEN i.energia_kcal END), 1) AS kcal_dia1,
               ROUND(SUM(CASE WHEN i.dia = 2 AND i.desativado = 0
                              THEN i.energia_kcal END), 1) AS kcal_dia2
        FROM registros_alimentares r
        LEFT JOIN registro_alimentar_itens i
               ON i.registro_id = r.id AND i.desativado = 0
        LEFT JOIN usuarios u ON u.id = r.criado_por
        WHERE r.paciente_id = :pid AND r.desativado = 0
        GROUP BY r.id
        ORDER BY r.id DESC
    """), {"pid": pid}).mappings().all()
    return jsonify([{
        "id": r["id"],
        # SQLite via text() devolve datas como string ISO (sem isoformat)
        "data_inicio": r["data_inicio"] or None,
        "data_fim": r["data_fim"] or None,
        "status": r["status"], "n_itens": r["n_itens"],
        "kcal_dia1": r["kcal_dia1"], "kcal_dia2": r["kcal_dia2"],
        "criado_em": r["criado_em"] or None,
        "criado_por": r["criado_por"], "criado_por_nome": r["criado_por_nome"],
    } for r in rows])


@registro_bp.route("/api/registro-alimentar/<int:registro_id>", methods=["PATCH"])
def api_atualizar_registro(registro_id):
    """Atualiza cabeçalho (status/datas/texto). Correção de itens é por item."""
    reg = db.session.get(RegistroAlimentar, registro_id)
    if not reg or reg.desativado:
        return jsonify({"erro": "Registro não encontrado."}), 404
    if not paciente_acessivel(reg.paciente_id):
        return jsonify({"erro": "Registro não encontrado."}), 404

    data = request.get_json(silent=True) or {}
    if "status" in data:
        st = data["status"]
        if st not in ("rascunho", "processado", "revisado"):
            return jsonify({"erro": "status inválido (rascunho|processado|revisado)"}), 400
        reg.status = st
    for campo in ("data_inicio", "data_fim"):
        if campo in data and data[campo]:
            try:
                setattr(reg, campo, date.fromisoformat(str(data[campo])))
            except ValueError:
                return jsonify({"erro": f"{campo} inválido (use AAAA-MM-DD)"}), 400
    if data.get("texto_original") is not None:
        t = str(data["texto_original"]).strip()
        if not t:
            return jsonify({"erro": "texto_original não pode ser vazio"}), 400
        reg.texto_original = t
    db.session.commit()
    return jsonify({"ok": True, "registro_id": reg.id, "status": reg.status})


@registro_bp.route("/api/registro-alimentar/itens/<int:item_id>", methods=["PATCH"])
def api_corrigir_item(item_id):
    """Correção manual de item — o servidor RECALCULA os nutrientes (fonte da
    verdade); o cliente só envia {quantidade_g?, candidato_tipo?, candidato_id?}."""
    item = db.session.get(RegistroAlimentarItem, item_id)
    if not item or item.desativado:
        return jsonify({"erro": "Item não encontrado."}), 404
    reg = db.session.get(RegistroAlimentar, item.registro_id)
    if not reg or reg.desativado or not paciente_acessivel(reg.paciente_id):
        return jsonify({"erro": "Item não encontrado."}), 404

    data = request.get_json(silent=True) or {}
    cache = _carregar_cache()
    origem = item.origem
    row = None

    # candidato novo (correção de origem) — 'estimado' força estimativa LLM
    ct = data.get("candidato_tipo")
    if ct:
        if ct == "estimado":
            origem = "estimado"
            item.prato_id = item.industrializado_id = item.ingrediente_id = None
        else:
            row = _buscar_por_id(ct, data.get("candidato_id"), cache)
            if not row:
                return jsonify({"erro": "candidato não encontrado"}), 404
            origem = ct
            item.prato_id = item.industrializado_id = item.ingrediente_id = None
            if origem == "prato":
                item.prato_id = row["id"]
            elif origem == "industrializado":
                item.industrializado_id = row["id"]
            else:
                item.ingrediente_id = row["id"]
        item.origem = origem
    elif item.prato_id:
        row = _buscar_por_id("prato", item.prato_id, cache)
    elif item.industrializado_id:
        row = _buscar_por_id("industrializado", item.industrializado_id, cache)
    elif item.ingrediente_id:
        row = _buscar_por_id("ingrediente", item.ingrediente_id, cache)

    if data.get("quantidade_g") is not None:
        qg = round(_num(data["quantidade_g"]), 2)
        if not qg or qg <= 0:
            return jsonify({"erro": "quantidade_g deve ser > 0"}), 400
        item.quantidade_g = qg
    qg = _num(item.quantidade_g)

    if qg:
        try:
            if origem == "estimado":
                nutri, obs = calcular_nutrientes("estimado", None, qg, item.descricao)
                item.estimado = True
            else:
                if row is None:
                    return jsonify({"erro": "item sem fonte cadastrada para recalcular"}), 400
                nutri, obs = calcular_nutrientes(origem, row, qg, item.descricao)
                item.estimado = False
            for k, v in (nutri or {}).items():
                setattr(item, k, v)
            if obs:
                item.observacao = obs[:255]
        except httpx.HTTPError as e:
            return jsonify({"erro": f"API de estimativa indisponível: {e}"}), 502

    if reg.status != "rascunho":
        reg.status = "revisado"  # correção manual ⇒ registro revisado
    db.session.commit()
    return jsonify(_item_db_publico(item))


@registro_bp.route("/api/registro-alimentar/<int:registro_id>", methods=["DELETE"])
def api_excluir_registro(registro_id):
    """Exclusão SOFT (desativado=1) — auditoria preservada (convenção do banco)."""
    reg = db.session.get(RegistroAlimentar, registro_id)
    if not reg or reg.desativado:
        return jsonify({"erro": "Registro não encontrado."}), 404
    if not paciente_acessivel(reg.paciente_id):
        return jsonify({"erro": "Registro não encontrado."}), 404
    reg.desativado = True
    db.session.commit()
    return jsonify({"ok": True, "registro_id": reg.id})


@registro_bp.route("/api/registro-alimentar/itens/<int:item_id>", methods=["DELETE"])
def api_excluir_item(item_id):
    """Exclusão SOFT de item (desativado=1)."""
    item = db.session.get(RegistroAlimentarItem, item_id)
    if not item or item.desativado:
        return jsonify({"erro": "Item não encontrado."}), 404
    reg = db.session.get(RegistroAlimentar, item.registro_id)
    if not reg or reg.desativado or not paciente_acessivel(reg.paciente_id):
        return jsonify({"erro": "Item não encontrado."}), 404
    item.desativado = True
    if reg.status != "rascunho":
        reg.status = "revisado"
    db.session.commit()
    return jsonify({"ok": True, "item_id": item.id})


@registro_bp.route("/api/registro-alimentar/<int:registro_id>")
def api_detalhe(registro_id):
    """Registro persistido (auditoria): cabeçalho + itens + totais."""
    reg = db.session.get(RegistroAlimentar, registro_id)
    if not reg or reg.desativado:
        return jsonify({"erro": "Registro não encontrado."}), 404
    if not paciente_acessivel(reg.paciente_id):
        return jsonify({"erro": "Registro não encontrado."}), 404

    itens = [_item_db_publico(it) for it in reg.itens if not it.desativado]
    return jsonify({
        "registro_id": reg.id,
        "paciente_id": reg.paciente_id,
        "status": reg.status,
        "data_inicio": reg.data_inicio.isoformat() if reg.data_inicio else None,
        "data_fim": reg.data_fim.isoformat() if reg.data_fim else None,
        "criado_por": reg.criado_por,
        "criado_em": reg.criado_em.isoformat() if reg.criado_em else None,
        "texto_original": reg.texto_original,
        "itens": itens,
        "totais_por_dia": _agregar([{
            "dia": it["dia"], "nutrientes": it["nutrientes"],
        } for it in itens]),
    })
