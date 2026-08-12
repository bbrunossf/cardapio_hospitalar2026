from sqlalchemy import func, text
from extensions import db


class Ingrediente(db.Model):
    __tablename__ = 'ingredientes'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nome = db.Column(db.String(100), nullable=False)
    tipo_alimento = db.Column(db.String(50))
    qtde = db.Column(db.Numeric(3,2))
    unidade_medida = db.Column(db.String(20))
    energia_kcal = db.Column(db.Numeric(8,2))
    carboidrato_g = db.Column(db.Numeric(8,2))
    proteina_g = db.Column(db.Numeric(8,2))
    lipidios_g = db.Column(db.Numeric(8,2))
    fibra_alimentar_g = db.Column(db.Numeric(8,2))
    calcio_mg = db.Column(db.Numeric(8,2))
    ferro_mg = db.Column(db.Numeric(8,2))
    sodio_mg = db.Column(db.Numeric(8,2))
    potassio_mg = db.Column(db.Numeric(8,2))
    fosforo_mg = db.Column(db.Numeric(8,2))
    vit_c_mg = db.Column(db.Numeric(8,2))
    vit_a_mg = db.Column(db.Numeric(8,2))
    gordura_saturada_g = db.Column(db.Numeric(8,2))
    colesterol_mg = db.Column(db.Numeric(8,2))
    custo_por_100g = db.Column(db.Numeric(10,4), default=0.50)
    disponibilidade = db.Column(db.Boolean, default=True)
    observacoes = db.Column(db.Text)
    criado_em = db.Column(db.DateTime, server_default=text('CURRENT_TIMESTAMP'))
    editado_em = db.Column(db.DateTime, server_default=text('CURRENT_TIMESTAMP'))
    fonte = db.Column(db.String(20))
    desativado = db.Column(db.Boolean, default=False)

    def __str__(self):
        return self.nome if self.nome else f"Device {self.id}"




class TipoPrato(db.Model):
    __tablename__ = 'tipos_preparacoes'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nome = db.Column(db.String(50))
    ordem_servico = db.Column(db.Integer)
    criado_em = db.Column(db.DateTime, server_default=text('CURRENT_TIMESTAMP'))
    editado_em = db.Column(db.DateTime, server_default=text('CURRENT_TIMESTAMP'))
    desativado = db.Column(db.Boolean, default=False)

    def __str__(self):
        return self.nome or ''


class Prato(db.Model):
    __tablename__ = 'pratos'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nome = db.Column(db.String(100))
    tipo_prato_id = db.Column(db.Integer, db.ForeignKey('tipos_preparacoes.id', ondelete='CASCADE'), nullable=False)
    cor_predominante = db.Column(db.String(30))
    consistencia = db.Column(db.String(30))
    textura = db.Column(db.String(50))
    temperatura_servimento = db.Column(db.String(30))
    porcao_padrao_g = db.Column(db.Numeric(8,2))
    custo_total = db.Column(db.Numeric(10,4))
    tempo_producao_min = db.Column(db.Integer)
    criado_em = db.Column(db.DateTime, server_default=text('CURRENT_TIMESTAMP'))
    editado_em = db.Column(db.DateTime, server_default=text('CURRENT_TIMESTAMP'))
    desativado = db.Column(db.Boolean, default=False)

    tipo_prato = db.relationship('TipoPrato', backref='pratos')

    def __str__(self):
        return self.nome or ''


class PratoComposicao(db.Model):
    __tablename__ = 'prato_composicao'
    prato_id = db.Column(db.Integer, db.ForeignKey('pratos.id', ondelete='CASCADE'), primary_key=True)
    ingrediente_id = db.Column(db.Integer, db.ForeignKey('ingredientes.id'), primary_key=True)
    quantidade_g = db.Column(db.Numeric(8,2), nullable=False)
    criado_em = db.Column(db.DateTime, server_default=text('CURRENT_TIMESTAMP'))
    editado_em = db.Column(db.DateTime, server_default=text('CURRENT_TIMESTAMP'))
    desativado = db.Column(db.Boolean, default=False)

    prato = db.relationship('Prato', backref='composicoes')
    ingrediente = db.relationship('Ingrediente', backref='composicoes')

    def __str__(self):
        return f"{self.prato} → {self.ingrediente} ({self.quantidade_g}g)"


class PassoPreparo(db.Model):
    """Modo de preparo da preparação — 1 passo por linha, ordenado (ficha técnica)."""
    __tablename__ = 'passos_preparo'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    prato_id = db.Column(db.Integer, db.ForeignKey('pratos.id', ondelete='CASCADE'), nullable=False)
    ordem = db.Column(db.Integer, nullable=False, default=1)
    descricao = db.Column(db.Text, nullable=False)
    criado_em = db.Column(db.DateTime, server_default=text('CURRENT_TIMESTAMP'))
    editado_em = db.Column(db.DateTime, server_default=text('CURRENT_TIMESTAMP'))
    desativado = db.Column(db.Boolean, default=False)

    prato = db.relationship('Prato', backref='passos_preparo')

    def __str__(self):
        return f"Passo {self.ordem}: {self.descricao[:40]}"


class Dieta(db.Model):
    __tablename__ = 'dietas'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nome = db.Column(db.String(50), unique=True, nullable=False)
    descricao = db.Column(db.Text)
    com_sal = db.Column(db.Boolean, default=True)
    criado_em = db.Column(db.DateTime, server_default=text('CURRENT_TIMESTAMP'))
    editado_em = db.Column(db.DateTime, server_default=text('CURRENT_TIMESTAMP'))
    desativado = db.Column(db.Boolean, default=False)

    def __str__(self):
        return self.nome


# ==========================================
# NOVOS MODELOS PARA REGRAS (Épicos 2 e 3)
# ==========================================

class TipoRefeicao(db.Model):
    __tablename__ = 'tipos_refeicao'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nome = db.Column(db.String(50), unique=True, nullable=False)
    horario_padrao = db.Column(db.String(10)) # Ex: '07:00:00'
    descricao = db.Column(db.Text)

    def __str__(self):
        return self.nome

class RegraComposicao(db.Model):
    __tablename__ = 'regras_composicao'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    tipo_refeicao_id = db.Column(db.Integer, db.ForeignKey('tipos_refeicao.id'), nullable=False)
    tipo_prato_id = db.Column(db.Integer, db.ForeignKey('tipos_preparacoes.id'), nullable=False)
    qtd_minima = db.Column(db.Integer, default=0)
    qtd_maxima = db.Column(db.Integer, default=1)
    obrigatorio = db.Column(db.Boolean, default=True)

    tipo_refeicao = db.relationship('TipoRefeicao', backref='regras_composicao')
    tipo_prato = db.relationship('TipoPrato', backref='regras_composicao')

    def __str__(self):
        return f"{self.tipo_refeicao} -> {self.tipo_prato}"

class DietaRefeicao(db.Model):
    __tablename__ = 'dieta_refeicoes'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    dieta_id = db.Column(db.Integer, db.ForeignKey('dietas.id'), nullable=False)
    tipo_refeicao_id = db.Column(db.Integer, db.ForeignKey('tipos_refeicao.id'), nullable=False)

    dieta = db.relationship('Dieta', backref='dieta_refeicoes')
    tipo_refeicao = db.relationship('TipoRefeicao', backref='dieta_refeicoes')

    def __str__(self):
        return f"{self.dieta} - {self.tipo_refeicao}"

class RegraElegibilidadeDieta(db.Model):
    __tablename__ = 'regras_elegibilidade_dieta'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    dieta_id = db.Column(db.Integer, db.ForeignKey('dietas.id'), nullable=False)
    atributo = db.Column(db.String(50), nullable=False) # 'consistencia', 'cor', 'textura'
    valores_permitidos = db.Column(db.Text, nullable=False) # JSON: '["líquido", "pastoso"]'
    operador = db.Column(db.String(20), default='IN') # 'IN', 'NOT IN'

    dieta = db.relationship('Dieta', backref='regras_elegibilidade')

    def __str__(self):
        return f"{self.dieta} - {self.atributo} {self.operador}"

class RestricaoNutricionalDieta(db.Model):
    __tablename__ = 'restricoes_nutricionais_dieta'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    dieta_id = db.Column(db.Integer, db.ForeignKey('dietas.id'), nullable=False)
    nutriente = db.Column(db.String(50), nullable=False) # 'energia', 'lipidios', etc.
    valor_minimo = db.Column(db.Numeric(10,2))
    valor_maximo = db.Column(db.Numeric(10,2))
    periodo = db.Column(db.String(20), default='diario')

    dieta = db.relationship('Dieta', backref='restricoes_nutricionais')

    def __str__(self):
        return f"{self.dieta} - {self.nutriente}"

class RegraSensorialGeral(db.Model):
    __tablename__ = 'regras_sensoriais_gerais'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    tipo_refeicao_id = db.Column(db.Integer, db.ForeignKey('tipos_refeicao.id'), nullable=False)
    regra = db.Column(db.String(50), nullable=False) # 'max_cores_iguais', 'consistencia_unica'
    valor_limite = db.Column(db.Integer, nullable=False)
    grupos_afetados = db.Column(db.Text, nullable=False) # JSON: '["MD", "EN", "SD"]'

    tipo_refeicao = db.relationship('TipoRefeicao', backref='regras_sensoriais')

    def __str__(self):
        return f"{self.tipo_refeicao} - {self.regra}"

class RegraVariedade(db.Model):
    __tablename__ = 'regras_variedade'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    tipo_prato_id = db.Column(db.Integer, db.ForeignKey('tipos_preparacoes.id'), nullable=False)
    dias_minimos_repeticao = db.Column(db.Integer, default=3)
    frequencia_maxima_semanal = db.Column(db.Integer, default=7)

    tipo_prato = db.relationship('TipoPrato', backref='regras_variedade')

    def __str__(self):
        return f"{self.tipo_prato} - Variedade"


class VwPratosNutricional(db.Model):
    """Read-only model mapeando a view vw_pratos_nutricional"""
    __tablename__ = 'vw_pratos_nutricional'
    prato_id = db.Column(db.Integer, primary_key=True)
    prato_nome = db.Column(db.String(100))
    porcao_padrao_g = db.Column(db.Numeric(8,2))
    tipo_prato_id = db.Column(db.Integer)
    tipo_prato = db.Column(db.String(50))
    consistencia = db.Column(db.String(30))
    textura = db.Column(db.String(50))
    temperatura_servimento = db.Column(db.String(30))
    cor_predominante = db.Column(db.String(30))
    tempo_producao_min = db.Column(db.Integer)
    energia_kcal = db.Column(db.Numeric(10,2))
    carboidrato_g = db.Column(db.Numeric(10,2))
    proteina_g = db.Column(db.Numeric(10,2))
    lipidios_g = db.Column(db.Numeric(10,2))
    fibra_alimentar_g = db.Column(db.Numeric(10,2))
    calcio_mg = db.Column(db.Numeric(10,2))
    ferro_mg = db.Column(db.Numeric(10,2))
    sodio_mg = db.Column(db.Numeric(10,2))
    potassio_mg = db.Column(db.Numeric(10,2))
    fosforo_mg = db.Column(db.Numeric(10,2))
    vit_c_mg = db.Column(db.Numeric(10,2))
    vit_a_mg = db.Column(db.Numeric(10,2))
    gordura_saturada_g = db.Column(db.Numeric(10,2))
    colesterol_mg = db.Column(db.Numeric(10,2))
    custo_total = db.Column(db.Numeric(12,4))
    qtd_ingredientes = db.Column(db.Integer)
    massa_total_calculada = db.Column(db.Numeric(10,2))

    def __str__(self):
        return self.prato_nome or ''
