#!/usr/bin/env python3
"""Aplica o escopo por dono (authz) nas rotas de API do novo_cardapio.

Plano: docs/autenticacao.md — cada rota que resolve paciente/plano/cardápio
passa a validar posse (paciente_acessivel / plano_acessivel / query_pacientes);
criar paciente grava criado_por = usuário logado.

Idempotente: se "from authz import" já estiver nos arquivos, não faz nada.

Uso:
    cd /home/plena/novo_cardapio
    ~/.venv/bin/python scripts/aplicar_escopo_auth.py
"""
import py_compile

ARQUIVOS = ["api/plano.py", "api/paciente.py", "api/posso_comer.py"]


def aplicar(arquivo, subs):
    src = open(arquivo, encoding="utf-8").read()
    if "from authz import" in src:
        print(f"já aplicado: {arquivo}")
        return False
    for old, new, count in subs:
        n = src.count(old)
        assert n == count, f"{arquivo}: esperado {count}, achei {n} :: {old[:70]!r}"
        src = src.replace(old, new)
    open(arquivo, "w", encoding="utf-8").write(src)
    py_compile.compile(arquivo, doraise=True)
    print(f"OK: {arquivo}")
    return True


modificou = False

# ── api/plano.py ────────────────────────────────────────────────────────
modificou |= aplicar("api/plano.py", [
    (
        "from api.otimizacao import carregar_dados_otimizacao, criar_modelo_otimizacao, resolver_e_extrair\n"
        "from extensions import db",
        "from api.otimizacao import carregar_dados_otimizacao, criar_modelo_otimizacao, resolver_e_extrair\n"
        "from authz import paciente_acessivel, plano_acessivel, query_pacientes\n"
        "from extensions import db", 1),
    (
        '    paciente_id = request.args.get("paciente_id", type=int)\n'
        '    if paciente_id:\n'
        '        return redirect(url_for("plano.pagina_planos_paciente", paciente_id=paciente_id))\n'
        '    pacientes = db.session.query(Paciente).filter(Paciente.desativado == False).order_by(Paciente.nome).all()',
        '    paciente_id = request.args.get("paciente_id", type=int)\n'
        '    if paciente_id:\n'
        '        if not paciente_acessivel(paciente_id):\n'
        '            return "Paciente não encontrado.", 404\n'
        '        return redirect(url_for("plano.pagina_planos_paciente", paciente_id=paciente_id))\n'
        '    pacientes = query_pacientes().order_by(Paciente.nome).all()', 1),
    (
        '    paciente = db.session.get(Paciente, paciente_id)\n'
        '    if not paciente or paciente.desativado:\n'
        '        return "Paciente não encontrado.", 404',
        '    paciente = paciente_acessivel(paciente_id)\n'
        '    if not paciente:\n'
        '        return "Paciente não encontrado.", 404', 1),
    (
        '    pacientes = db.session.query(Paciente).filter(Paciente.desativado == False).order_by(Paciente.nome).all()\n'
        '    paciente_id = request.args.get("paciente_id", type=int)\n'
        '    return render_template("plano_form.html", pacientes=pacientes, paciente_id=paciente_id)',
        '    pacientes = query_pacientes().order_by(Paciente.nome).all()\n'
        '    paciente_id = request.args.get("paciente_id", type=int)\n'
        '    if paciente_id and not paciente_acessivel(paciente_id):\n'
        '        return "Paciente não encontrado.", 404\n'
        '    return render_template("plano_form.html", pacientes=pacientes, paciente_id=paciente_id)', 1),
    (
        '    paciente = db.session.get(Paciente, paciente_id)\n'
        '    if not paciente or paciente.desativado:\n'
        '        return jsonify({"erro": "Paciente não encontrado."}), 404',
        '    paciente = paciente_acessivel(paciente_id)\n'
        '    if not paciente:\n'
        '        return jsonify({"erro": "Paciente não encontrado."}), 404', 2),
    (
        '    plano = db.session.get(PlanoNutricional, plano_id)\n'
        '    if not plano:\n'
        '        return "Plano não encontrado.", 404',
        '    plano = db.session.get(PlanoNutricional, plano_id)\n'
        '    if not plano or not plano_acessivel(plano):\n'
        '        return "Plano não encontrado.", 404', 2),
    (
        '    plano = db.session.get(PlanoNutricional, plano_id)\n'
        '    if not plano:\n'
        '        return jsonify({"erro": "Plano não encontrado."}), 404',
        '    plano = db.session.get(PlanoNutricional, plano_id)\n'
        '    if not plano or not plano_acessivel(plano):\n'
        '        return jsonify({"erro": "Plano não encontrado."}), 404', 5),
    (
        '    cardapio = db.session.get(CardapioSalvo, cardapio_id)\n'
        '    if not cardapio:\n'
        '        return jsonify({"erro": "Cardápio não encontrado."}), 404',
        '    cardapio = db.session.get(CardapioSalvo, cardapio_id)\n'
        '    if not cardapio or not paciente_acessivel(cardapio.paciente_id):\n'
        '        return jsonify({"erro": "Cardápio não encontrado."}), 404', 1),
    (
        '    cardapio = db.session.get(CardapioSalvo, cardapio_id)\n'
        '    if not cardapio:\n'
        '        return "Cardápio não encontrado.", 404',
        '    cardapio = db.session.get(CardapioSalvo, cardapio_id)\n'
        '    if not cardapio or not paciente_acessivel(cardapio.paciente_id):\n'
        '        return "Cardápio não encontrado.", 404', 1),
])

# ── api/paciente.py ──────────────────────────────────────────────────────
modificou |= aplicar("api/paciente.py", [
    (
        "from extensions import db\nfrom models_paciente import Paciente",
        "from flask_login import current_user\n\n"
        "from authz import paciente_acessivel, query_pacientes\n"
        "from extensions import db\nfrom models_paciente import Paciente", 1),
    (
        "    query = db.session.query(Paciente).filter(Paciente.desativado == False)",
        "    query = query_pacientes()", 1),
    (
        '    paciente = db.session.get(Paciente, paciente_id)\n'
        '    if not paciente or paciente.desativado:\n'
        '        return jsonify({"erro": "Paciente não encontrado."}), 404',
        '    paciente = paciente_acessivel(paciente_id)\n'
        '    if not paciente:\n'
        '        return jsonify({"erro": "Paciente não encontrado."}), 404', 3),
    (
        '    paciente = _preencher_paciente(Paciente(), payload)\n'
        '    db.session.add(paciente)',
        '    paciente = _preencher_paciente(Paciente(), payload)\n'
        '    paciente.criado_por = current_user.id\n'
        '    db.session.add(paciente)', 1),
    (
        '    paciente = db.session.get(Paciente, paciente_id)\n'
        '    if not paciente or paciente.desativado:\n'
        '        return render_template("pacientes.html"), 404',
        '    paciente = paciente_acessivel(paciente_id)\n'
        '    if not paciente:\n'
        '        return render_template("pacientes.html"), 404', 1),
])

# ── api/posso_comer.py ───────────────────────────────────────────────────
modificou |= aplicar("api/posso_comer.py", [
    (
        "from extensions import db",
        "from authz import paciente_acessivel\nfrom extensions import db", 1),
    (
        "@posso_comer_bp.route('/api/posso-comer/contexto/<int:paciente_id>')\n"
        "def api_contexto(paciente_id):\n"
        "    return jsonify(_contexto_publico(paciente_id))",
        "@posso_comer_bp.route('/api/posso-comer/contexto/<int:paciente_id>')\n"
        "def api_contexto(paciente_id):\n"
        "    if not paciente_acessivel(paciente_id):\n"
        "        return jsonify({'erro': 'Paciente não encontrado.'}), 404\n"
        "    return jsonify(_contexto_publico(paciente_id))", 1),
    (
        "    if not paciente_id:\n"
        "        return jsonify({'erro': 'paciente_id obrigatório'}), 400\n"
        "\n"
        "    # --- modo 3",
        "    if not paciente_id:\n"
        "        return jsonify({'erro': 'paciente_id obrigatório'}), 400\n"
        "    if not paciente_acessivel(paciente_id):\n"
        "        return jsonify({'erro': 'Paciente não encontrado.'}), 404\n"
        "\n"
        "    # --- modo 3", 1),
])

print("\nConcluído." if modificou else "\nNada a fazer (já estava aplicado).")
