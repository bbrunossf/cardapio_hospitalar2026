"""
Blueprint de Planos Nutricionais por Paciente.

Fluxo:
  1. Nutricionista cadastra o paciente (api/paciente.py) e informa o objetivo.
  2. POST /api/planos → calcula TMB/GET/meta/macros via cálculo LOCAL
     (calculo_nutricional — default, determinístico) ou WolframAlpha
     (FONTE_CALCULO=wolfram, benchmark opcional) e salva o plano.
  3. POST /api/planos/<id>/cardapio → roda o PuLP com overrides do plano
     (energia ±10%, macros ±15%, objetivo TARGET) e salva o cardápio
     versionado (cardapios_salvos → dias → refeicoes).
"""
import os
from datetime import date

from flask import Blueprint, jsonify, redirect, render_template, request, url_for
from sqlalchemy import desc, text

from api.otimizacao import (carregar_dados_otimizacao, carregar_restricoes_paciente,
                            criar_modelo_otimizacao, resolver_e_extrair)
from authz import paciente_acessivel, plano_acessivel, query_pacientes
from extensions import db
from models_paciente import Paciente
from models_plano import (CardapioDia, CardapioRefeicao, CardapioSalvo,
                          PlanoNutricional, WolframConsulta)
from wolfram_client import ErroConfiguracao, WolframDietClient

plano_bp = Blueprint("plano", __name__, template_folder="../templates")

# Tolerâncias do plano convertidas em faixas de restrição no PuLP
TOL_ENERGIA = 0.10   # ±10% da meta_kcal
TOL_MACRO = 0.15     # ±15% das macros (g)

OBJETIVOS_VALIDOS = {"perder", "ganhar", "manter"}


def _calcular_idade(paciente: Paciente) -> int | None:
    """Idade em anos a partir da data de nascimento."""
    if not paciente.data_nascimento:
        return None
    hoje = date.today()
    nasc = paciente.data_nascimento
    return hoje.year - nasc.year - ((hoje.month, hoje.day) < (nasc.month, nasc.day))


def _dados_para_calculo(paciente: Paciente) -> dict:
    """Monta o dict de entrada do cálculo (local ou Wolfram) a partir do paciente."""
    return {
        "sexo": paciente.sexo or "M",
        "idade": _calcular_idade(paciente) or 30,
        "altura_cm": float(paciente.altura_cm or 0),
        "peso_kg": float(paciente.peso_kg or 0),
        "nivel_atividade_fisica": paciente.nivel_atividade_fisica or "moderado",
    }


def _fonte_calculo() -> str:
    """
    Fonte de cálculo do plano: 'local' (default) ou 'wolfram'.

    Lê FONTE_CALCULO do ambiente (o CLI do flask carrega .env). Se não estiver
    no ambiente, lê direto do arquivo .env — robustez caso o app rode fora do
    `flask run` (ex: gunicorn sem load_dotenv).
    """
    valor = os.environ.get("FONTE_CALCULO")
    if not valor:
        try:
            env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
            with open(env_path, encoding="utf-8") as fh:
                for linha in fh:
                    linha = linha.strip()
                    if linha.startswith("FONTE_CALCULO="):
                        valor = linha.split("=", 1)[1].strip().strip('"').strip("'")
                        break
        except OSError:
            pass
    return (valor or "local").strip().lower()


def _overrides_do_plano(plano: PlanoNutricional) -> dict:
    """
    Converte o plano em faixas de restrição para o PuLP:
      energia_kcal: meta ±10%
      proteina/carboidrato/lipidios (g): valor ±15%
    """
    overrides = {}
    if plano.meta_kcal is not None:
        meta = float(plano.meta_kcal)
        overrides["meta_kcal"] = meta
        overrides["energia_kcal"] = (round(meta * (1 - TOL_ENERGIA)), round(meta * (1 + TOL_ENERGIA)))
    for campo, nutriente in (("proteinas_g", "proteina"), ("carboidratos_g", "carboidrato"),
                             ("lipidios_g", "lipidios")):
        valor = getattr(plano, campo)
        if valor is not None:
            v = float(valor)
            overrides[nutriente] = (round(v * (1 - TOL_MACRO)), round(v * (1 + TOL_MACRO)))
    return overrides


# ---------------------------------------------------------------------------
# Páginas HTML
# ---------------------------------------------------------------------------

@plano_bp.route("/planos")
def pagina_lista_planos():
    """
    Ponto de entrada de planos: seleciona o paciente PRIMEIRO.
    Sem ?paciente_id → página de seleção; com ?paciente_id → redireciona
    para os planos daquele paciente (nunca mostra lista geral).
    """
    paciente_id = request.args.get("paciente_id", type=int)
    if paciente_id:
        if not paciente_acessivel(paciente_id):
            return "Paciente não encontrado.", 404
        return redirect(url_for("plano.pagina_planos_paciente", paciente_id=paciente_id))
    pacientes = query_pacientes().order_by(Paciente.nome).all()
    return render_template("planos_selecao.html", pacientes=pacientes)


@plano_bp.route("/pacientes/<int:paciente_id>/planos")
def pagina_planos_paciente(paciente_id):
    """Lista os planos de UM paciente (seleciona o paciente primeiro)."""
    paciente = paciente_acessivel(paciente_id)
    if not paciente:
        return "Paciente não encontrado.", 404

    planos = (db.session.query(PlanoNutricional)
              .filter(PlanoNutricional.paciente_id == paciente_id)
              .order_by(desc(PlanoNutricional.criado_em))
              .all())
    itens = []
    for plano in planos:
        data = plano.to_dict()
        data["paciente_nome"] = paciente.nome
        itens.append(data)

    # Dados para o bloco "Regras do cardápio" (personalização Fase 1)
    tipos_prato = [{"id": t[0], "nome": t[1]}
                   for t in db.session.execute(text(
                       "SELECT id, nome FROM tipos_preparacoes ORDER BY nome")).all()]
    pratos = [{"id": p[0], "nome": p[1]}
              for p in db.session.execute(text(
                  "SELECT id, nome FROM pratos WHERE desativado = 0 ORDER BY nome")).all()]
    ingredientes = [{"id": i[0], "nome": i[1]}
                    for i in db.session.execute(text(
                        "SELECT id, nome FROM ingredientes WHERE desativado = 0 ORDER BY nome")).all()]

    return render_template("planos.html", planos=itens, paciente=paciente,
                           tipos_prato=tipos_prato, pratos=pratos,
                           ingredientes=ingredientes)


@plano_bp.route("/planos/novo")
def pagina_novo_plano():
    """Formulário para criar um plano nutricional para um paciente."""
    pacientes = query_pacientes().order_by(Paciente.nome).all()
    paciente_id = request.args.get("paciente_id", type=int)
    if paciente_id and not paciente_acessivel(paciente_id):
        return "Paciente não encontrado.", 404
    return render_template("plano_form.html", pacientes=pacientes, paciente_id=paciente_id)


@plano_bp.route("/planos/<int:plano_id>")
def pagina_plano(plano_id):
    """Detalhe do plano + botão de gerar cardápio."""
    plano = db.session.get(PlanoNutricional, plano_id)
    if not plano or not plano_acessivel(plano):
        return "Plano não encontrado.", 404
    paciente = db.session.get(Paciente, plano.paciente_id)
    cardapios = (db.session.query(CardapioSalvo)
                 .filter(CardapioSalvo.plano_id == plano_id)
                 .order_by(desc(CardapioSalvo.criado_em)).all())
    return render_template("plano_detalhe.html", plano=plano, paciente=paciente, cardapios=cardapios)


# ---------------------------------------------------------------------------
# API REST — Planos
# ---------------------------------------------------------------------------

@plano_bp.route("/api/planos", methods=["POST"])
def api_criar_plano():
    """
    Calcula o plano nutricional (Wolfram + fallbacks) e salva.

    Payload: {
      paciente_id: int (obrigatório),
      objetivo: 'perder'|'ganhar'|'manter' (obrigatório),
      peso_alvo_kg?: float,
      prazo_dias?: int,          // prazo OU déficit
      deficit_diario_kcal?: float,
      perfil_macro?: 'equilibrado'|'hipocalorico'|'hiperproteico'|'hipolipidico'
    }
    """
    payload = request.get_json(silent=True) or {}

    paciente_id = payload.get("paciente_id")
    objetivo = (payload.get("objetivo") or "").strip().lower()
    if not paciente_id:
        return jsonify({"erro": "paciente_id é obrigatório."}), 400
    if objetivo not in OBJETIVOS_VALIDOS:
        return jsonify({"erro": f"objetivo deve ser um de: {sorted(OBJETIVOS_VALIDOS)}."}), 400

    paciente = paciente_acessivel(paciente_id)
    if not paciente:
        return jsonify({"erro": "Paciente não encontrado."}), 404
    if not paciente.peso_kg or not paciente.altura_cm:
        return jsonify({"erro": "Paciente precisa de peso_kg e altura_cm para o cálculo."}), 400

    meta = {
        "objetivo": objetivo,
        "peso_alvo_kg": payload.get("peso_alvo_kg") or float(paciente.peso_kg),
        "prazo_dias": payload.get("prazo_dias"),
        "deficit_diario_kcal": payload.get("deficit_diario_kcal"),
        "perfil_macro": payload.get("perfil_macro") or "equilibrado",
    }

    try:
        fonte_calculo = _fonte_calculo()
        if fonte_calculo == "wolfram":
            cliente = WolframDietClient()
            try:
                resultado = cliente.calcular_plano_completo(_dados_para_calculo(paciente), meta)
            except Exception as e:  # rede/quota — não derruba a API
                return jsonify({"erro": f"Falha ao consultar WolframAlpha: {e}"}), 502
            consultas = cliente.consultas
        else:
            from calculo_nutricional import calcular_plano_completo as calcular_plano_local
            try:
                resultado = calcular_plano_local(_dados_para_calculo(paciente), meta)
            except (TypeError, ValueError) as e:
                return jsonify({"erro": f"Dados inválidos para o cálculo: {e}"}), 400
            consultas = resultado.get("consultas", [])
    except ErroConfiguracao as e:
        return jsonify({"erro": str(e)}), 500

    plano = PlanoNutricional(
        paciente_id=paciente_id,
        objetivo=objetivo,
        peso_alvo_kg=meta["peso_alvo_kg"],
        prazo_dias=resultado.get("prazo_dias"),
        deficit_diario_kcal=resultado.get("deficit_diario_kcal"),
        nivel_atividade=paciente.nivel_atividade_fisica,
        perfil_macro=meta["perfil_macro"],
        tmb_kcal=resultado.get("tmb_kcal"),
        get_kcal=resultado.get("get_kcal"),
        meta_kcal=resultado.get("meta_kcal"),
        proteinas_g=resultado.get("proteinas_g"),
        carboidratos_g=resultado.get("carboidratos_g"),
        lipidios_g=resultado.get("lipidios_g"),
        proteinas_pct=resultado.get("proteinas_pct"),
        carboidratos_pct=resultado.get("carboidratos_pct"),
        lipidios_pct=resultado.get("lipidios_pct"),
        fonte=resultado.get("fonte", "fallback"),
        alertas="\n".join(resultado.get("alertas", [])),
        status="ativo",
    )
    db.session.add(plano)
    db.session.flush()  # garante plano.id

    # Auditoria das consultas (wolfram_consultas — fonte 'local' ou API)
    for consulta in consultas:
        db.session.add(WolframConsulta(
            plano_id=plano.id,
            query=consulta.get("query", "")[:500],
            api=consulta.get("api", ""),
            resposta=consulta.get("resposta"),
            ok=consulta.get("ok", False),
        ))

    db.session.commit()
    return jsonify(plano.to_dict()), 201


@plano_bp.route("/api/pacientes/<int:paciente_id>/planos", methods=["GET"])
def api_listar_planos(paciente_id):
    """Lista os planos de um paciente (mais recentes primeiro)."""
    paciente = paciente_acessivel(paciente_id)
    if not paciente:
        return jsonify({"erro": "Paciente não encontrado."}), 404
    planos = (db.session.query(PlanoNutricional)
              .filter(PlanoNutricional.paciente_id == paciente_id)
              .order_by(desc(PlanoNutricional.criado_em))
              .all())
    return jsonify([p.to_dict() for p in planos])


@plano_bp.route("/api/planos/<int:plano_id>", methods=["GET"])
def api_obter_plano(plano_id):
    """Detalhe de um plano (com cardápios salvos)."""
    plano = db.session.get(PlanoNutricional, plano_id)
    if not plano or not plano_acessivel(plano):
        return jsonify({"erro": "Plano não encontrado."}), 404
    data = plano.to_dict()
    cardapios = (db.session.query(CardapioSalvo)
                 .filter(CardapioSalvo.plano_id == plano_id)
                 .order_by(desc(CardapioSalvo.criado_em)).all())
    data["cardapios"] = [{
        "id": c.id, "nome": c.nome, "versao": c.versao, "dias": c.dias,
        "data_inicio": str(c.data_inicio) if c.data_inicio else None,
        "data_fim": str(c.data_fim) if c.data_fim else None,
    } for c in cardapios]
    return jsonify(data)


@plano_bp.route("/api/planos/<int:plano_id>", methods=["DELETE"])
def api_cancelar_plano(plano_id):
    """Cancela um plano (status → cancelado; mantém histórico)."""
    plano = db.session.get(PlanoNutricional, plano_id)
    if not plano or not plano_acessivel(plano):
        return jsonify({"erro": "Plano não encontrado."}), 404
    plano.status = "cancelado"
    db.session.commit()
    return jsonify(plano.to_dict())


# ---------------------------------------------------------------------------
# API REST — Simulador interativo (Fase 2, d3.js)
# ---------------------------------------------------------------------------

@plano_bp.route("/planos/<int:plano_id>/simulador")
def pagina_simulador(plano_id):
    """Página do simulador de estratégia (arrastar ingestão/peso-alvo)."""
    plano = db.session.get(PlanoNutricional, plano_id)
    if not plano or not plano_acessivel(plano):
        return "Plano não encontrado.", 404
    paciente = db.session.get(Paciente, plano.paciente_id)
    return render_template("simulador.html", plano=plano, paciente=paciente)


@plano_bp.route("/api/planos/<int:plano_id>/simulador/dados")
def api_dados_simulador(plano_id):
    """Dados iniciais do simulador: plano + projeção semanal (7700 kcal/kg)."""
    plano = db.session.get(PlanoNutricional, plano_id)
    if not plano or not plano_acessivel(plano):
        return jsonify({"erro": "Plano não encontrado."}), 404
    paciente = db.session.get(Paciente, plano.paciente_id)

    get_kcal = float(plano.get_kcal or 0)
    meta_kcal = float(plano.meta_kcal or get_kcal)
    peso_atual = float(paciente.peso_kg or 0) if paciente else 0.0
    peso_alvo = float(plano.peso_alvo_kg or peso_atual)
    prazo_dias = plano.prazo_dias or 56

    from calculo_nutricional import projecao_peso
    projecao = projecao_peso(peso_atual, meta_kcal, get_kcal, prazo_dias)

    return jsonify({
        "plano_id": plano.id,
        "paciente": {"id": paciente.id, "nome": paciente.nome} if paciente else None,
        "objetivo": plano.objetivo,
        "peso_atual_kg": peso_atual,
        "peso_alvo_kg": peso_alvo,
        "prazo_dias": prazo_dias,
        "get_kcal": get_kcal,
        "meta_kcal": meta_kcal,
        "deficit_diario_kcal": float(plano.deficit_diario_kcal or 0),
        "perfil_macro": plano.perfil_macro or "equilibrado",
        "projecao": projecao,
    })


@plano_bp.route("/api/planos/<int:plano_id>", methods=["PATCH"])
def api_ajustar_plano(plano_id):
    """
    Ajusta campos do plano a partir do simulador.

    Campos aceitos: peso_alvo_kg, prazo_dias, meta_kcal, deficit_diario_kcal,
    perfil_macro. Se meta_kcal mudar e macros não forem enviadas, recalcula
    as macros pelo perfil (calculo_nutricional.distribuir_macros).
    """
    plano = db.session.get(PlanoNutricional, plano_id)
    if not plano or not plano_acessivel(plano):
        return jsonify({"erro": "Plano não encontrado."}), 404
    if plano.status != "ativo":
        return jsonify({"erro": "Plano não está ativo."}), 400

    payload = request.get_json(silent=True) or {}
    permitidos = {"peso_alvo_kg", "prazo_dias", "meta_kcal",
                  "deficit_diario_kcal", "perfil_macro"}
    extras = set(payload) - permitidos
    if extras:
        return jsonify({"erro": f"Campos não permitidos: {sorted(extras)}"}), 400

    meta_antiga = float(plano.meta_kcal) if plano.meta_kcal is not None else None
    perfil = payload.get("perfil_macro") or plano.perfil_macro or "equilibrado"

    for campo in permitidos:
        if campo not in payload:
            continue
        valor = payload[campo]
        if campo == "prazo_dias":
            valor = int(valor) if valor is not None else None
        elif campo in ("peso_alvo_kg", "meta_kcal", "deficit_diario_kcal"):
            valor = float(valor) if valor is not None else None
        setattr(plano, campo, valor)

    # Recalcula macros se a meta mudou (macros não são enviadas pelo simulador)
    nova_meta = float(plano.meta_kcal) if plano.meta_kcal is not None else None
    if nova_meta is not None and (meta_antiga is None or meta_antiga != nova_meta):
        from calculo_nutricional import distribuir_macros
        mac = distribuir_macros(nova_meta, perfil)
        plano.proteinas_pct = mac["proteinas_pct"]
        plano.carboidratos_pct = mac["carboidratos_pct"]
        plano.lipidios_pct = mac["lipidios_pct"]
        plano.proteinas_g = mac["proteinas_g"]
        plano.carboidratos_g = mac["carboidratos_g"]
        plano.lipidios_g = mac["lipidios_g"]

    db.session.commit()
    return jsonify(plano.to_dict())


# ---------------------------------------------------------------------------
# API REST — Cardápio do plano
# ---------------------------------------------------------------------------

@plano_bp.route("/api/planos/<int:plano_id>/cardapio", methods=["POST"])
def api_gerar_cardapio(plano_id):
    """
    Gera o cardápio dimensionado do plano via PuLP com overrides e salva
    versionado (cardapios_salvos → cardapio_dias → cardapio_refeicoes).

    Payload: {dieta?: 'LIVRE', dias?: int (1-30), versao?: int}
    """
    plano = db.session.get(PlanoNutricional, plano_id)
    if not plano or not plano_acessivel(plano):
        return jsonify({"erro": "Plano não encontrado."}), 404
    if plano.status != "ativo":
        return jsonify({"erro": "Plano não está ativo."}), 400

    payload = request.get_json(silent=True) or {}
    dieta_nome = (payload.get("dieta") or "LIVRE").strip().upper()
    dias = int(payload.get("dias", 7))
    if dias < 1 or dias > 30:
        return jsonify({"erro": "dias deve estar entre 1 e 30."}), 400

    try:
        dados = carregar_dados_otimizacao(dieta_nome, paciente_id=plano.paciente_id)
    except ValueError as e:
        return jsonify({"erro": str(e)}), 404

    overrides = _overrides_do_plano(plano)
    # Fase 1 personalização: faixas do paciente vencem as do plano (precedência
    # dieta → plano → paciente). Exclusões já filtraram os pratos no carregador.
    overrides.update(carregar_restricoes_paciente(plano.paciente_id))
    try:
        problema, X, dados = criar_modelo_otimizacao(dados, dias=dias, overrides=overrides, objetivo="target")
        resultado = resolver_e_extrair(problema, X, dados, dias=dias)
    except Exception as e:
        return jsonify({"erro": f"Falha na otimização: {e}"}), 500

    if resultado["status"] != "Optimal":
        return jsonify({
            "erro": f"Modelo inviável com os overrides do plano ({resultado['status']}). "
                    "Verifique as restrições ou ajuste prazo/meta.",
            "resultado": resultado,
        }), 422

    # Persiste o cardápio versionado
    ultima_versao = (db.session.query(CardapioSalvo)
                     .filter(CardapioSalvo.plano_id == plano_id)
                     .order_by(desc(CardapioSalvo.versao)).first())
    nova_versao = (ultima_versao.versao + 1) if ultima_versao else 1

    cardapio = CardapioSalvo(
        paciente_id=plano.paciente_id,
        plano_id=plano.id,
        dieta_id=dados.get("dieta_id"),
        nome=f"Cardápio {dieta_nome} — {plano.objetivo}",
        versao=nova_versao,
        dias=dias,
        data_inicio=date.today(),
    )
    db.session.add(cardapio)
    db.session.flush()

    for dia in resultado["cardapio"]:
        dia_num = dia["dia"]
        energia_dia = sum(
            float(prato.get("energia_kcal", 0) or 0)
            for ref in dia["refeicoes"]
            for tipo in ref["tipos"]
            for prato in tipo["pratos"]
        )
        dia_db = CardapioDia(
            cardapio_id=cardapio.id,
            dia_numero=dia_num,
            energia_kcal_total=round(energia_dia, 2),
        )
        db.session.add(dia_db)
        db.session.flush()
        for ref in dia["refeicoes"]:
            for tipo in ref["tipos"]:
                for prato in tipo["pratos"]:
                    db.session.add(CardapioRefeicao(
                        cardapio_dia_id=dia_db.id,
                        tipo_refeicao_id=ref["refeicao_id"],
                        prato_id=prato["id"],
                        porcao_g=prato.get("porcao_g"),
                    ))

    db.session.commit()
    return jsonify({
        "cardapio_id": cardapio.id,
        "versao": cardapio.versao,
        "dieta": dieta_nome,
        "dias": dias,
        "overrides_aplicados": overrides,
        "resultado": resultado,
    }), 201


@plano_bp.route("/api/cardapios/<int:cardapio_id>", methods=["GET"])
def api_obter_cardapio(cardapio_id):
    """Retorna um cardápio salvo com dias e refeições."""
    cardapio = db.session.get(CardapioSalvo, cardapio_id)
    if not cardapio or not paciente_acessivel(cardapio.paciente_id):
        return jsonify({"erro": "Cardápio não encontrado."}), 404
    return jsonify({
        "id": cardapio.id,
        "paciente_id": cardapio.paciente_id,
        "plano_id": cardapio.plano_id,
        "nome": cardapio.nome,
        "versao": cardapio.versao,
        "dias": cardapio.dias,
        "data_inicio": str(cardapio.data_inicio) if cardapio.data_inicio else None,
        "data_fim": str(cardapio.data_fim) if cardapio.data_fim else None,
        "dias_itens": [
            {
                "dia_numero": d.dia_numero,
                "energia_kcal_total": float(d.energia_kcal_total) if d.energia_kcal_total else None,
                "refeicoes": [
                    {
                        "tipo_refeicao_id": r.tipo_refeicao_id,
                        "prato_id": r.prato_id,
                        "porcao_g": float(r.porcao_g) if r.porcao_g else None,
                    }
                    for r in d.refeicoes
                ],
            }
            for d in sorted(cardapio.dias_itens, key=lambda x: x.dia_numero)
        ],
    })


@plano_bp.route("/cardapios/<int:cardapio_id>")
def pagina_cardapio(cardapio_id):
    """
    Página de visualização de um cardápio salvo: dias × refeições × pratos,
    com totais de energia por dia e por refeição.
    """
    cardapio = db.session.get(CardapioSalvo, cardapio_id)
    if not cardapio or not paciente_acessivel(cardapio.paciente_id):
        return "Cardápio não encontrado.", 404

    paciente = db.session.get(Paciente, cardapio.paciente_id)
    plano = db.session.get(PlanoNutricional, cardapio.plano_id) if cardapio.plano_id else None

    # Refeições do cardápio com nome do tipo de refeição
    refeicoes = db.session.execute(text("""
        SELECT cr.cardapio_dia_id, cr.tipo_refeicao_id, tr.nome AS tipo_nome,
               cr.prato_id, p.nome AS prato_nome, cr.porcao_g
        FROM cardapio_refeicoes cr
        JOIN tipos_refeicao tr ON tr.id = cr.tipo_refeicao_id
        JOIN pratos p ON p.id = cr.prato_id
        WHERE cr.cardapio_dia_id IN (
            SELECT id FROM cardapio_dias WHERE cardapio_id = :cid
        )
        ORDER BY cr.cardapio_dia_id, cr.tipo_refeicao_id, cr.id
    """), {"cid": cardapio_id}).mappings().all()

    refeicoes_por_dia: dict[int, list[dict]] = {}
    for r in refeicoes:
        refeicoes_por_dia.setdefault(r["cardapio_dia_id"], []).append(dict(r))

    # Nutrientes por dia — mesma fonte da energia (vw_pratos_nutricional, 1
    # porção padrão por prato), para os totais baterem com o kcal exibido.
    # energia_calculada serve de conferência contra cardapio_dias.energia_kcal_total.
    nutrientes_por_dia = {
        row["cardapio_dia_id"]: row
        for row in db.session.execute(text("""
            SELECT cr.cardapio_dia_id,
                   ROUND(SUM(COALESCE(v.proteina_g, 0)), 1)          AS proteina_g,
                   ROUND(SUM(COALESCE(v.carboidrato_g, 0)), 1)       AS carboidrato_g,
                   ROUND(SUM(COALESCE(v.lipidios_g, 0)), 1)          AS lipidios_g,
                   ROUND(SUM(COALESCE(v.fibra_alimentar_g, 0)), 1)   AS fibra_alimentar_g,
                   ROUND(SUM(COALESCE(v.energia_kcal, 0)), 1)        AS energia_calculada,
                   ROUND(SUM(COALESCE(v.calcio_mg, 0)), 1)           AS calcio_mg,
                   ROUND(SUM(COALESCE(v.ferro_mg, 0)), 1)            AS ferro_mg,
                   ROUND(SUM(COALESCE(v.sodio_mg, 0)), 1)            AS sodio_mg,
                   ROUND(SUM(COALESCE(v.potassio_mg, 0)), 1)         AS potassio_mg,
                   ROUND(SUM(COALESCE(v.fosforo_mg, 0)), 1)          AS fosforo_mg,
                   ROUND(SUM(COALESCE(v.vit_c_mg, 0)), 1)            AS vit_c_mg
            FROM cardapio_refeicoes cr
            LEFT JOIN vw_pratos_nutricional v ON v.prato_id = cr.prato_id
            WHERE cr.cardapio_dia_id IN (
                SELECT id FROM cardapio_dias WHERE cardapio_id = :cid
            )
            GROUP BY cr.cardapio_dia_id
        """), {"cid": cardapio_id}).mappings().all()
    }

    dias_view = []
    for dia in sorted(cardapio.dias_itens, key=lambda x: x.dia_numero):
        refs = refeicoes_por_dia.get(dia.id, [])
        # Agrupa por tipo de refeição preservando a ordem
        grupos: dict[int, dict] = {}
        ordem_tipos: list[int] = []
        for r in refs:
            if r["tipo_refeicao_id"] not in grupos:
                grupos[r["tipo_refeicao_id"]] = {
                    "tipo_nome": r["tipo_nome"],
                    "pratos": [],
                }
                ordem_tipos.append(r["tipo_refeicao_id"])
            grupos[r["tipo_refeicao_id"]]["pratos"].append(r)
        nutri = nutrientes_por_dia.get(dia.id, {})
        dias_view.append({
            "dia_numero": dia.dia_numero,
            "energia_kcal_total": float(dia.energia_kcal_total) if dia.energia_kcal_total else None,
            "macros": {
                "proteina_g": float(nutri.get("proteina_g") or 0),
                "carboidrato_g": float(nutri.get("carboidrato_g") or 0),
                "lipidios_g": float(nutri.get("lipidios_g") or 0),
            },
            "micronutrientes": {
                "fibra_alimentar_g": float(nutri.get("fibra_alimentar_g") or 0),
                "calcio_mg": float(nutri.get("calcio_mg") or 0),
                "ferro_mg": float(nutri.get("ferro_mg") or 0),
                "sodio_mg": float(nutri.get("sodio_mg") or 0),
                "potassio_mg": float(nutri.get("potassio_mg") or 0),
                "fosforo_mg": float(nutri.get("fosforo_mg") or 0),
                "vit_c_mg": float(nutri.get("vit_c_mg") or 0),
            },
            "tipos": [grupos[t] for t in ordem_tipos],
        })

    total_energia = sum(d["energia_kcal_total"] or 0 for d in dias_view)
    media_energia = total_energia / len(dias_view) if dias_view else 0

    total_macros = {
        "proteina_g": round(sum(d["macros"]["proteina_g"] for d in dias_view), 1),
        "carboidrato_g": round(sum(d["macros"]["carboidrato_g"] for d in dias_view), 1),
        "lipidios_g": round(sum(d["macros"]["lipidios_g"] for d in dias_view), 1),
    }
    media_macros = {
        k: round(v / len(dias_view), 1) if dias_view else 0
        for k, v in total_macros.items()
    }

    return render_template(
        "cardapio_detalhe.html",
        cardapio=cardapio,
        paciente=paciente,
        plano=plano,
        dias_view=dias_view,
        total_energia=round(total_energia, 1),
        media_energia=round(media_energia, 1),
        total_macros=total_macros,
        media_macros=media_macros,
    )
