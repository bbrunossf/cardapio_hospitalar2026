"""
Modelos SQLAlchemy para o módulo de cadastro de alimentos por rótulo nutricional.

As tabelas correspondentes devem ser criadas manualmente no banco (DDL na
docs/especificacao_modulo_rotulo.md, seção 5.2). Este arquivo contém apenas os
modelos de mapeamento, sem CREATE TABLE/ALTER TABLE.
"""
from sqlalchemy import func
from extensions import db


class AlimentoIndustrializado(db.Model):
    __tablename__ = "alimentos_industrializados"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    codigo_barras = db.Column(db.String(14), unique=True, nullable=True)
    nome = db.Column(db.String(200), nullable=False)
    marca = db.Column(db.String(100))
    fabricante = db.Column(db.String(150))
    peso_liquido = db.Column(db.Numeric(10, 2))
    unidade_peso = db.Column(db.String(10))
    porcao_qtd = db.Column(db.Numeric(8, 2))
    porcao_unidade = db.Column(db.String(20))
    energia_kcal = db.Column(db.Numeric(8, 2))
    carboidratos_g = db.Column(db.Numeric(8, 2))
    acucares_totais_g = db.Column(db.Numeric(8, 2))
    acucares_adicionados_g = db.Column(db.Numeric(8, 2))
    proteinas_g = db.Column(db.Numeric(8, 2))
    gorduras_totais_g = db.Column(db.Numeric(8, 2))
    gorduras_saturadas_g = db.Column(db.Numeric(8, 2))
    gorduras_trans_g = db.Column(db.Numeric(8, 2))
    fibras_g = db.Column(db.Numeric(8, 2))
    sodio_mg = db.Column(db.Numeric(8, 2))
    ingredientes_lista = db.Column(db.Text)
    alergenos = db.Column(db.Text)  # JSON array de strings
    fonte = db.Column(db.String(10), nullable=False, default="manual")
    versao = db.Column(db.Integer, nullable=False, default=1)
    criado_em = db.Column(db.DateTime, server_default=func.now())
    editado_em = db.Column(db.DateTime, server_default=func.now(), onupdate=func.now())
    desativado = db.Column(db.Boolean, default=False)

    versoes = db.relationship(
        "AlimentoVersao",
        backref="alimento",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    def __str__(self):
        return self.nome or f"Alimento {self.id}"


class AlimentoVersao(db.Model):
    __tablename__ = "alimento_versoes"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    alimento_id = db.Column(
        db.Integer,
        db.ForeignKey("alimentos_industrializados.id", ondelete="CASCADE"),
        nullable=False,
    )
    versao = db.Column(db.Integer, nullable=False)
    dados_json = db.Column(db.Text, nullable=False)
    motivo = db.Column(db.String(30))
    criado_em = db.Column(db.DateTime, server_default=func.now())

    def __str__(self):
        return f"Versão {self.versao} de {self.alimento_id}"


class VwAlimentosIndustrializados100g(db.Model):
    """Read-only view de conversão para base 100g (seção 5.3)."""

    __tablename__ = "vw_alimentos_industrializados_100g"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(200))
    marca = db.Column(db.String(100))
    energia_kcal_100g = db.Column(db.Numeric(10, 2))
    carboidratos_g_100g = db.Column(db.Numeric(10, 2))
    acucares_totais_g_100g = db.Column(db.Numeric(10, 2))
    acucares_adicionados_g_100g = db.Column(db.Numeric(10, 2))
    proteinas_g_100g = db.Column(db.Numeric(10, 2))
    gorduras_totais_g_100g = db.Column(db.Numeric(10, 2))
    gorduras_saturadas_g_100g = db.Column(db.Numeric(10, 2))
    gorduras_trans_g_100g = db.Column(db.Numeric(10, 2))
    fibras_g_100g = db.Column(db.Numeric(10, 2))
    sodio_mg_100g = db.Column(db.Numeric(10, 2))

    def __str__(self):
        return self.nome or f"Alimento {self.id}"
