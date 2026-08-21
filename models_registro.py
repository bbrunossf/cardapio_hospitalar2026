"""Modelos SQLAlchemy do módulo Registro Alimentar 48h (3 tabelas novas).

DDL: docs/sql/registro_alimentar_48h.sql (executado pelo Bruno em 20/08/2026).
O escopo por dono é herdado pela âncora `registros_alimentares.paciente_id`
→ `pacientes.criado_por` (mesmo padrão de planos/cardápios — ver authz.py).
"""
from sqlalchemy import func

from extensions import db


class RegistroAlimentar(db.Model):
    """Cabeçalho de um registro alimentar (um relato de 48h de um paciente)."""

    __tablename__ = "registros_alimentares"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    paciente_id = db.Column(
        db.Integer, db.ForeignKey("pacientes.id", ondelete="CASCADE"), nullable=False
    )
    data_inicio = db.Column(db.Date, nullable=False)   # dia 1 do relato
    data_fim = db.Column(db.Date, nullable=False)      # dia 2 (data_inicio + 1)
    texto_original = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="rascunho")
    criado_por = db.Column(db.Integer, db.ForeignKey("usuarios.id"))
    criado_em = db.Column(db.DateTime, server_default=func.now())
    editado_em = db.Column(db.DateTime, server_default=func.now(), onupdate=func.now())
    desativado = db.Column(db.Boolean, default=False)

    itens = db.relationship(
        "RegistroAlimentarItem",
        backref="registro",
        cascade="all, delete-orphan",
        order_by="RegistroAlimentarItem.ordem",
    )

    def __str__(self) -> str:
        return f"Registro {self.id} (paciente {self.paciente_id}, {self.data_inicio}–{self.data_fim})"


class RegistroAlimentarItem(db.Model):
    """Item estruturado do registro (um alimento/refeição relatado).

    FK exclusiva: exatamente uma de prato_id/industrializado_id/ingrediente_id
    preenchida conforme `origem` (CHECK no DDL); origem='estimado' → nenhuma.
    """

    __tablename__ = "registro_alimentar_itens"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    registro_id = db.Column(
        db.Integer,
        db.ForeignKey("registros_alimentares.id", ondelete="CASCADE"),
        nullable=False,
    )
    dia = db.Column(db.Integer, nullable=False)          # 1 ou 2
    refeicao = db.Column(db.String(20), nullable=False)  # cafe_da_manha|colacao|...
    ordem = db.Column(db.Integer, nullable=False, default=0)
    descricao = db.Column(db.String(255), nullable=False)
    quantidade_texto = db.Column(db.String(100))         # como relatado ("2 fatias")
    quantidade_g = db.Column(db.Numeric(8, 2))           # NULL = revisar
    origem = db.Column(db.String(20), nullable=False, default="estimado")
    prato_id = db.Column(db.Integer, db.ForeignKey("pratos.id"))
    industrializado_id = db.Column(db.Integer, db.ForeignKey("alimentos_industrializados.id"))
    ingrediente_id = db.Column(db.Integer, db.ForeignKey("ingredientes.id"))
    estimado = db.Column(db.Boolean, nullable=False, default=False)
    # Nutrientes calculados na hora do processamento (auditoria)
    energia_kcal = db.Column(db.Numeric(8, 2))
    carboidratos_g = db.Column(db.Numeric(8, 2))
    proteinas_g = db.Column(db.Numeric(8, 2))
    gorduras_totais_g = db.Column(db.Numeric(8, 2))
    fibras_g = db.Column(db.Numeric(8, 2))
    sodio_mg = db.Column(db.Numeric(8, 2))
    calcio_mg = db.Column(db.Numeric(8, 2))
    ferro_mg = db.Column(db.Numeric(8, 2))
    potassio_mg = db.Column(db.Numeric(8, 2))
    fosforo_mg = db.Column(db.Numeric(8, 2))
    vit_c_mg = db.Column(db.Numeric(8, 2))
    observacao = db.Column(db.String(255))               # ex.: "porção assumida: ..."
    criado_em = db.Column(db.DateTime, server_default=func.now())
    editado_em = db.Column(db.DateTime, server_default=func.now(), onupdate=func.now())
    desativado = db.Column(db.Boolean, default=False)


class MedidaCaseira(db.Model):
    """Conversão de medida caseira → gramas (match específico antes do genérico)."""

    __tablename__ = "medidas_caseiras"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    unidade = db.Column(db.String(50), nullable=False)   # fatia, copo, concha...
    alimento_padrao = db.Column(db.String(150))          # NULL = genérico
    gramas = db.Column(db.Numeric(8, 2), nullable=False)
    fonte = db.Column(db.String(20), default="taco")     # taco|rotulagem|estimativa
    criado_em = db.Column(db.DateTime, server_default=func.now())
    editado_em = db.Column(db.DateTime, server_default=func.now(), onupdate=func.now())
    desativado = db.Column(db.Boolean, default=False)

    __table_args__ = (db.UniqueConstraint("unidade", "alimento_padrao"),)

    def __str__(self) -> str:
        alvo = self.alimento_padrao or "(genérico)"
        return f"{self.unidade} de {alvo} = {self.gramas} g ({self.fonte})"
