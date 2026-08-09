"""
Modelos SQLAlchemy — Plano Nutricional por Paciente + Integração WolframAlpha.

Tabelas (DDL aplicado diretamente em cardapio_hospitalar.db):
  planos_nutricionais  — meta + resultado Wolfram (TMB/GET/meta/macros/alertas)
  wolfram_consultas    — auditoria: query + resposta bruta da API
  restricoes_paciente  — alergias/exclusões do paciente (elegibilidade no PuLP)
  cardapios_salvos     — cardápio dimensionado salvo (versionado) por paciente
  cardapio_dias        — dias do cardápio (energia total calculada)
  cardapio_refeicoes   — refeições de cada dia (prato + tipo de refeição)
"""
from sqlalchemy import func
from extensions import db


class PlanoNutricional(db.Model):
    __tablename__ = "planos_nutricionais"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    paciente_id = db.Column(db.Integer, db.ForeignKey("pacientes.id", ondelete="CASCADE"), nullable=False)
    objetivo = db.Column(db.String(20), nullable=False)  # perder | ganhar | manter
    peso_alvo_kg = db.Column(db.Numeric(6, 2))
    prazo_dias = db.Column(db.Integer)
    deficit_diario_kcal = db.Column(db.Numeric(8, 2))  # negativo p/ perda
    nivel_atividade = db.Column(db.String(20))
    perfil_macro = db.Column(db.String(20), default="equilibrado")

    # Resultados (Wolfram ou fallback local)
    tmb_kcal = db.Column(db.Numeric(8, 2))
    get_kcal = db.Column(db.Numeric(8, 2))
    meta_kcal = db.Column(db.Numeric(8, 2))
    proteinas_g = db.Column(db.Numeric(8, 2))
    carboidratos_g = db.Column(db.Numeric(8, 2))
    lipidios_g = db.Column(db.Numeric(8, 2))
    proteinas_pct = db.Column(db.Numeric(5, 2))
    carboidratos_pct = db.Column(db.Numeric(5, 2))
    lipidios_pct = db.Column(db.Numeric(5, 2))

    fonte = db.Column(db.String(10), default="wolfram")  # wolfram | fallback
    alertas = db.Column(db.Text)  # JSON list
    status = db.Column(db.String(20), default="ativo")  # ativo | concluido | cancelado
    criado_em = db.Column(db.DateTime, server_default=func.now())
    editado_em = db.Column(db.DateTime, server_default=func.now(), onupdate=func.now())

    def __str__(self):
        return f"Plano {self.id} — {self.objetivo} (paciente {self.paciente_id})"

    def to_dict(self):
        return {
            "id": self.id,
            "paciente_id": self.paciente_id,
            "objetivo": self.objetivo,
            "peso_alvo_kg": float(self.peso_alvo_kg) if self.peso_alvo_kg is not None else None,
            "prazo_dias": self.prazo_dias,
            "deficit_diario_kcal": float(self.deficit_diario_kcal) if self.deficit_diario_kcal is not None else None,
            "nivel_atividade": self.nivel_atividade,
            "perfil_macro": self.perfil_macro,
            "tmb_kcal": float(self.tmb_kcal) if self.tmb_kcal is not None else None,
            "get_kcal": float(self.get_kcal) if self.get_kcal is not None else None,
            "meta_kcal": float(self.meta_kcal) if self.meta_kcal is not None else None,
            "proteinas_g": float(self.proteinas_g) if self.proteinas_g is not None else None,
            "carboidratos_g": float(self.carboidratos_g) if self.carboidratos_g is not None else None,
            "lipidios_g": float(self.lipidios_g) if self.lipidios_g is not None else None,
            "proteinas_pct": float(self.proteinas_pct) if self.proteinas_pct is not None else None,
            "carboidratos_pct": float(self.carboidratos_pct) if self.carboidratos_pct is not None else None,
            "lipidios_pct": float(self.lipidios_pct) if self.lipidios_pct is not None else None,
            "fonte": self.fonte,
            "alertas": self.alertas,
            "status": self.status,
            "criado_em": str(self.criado_em) if self.criado_em else None,
        }


class WolframConsulta(db.Model):
    __tablename__ = "wolfram_consultas"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    plano_id = db.Column(db.Integer, db.ForeignKey("planos_nutricionais.id", ondelete="SET NULL"))
    query = db.Column(db.String(500), nullable=False)
    api = db.Column(db.String(30), nullable=False)  # short_answers | full_results
    resposta = db.Column(db.Text)
    ok = db.Column(db.Boolean, default=True)
    criado_em = db.Column(db.DateTime, server_default=func.now())

    def __str__(self):
        return f"Consulta {self.id}: {self.query[:50]}"


class RestricaoPaciente(db.Model):
    __tablename__ = "restricoes_paciente"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    paciente_id = db.Column(db.Integer, db.ForeignKey("pacientes.id", ondelete="CASCADE"), nullable=False)
    tipo = db.Column(db.String(20), nullable=False)  # alergia | restricao | preferencia
    atributo = db.Column(db.String(50))  # ex: tipo_prato, cor_predominante, consistencia
    valor = db.Column(db.String(100))
    observacao = db.Column(db.Text)

    def __str__(self):
        return f"{self.tipo}: {self.atributo}={self.valor}"


class CardapioSalvo(db.Model):
    __tablename__ = "cardapios_salvos"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    paciente_id = db.Column(db.Integer, db.ForeignKey("pacientes.id", ondelete="CASCADE"), nullable=False)
    plano_id = db.Column(db.Integer, db.ForeignKey("planos_nutricionais.id", ondelete="SET NULL"))
    dieta_id = db.Column(db.Integer, db.ForeignKey("dietas.id", ondelete="SET NULL"))
    nome = db.Column(db.String(100))
    versao = db.Column(db.Integer, default=1)
    dias = db.Column(db.Integer, default=7)
    data_inicio = db.Column(db.Date)
    data_fim = db.Column(db.Date)
    criado_em = db.Column(db.DateTime, server_default=func.now())

    dias_itens = db.relationship("CardapioDia", backref="cardapio", cascade="all, delete-orphan")

    def __str__(self):
        return self.nome or f"Cardápio {self.id}"


class CardapioDia(db.Model):
    __tablename__ = "cardapio_dias"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    cardapio_id = db.Column(db.Integer, db.ForeignKey("cardapios_salvos.id", ondelete="CASCADE"), nullable=False)
    dia_numero = db.Column(db.Integer, nullable=False)
    energia_kcal_total = db.Column(db.Numeric(8, 2))
    __table_args__ = (db.UniqueConstraint("cardapio_id", "dia_numero"),)

    refeicoes = db.relationship("CardapioRefeicao", backref="dia", cascade="all, delete-orphan")


class CardapioRefeicao(db.Model):
    __tablename__ = "cardapio_refeicoes"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    cardapio_dia_id = db.Column(db.Integer, db.ForeignKey("cardapio_dias.id", ondelete="CASCADE"), nullable=False)
    tipo_refeicao_id = db.Column(db.Integer, db.ForeignKey("tipos_refeicao.id"), nullable=False)
    prato_id = db.Column(db.Integer, db.ForeignKey("pratos.id"), nullable=False)
    porcao_g = db.Column(db.Numeric(8, 2))

    def __str__(self):
        return f"Refeição {self.id} (prato {self.prato_id})"
