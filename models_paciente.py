"""
Modelos SQLAlchemy para o módulo de cadastro de pacientes.

A tabela correspondente deve ser criada manualmente no banco (DDL em
scripts a aplicar/02_criar_tabela_pacientes.sql).
"""
from sqlalchemy import func
from extensions import db


class Paciente(db.Model):
    __tablename__ = "pacientes"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nome = db.Column(db.String(150), nullable=False)
    data_nascimento = db.Column(db.Date, nullable=True)
    sexo = db.Column(db.String(1), nullable=True)  # M | F
    peso_kg = db.Column(db.Numeric(6, 2))
    altura_cm = db.Column(db.Numeric(6, 2))
    cintura_cm = db.Column(db.Numeric(6, 2))
    quadril_cm = db.Column(db.Numeric(6, 2))
    objetivo = db.Column(db.String(20), default="manter")  # ganhar | perder | manter
    nivel_atividade_fisica = db.Column(db.String(20))  # sedentario | leve | moderado | intenso
    observacoes = db.Column(db.Text)
    # Dono (escopo por nutricionista — docs/autenticacao.md). NULL = sem dono
    # (só admin vê até atribuir). FK p/ usuarios(id), DDL em autenticacao.sql.
    criado_por = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=True)
    criado_em = db.Column(db.DateTime, server_default=func.now())
    editado_em = db.Column(db.DateTime, server_default=func.now(), onupdate=func.now())
    desativado = db.Column(db.Boolean, default=False)

    def __str__(self):
        return self.nome or f"Paciente {self.id}"

    @property
    def imc(self) -> float | None:
        """Calcula IMC a partir de peso e altura."""
        if not self.peso_kg or not self.altura_cm:
            return None
        altura_m = float(self.altura_cm) / 100
        if altura_m <= 0:
            return None
        return round(float(self.peso_kg) / (altura_m ** 2), 1)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "nome": self.nome,
            "data_nascimento": str(self.data_nascimento) if self.data_nascimento else None,
            "sexo": self.sexo,
            "peso_kg": float(self.peso_kg) if self.peso_kg is not None else None,
            "altura_cm": float(self.altura_cm) if self.altura_cm is not None else None,
            "cintura_cm": float(self.cintura_cm) if self.cintura_cm is not None else None,
            "quadril_cm": float(self.quadril_cm) if self.quadril_cm is not None else None,
            "objetivo": self.objetivo,
            "nivel_atividade_fisica": self.nivel_atividade_fisica,
            "imc": self.imc,
            "observacoes": self.observacoes,
            "criado_em": str(self.criado_em) if self.criado_em else None,
        }
