"""Modelos SQLAlchemy da personalização por paciente (delta).

DDL: docs/sql/personalizacao_por_paciente.sql — Bruno executa manualmente.
Doc: docs/personalizacao_por_paciente.md

Estratégia: catálogo global + regras por paciente (preenchimento opcional).
O escopo por dono flui da âncora pacientes.criado_por (authz.paciente_acessivel)
— nenhuma coluna de dono aqui.
"""
import json

from sqlalchemy import CheckConstraint, func

from extensions import db


class RestricaoNutricionalPaciente(db.Model):
    """Faixas nutricionais por paciente (espelho de restricoes_nutricionais_dieta)."""

    __tablename__ = "restricoes_nutricionais_paciente"
    __table_args__ = (
        CheckConstraint("valor_minimo IS NOT NULL OR valor_maximo IS NOT NULL"),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    paciente_id = db.Column(db.Integer,
                            db.ForeignKey("pacientes.id", ondelete="CASCADE"),
                            nullable=False)
    nutriente = db.Column(db.String(50), nullable=False)  # energia_kcal, sodio_mg, potassio_mg...
    valor_minimo = db.Column(db.Numeric(10, 2))
    valor_maximo = db.Column(db.Numeric(10, 2))
    criado_em = db.Column(db.DateTime, server_default=func.now())
    editado_em = db.Column(db.DateTime, server_default=func.now(), onupdate=func.now())
    desativado = db.Column(db.Boolean, default=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "nutriente": self.nutriente,
            "valor_minimo": float(self.valor_minimo) if self.valor_minimo is not None else None,
            "valor_maximo": float(self.valor_maximo) if self.valor_maximo is not None else None,
            "desativado": bool(self.desativado),
        }


class RegraElegibilidadePaciente(db.Model):
    """Elegibilidade por paciente (espelho de regras_elegibilidade_dieta).

    valores_permitidos é armazenado como JSON (mesma convenção da tabela de
    dieta — o motor faz json.loads). O DDL original comentava separador ';';
    a API aceita lista OU string ';' e normaliza para JSON.
    """

    __tablename__ = "regras_elegibilidade_paciente"
    __table_args__ = (
        CheckConstraint("operador IN ('IN','NOT IN')"),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    paciente_id = db.Column(db.Integer,
                            db.ForeignKey("pacientes.id", ondelete="CASCADE"),
                            nullable=False)
    atributo = db.Column(db.String(50), nullable=False)  # consistencia, textura, temperatura_servimento...
    valores_permitidos = db.Column(db.Text, nullable=False)  # JSON array
    operador = db.Column(db.String(20), nullable=False, default="IN")
    criado_em = db.Column(db.DateTime, server_default=func.now())
    editado_em = db.Column(db.DateTime, server_default=func.now(), onupdate=func.now())
    desativado = db.Column(db.Boolean, default=False)

    def _valores_lista(self):
        try:
            v = json.loads(self.valores_permitidos)
            return v if isinstance(v, list) else []
        except (TypeError, ValueError):
            return [x.strip() for x in (self.valores_permitidos or "").split(";") if x.strip()]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "atributo": self.atributo,
            "valores_permitidos": self._valores_lista(),
            "operador": self.operador,
            "desativado": bool(self.desativado),
        }


class RegraVariedadePaciente(db.Model):
    """Variedade/aversão por paciente (espelho de regras_variedade)."""

    __tablename__ = "regras_variedade_paciente"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    paciente_id = db.Column(db.Integer,
                            db.ForeignKey("pacientes.id", ondelete="CASCADE"),
                            nullable=False)
    tipo_prato_id = db.Column(db.Integer,
                              db.ForeignKey("tipos_preparacoes.id", ondelete="CASCADE"),
                              nullable=False)
    dias_minimos_repeticao = db.Column(db.Integer)
    frequencia_maxima_semanal = db.Column(db.Integer)  # 0 = nunca servir (aversão)
    criado_em = db.Column(db.DateTime, server_default=func.now())
    editado_em = db.Column(db.DateTime, server_default=func.now(), onupdate=func.now())
    desativado = db.Column(db.Boolean, default=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tipo_prato_id": self.tipo_prato_id,
            "dias_minimos_repeticao": self.dias_minimos_repeticao,
            "frequencia_maxima_semanal": self.frequencia_maxima_semanal,
            "desativado": bool(self.desativado),
        }


class ExclusaoPaciente(db.Model):
    """Exclusões por paciente: prato OU ingrediente (CHECK garante exatamente um).

    Ingrediente excluído remove todos os pratos que o contêm (prato_composicao).
    """

    __tablename__ = "exclusoes_paciente"
    __table_args__ = (
        CheckConstraint("(prato_id IS NOT NULL) + (ingrediente_id IS NOT NULL) = 1"),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    paciente_id = db.Column(db.Integer,
                            db.ForeignKey("pacientes.id", ondelete="CASCADE"),
                            nullable=False)
    prato_id = db.Column(db.Integer, db.ForeignKey("pratos.id", ondelete="CASCADE"))
    ingrediente_id = db.Column(db.Integer, db.ForeignKey("ingredientes.id", ondelete="CASCADE"))
    motivo = db.Column(db.Text)
    criado_em = db.Column(db.DateTime, server_default=func.now())
    editado_em = db.Column(db.DateTime, server_default=func.now(), onupdate=func.now())
    desativado = db.Column(db.Boolean, default=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "prato_id": self.prato_id,
            "ingrediente_id": self.ingrediente_id,
            "motivo": self.motivo,
            "desativado": bool(self.desativado),
        }
