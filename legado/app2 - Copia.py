"""
App Flask + SQLAlchemy + Flask-Admin
Interface administrativa para o banco de Cardápio Hospitalar
"""
from flask import Flask, redirect, url_for, jsonify, request, render_template_string
from flask_sqlalchemy import SQLAlchemy
from flask_admin import Admin, AdminIndexView, expose
from flask_admin.menu import MenuLink
from flask_admin.contrib.sqla import ModelView
from flask_admin.theme import Bootstrap4Theme
from sqlalchemy import func, text
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'cardapio-hospitalar-secret'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(
    os.path.dirname(__file__), 'cardapio_hospitalar.db'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


# ─── MODELOS ──────────────────────────────────────────────────────────────

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


# ─── VIEWS ADMIN ──────────────────────────────────────────────────────────

class BaseModelView(ModelView):
    can_create = True
    can_edit = True
    can_delete = True
    can_export = True
    create_modal = False
    edit_modal = False
    page_size = 40

    column_display_pk = False  # hide PK column by default
    column_hide_backrefs = False


class IngredienteView(BaseModelView):
    column_list = ['nome', 'tipo_alimento', 'qtde', 'unidade_medida', 'energia_kcal', 'carboidrato_g', 'proteina_g', 'lipidios_g', 'fibra_alimentar_g', 'calcio_mg',
    'ferro_mg', 'sodio_mg', 'potassio_mg', 'fosforo_mg', 'vit_c_mg', 'vit_a_mg',
    'gordura_saturada_g', 'colesterol_mg',
    
    
    'custo_por_100g', 'disponibilidade', 'observacoes', 'fonte', 'desativado']
                   
    column_searchable_list = ['nome', 'tipo_alimento']
    column_filters = ['tipo_alimento', 'disponibilidade', 'desativado']
    column_editable_list = ['disponibilidade', 'custo_por_100g']
    form_excluded_columns = ['criado_em', 'editado_em']
    
    column_labels = {
        'nome': 'Nome', 'tipo_alimento': 'Tipo', 'qtde': 'Qtde_medida', 'unidade_medida': 'unidade', 'energia_kcal': 'Kcal', 'carboidrato_g': 'Carboidrato (g)',
        'proteina_g': 'Proteína (g)', 'lipidios_g': 'Lipídios (g)',
         'custo_por_100g': 'Custo R$', 'disponibilidade': 'Disponível'
    }
# class IngredienteView(ModelView):
    # pass

class TipoPratoView(BaseModelView):
    column_list = ['nome', 'ordem_servico']
    column_searchable_list = ['nome']
    form_excluded_columns = ['criado_em', 'editado_em', 'pratos']


class PratoView(BaseModelView):
    column_list = ['nome', 'tipo_prato', 'consistencia', 'temperatura_servimento']
    column_searchable_list = ['nome']
    column_filters = ['tipo_prato', 'consistencia', 'temperatura_servimento']
    form_excluded_columns = ['criado_em', 'editado_em', 'prato_preparacoes']
    column_labels = {
        'tipo_prato': 'Tipo', 'consistencia': 'Consistência',
        'temperatura_servimento': 'Temperatura'
    }


class DietaView(BaseModelView):
    column_list = ['nome', 'com_sal', 'descricao']
    column_searchable_list = ['nome']
    column_filters = ['com_sal']
    form_excluded_columns = ['criado_em', 'editado_em', 'variacoes']
    column_labels = {'com_sal': 'Com sal?', 'descricao': 'Descrição'}
    column_editable_list = ['com_sal']


class PratoComposicaoView(BaseModelView):
    column_list = ['prato', 'ingrediente', 'quantidade_g', 'desativado']
    column_filters = ['desativado']
    column_editable_list = ['quantidade_g', 'desativado']
    form_excluded_columns = ['criado_em', 'editado_em', 'prato', 'ingrediente']
    column_labels = {
        'prato': 'Prato', 'ingrediente': 'Ingrediente',
        'quantidade_g': 'Quantidade (g)', 'desativado': 'Inativo'
    }
    column_sortable_list = ['quantidade_g', 'desativado']


# ==========================================
# NOVAS VIEWS ADMIN PARA REGRAS
# ==========================================

class TipoRefeicaoView(BaseModelView):
    column_list = ['nome', 'horario_padrao', 'descricao']
    column_searchable_list = ['nome']
    form_excluded_columns = ['criado_em', 'editado_em', 'regras_composicao', 'dieta_refeicoes', 'regras_sensoriais']

class RegraComposicaoView(BaseModelView):
    column_list = ['tipo_refeicao', 'tipo_prato', 'qtd_minima', 'qtd_maxima', 'obrigatorio']
    column_filters = ['tipo_refeicao', 'tipo_prato', 'obrigatorio']
    form_excluded_columns = ['id']

class DietaRefeicaoView(BaseModelView):
    column_list = ['dieta', 'tipo_refeicao']
    column_filters = ['dieta', 'tipo_refeicao']
    form_excluded_columns = ['id']

class RegraElegibilidadeDietaView(BaseModelView):
    column_list = ['dieta', 'atributo', 'valores_permitidos', 'operador']
    column_filters = ['dieta', 'atributo', 'operador']
    column_searchable_list = ['valores_permitidos']
    form_excluded_columns = ['id']
    form_widget_args = {
        'valores_permitidos': {'rows': 3} # Campo de texto maior para JSON
    }

class RestricaoNutricionalDietaView(BaseModelView):
    column_list = ['dieta', 'nutriente', 'valor_minimo', 'valor_maximo', 'periodo']
    column_filters = ['dieta', 'nutriente', 'periodo']
    form_excluded_columns = ['id']

class RegraSensorialGeralView(BaseModelView):
    column_list = ['tipo_refeicao', 'regra', 'valor_limite', 'grupos_afetados']
    column_filters = ['tipo_refeicao', 'regra']
    form_excluded_columns = ['id']
    form_widget_args = {
        'grupos_afetados': {'rows': 3}
    }

class RegraVariedadeView(BaseModelView):
    column_list = ['tipo_prato', 'dias_minimos_repeticao', 'frequencia_maxima_semanal']
    column_filters = ['tipo_prato']
    form_excluded_columns = ['id']


class VwPratosNutricionalView(BaseModelView):
    can_create = False
    can_edit = False
    can_delete = False
    column_list = ['prato_nome', 'tipo_prato', 'energia_kcal', 'carboidrato_g',
                   'proteina_g', 'lipidios_g', 'fibra_alimentar_g',
                   'sodio_mg', 'potassio_mg', 'qtd_ingredientes', 'massa_total_calculada']
    column_searchable_list = ['prato_nome', 'tipo_prato']
    column_filters = ['tipo_prato', 'consistencia']
    column_labels = {
        'prato_nome': 'Prato', 'tipo_prato': 'Tipo',
        'energia_kcal': 'Kcal', 'carboidrato_g': 'Carboidrato (g)',
        'proteina_g': 'Proteína (g)', 'lipidios_g': 'Lipídios (g)',
        'fibra_alimentar_g': 'Fibra (g)',
        'sodio_mg': 'Sódio (mg)', 'potassio_mg': 'Potássio (mg)',
        'qtd_ingredientes': 'Ingredientes', 'massa_total_calculada': 'Massa (g)'
    }
    column_default_sort = ('energia_kcal', True)


# ─── DASHBOARD ───────────────────────────────────────────────────────────

class DashboardView(AdminIndexView):

    @expose('/')
    def index(self):
        stats = {
            'ingredientes': Ingrediente.query.filter_by(desativado=False).count(),
            'pratos': Prato.query.filter_by(desativado=False).count(),
            'dietas': Dieta.query.count(),
            'pratos_sem_composicao': db.session.execute(
                text("SELECT COUNT(*) FROM pratos p LEFT JOIN prato_composicao pc ON p.id = pc.prato_id WHERE pc.prato_id IS NULL AND p.desativado = 0")
            ).scalar(),
            'tipos_refeicao': TipoRefeicao.query.count(),
        }

        # Top pratos mais calóricos (via view)
        top_kcal = db.session.execute(
            text("SELECT prato_nome, energia_kcal, proteina_g FROM vw_pratos_nutricional WHERE qtd_ingredientes > 0 ORDER BY energia_kcal DESC LIMIT 5")
        ).mappings().all()

        # Top ingredientes com mais proteína
        top_prot = db.session.execute(
            text("SELECT nome, proteina_g, tipo_alimento FROM ingredientes WHERE desativado = 0 ORDER BY proteina_g DESC LIMIT 5")
        ).mappings().all()

        # Distribuição de consistência
        consistencias = db.session.execute(
            text("SELECT consistencia, COUNT(*) as qtd FROM pratos WHERE desativado = 0 AND consistencia IS NOT NULL AND consistencia != '' GROUP BY consistencia ORDER BY qtd DESC")
        ).mappings().all()

        # Dietas com/sem sal
        dietas_sal = db.session.execute(
            text("SELECT com_sal, COUNT(*) as qtd FROM dietas GROUP BY com_sal")
        ).mappings().all()

        # Pratos por tipo (via view)
        pratos_por_tipo = db.session.execute(
            text("SELECT tipo_prato, COUNT(*) as qtd FROM vw_pratos_nutricional WHERE qtd_ingredientes > 0 GROUP BY tipo_prato ORDER BY qtd DESC")
        ).mappings().all()

        # Pratos com maiores porções
        top_porcoes = db.session.execute(
            text("SELECT id, nome, porcao_padrao_g FROM pratos WHERE desativado = 0 AND porcao_padrao_g IS NOT NULL ORDER BY CAST(porcao_padrao_g AS REAL) DESC LIMIT 5")
        ).mappings().all()

        return self.render('admin/dashboard.html',
                           stats=stats,
                           top_kcal=top_kcal,
                           top_prot=top_prot,
                           consistencias=consistencias,
                           consistencias_total=sum(c.qtd for c in consistencias),
                           dietas_sal=dietas_sal,
                           pratos_por_tipo=pratos_por_tipo,
                           top_porcoes=top_porcoes,
                           )


# ─── TEMPLATE DASHBOARD ──────────────────────────────────────────────────

DASHBOARD_TEMPLATE = '''
{% extends 'admin/master.html' %}
{% block body %}
<style>
  .container, .container-fluid { max-width: 100% !important; padding-left: 24px; padding-right: 24px; }
</style>
<div style="padding: 20px; width: 100%">
  <h1>📊 Cardápio Hospitalar — Dashboard</h1>
  <p style="color: #666;">Épico 1: Gestão de Dados Mestres</p>

  <div style="display: flex; gap: 15px; flex-wrap: wrap; margin: 25px 0;">
    {% for label, count in [('🥩 Ingredientes', stats.ingredientes), ('🍽️ Pratos', stats.pratos), ('🥗 Dietas', stats.dietas), ('⏰ Refeições', stats.tipos_refeicao)] %}
    <div style="flex: 1; min-width: 150px; background: #f8f9fa; border-radius: 10px; padding: 20px; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
      <div style="font-size: 2.5em; font-weight: bold; color: #2c3e50;">{{ count }}</div>
      <div style="color: #7f8c8d; margin-top: 5px;">{{ label }}</div>
    </div>
    {% endfor %}
  </div>

  {% if stats.pratos_sem_composicao %}
  <div style="margin-bottom: 20px; padding: 12px 20px; background: #fff3cd; border-radius: 8px; font-size: 0.9em;">
    ⚠️ <strong>{{ stats.pratos_sem_composicao }} pratos</strong> ainda sem composição de ingredientes.
  </div>
  {% endif %}

  <div style="display: flex; gap: 20px; flex-wrap: wrap;">
    <div style="flex: 1; min-width: 300px; background: white; border-radius: 10px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
      <h3>🔥 Pratos mais calóricos</h3>
      <table style="width: 100%; border-collapse: collapse;">
        <tr style="border-bottom: 2px solid #eee;">
          <th style="text-align: left; padding: 8px;">Prato</th>
          <th style="text-align: right; padding: 8px;">Kcal</th>
          <th style="text-align: right; padding: 8px;">Prot</th>
        </tr>
        {% for p in top_kcal %}
        <tr style="border-bottom: 1px solid #f0f0f0;">
          <td style="padding: 6px;">{{ p.prato_nome }}</td>
          <td style="text-align: right; padding: 6px; font-weight: bold;">{{ "%.0f"|format(p.energia_kcal|float) }}</td>
          <td style="text-align: right; padding: 6px;">{{ "%.1f"|format(p.proteina_g|float) }}g</td>
        </tr>
        {% endfor %}
      </table>
    </div>

    <div style="flex: 1; min-width: 300px; background: white; border-radius: 10px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
      <h3>💪 Ingredientes + Proteicos</h3>
      <table style="width: 100%; border-collapse: collapse;">
        <tr style="border-bottom: 2px solid #eee;">
          <th style="text-align: left; padding: 8px;">Ingrediente</th>
          <th style="text-align: right; padding: 8px;">Proteína</th>
          <th style="text-align: left; padding: 8px;">Tipo</th>
        </tr>
        {% for p in top_prot %}
        <tr style="border-bottom: 1px solid #f0f0f0;">
          <td style="padding: 6px;">{{ p.nome }}</td>
          <td style="text-align: right; padding: 6px; font-weight: bold;">{{ "%.1f"|format(p.proteina_g|float) }}g</td>
          <td style="padding: 6px; font-size: 0.85em; color: #666;">{{ p.tipo_alimento }}</td>
        </tr>
        {% endfor %}
      </table>
    </div>

    <div style="flex: 1; min-width: 300px; background: white; border-radius: 10px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
      <h3>🥧 Pratos por Tipo</h3>
      {% for t in pratos_por_tipo %}
      <div style="margin: 8px 0; display: flex; align-items: center;">
        <span style="width: 150px;">{{ t.tipo_prato }}</span>
        <div style="width: 100%; height: 20px; background: #ecf0f1; border-radius: 10px; margin: 0 10px;">
          <div style="height: 100%; width: {{ (t.qtd / pratos_por_tipo|map(attribute='qtd')|sum * 100)|round }}%; background: #3498db; border-radius: 10px;"></div>
        </div>
        <span style="font-weight: bold;">{{ t.qtd }}</span>
      </div>
      {% endfor %}
    </div>

    <div style="flex: 1; min-width: 300px; background: white; border-radius: 10px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
      <h3>📏 Maiores Porções</h3>
      <table style="width: 100%; border-collapse: collapse;">
        <tr style="border-bottom: 2px solid #eee;">
          <th style="text-align: left; padding: 8px;">Prato</th>
          <th style="text-align: right; padding: 8px;">Porção (g)</th>
        </tr>
        {% for p in top_porcoes %}
        <tr style="border-bottom: 1px solid #f0f0f0;">
          <td style="padding: 6px;">{{ p.nome }}</td>
          <td style="text-align: right; padding: 6px; font-weight: bold;">{{ "%.0f"|format(p.porcao_padrao_g|float) }}g</td>
        </tr>
        {% endfor %}
      </table>
    </div>
  </div>

  <div style="display: flex; gap: 20px; flex-wrap: wrap; margin-top: 20px;">
    <div style="flex: 1; min-width: 250px; background: white; border-radius: 10px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
      <h3>📦 Consistência dos Pratos</h3>
      {% for c in consistencias %}
      <div style="margin: 8px 0; display: flex; align-items: center;">
        <span style="width: 100px;">{{ c.consistencia }}</span>
        <div style="width: 100%; height: 20px; background: #ecf0f1; border-radius: 10px; margin: 0 10px;">
          <div style="height: 100%; width: {{ (c.qtd / consistencias_total * 100)|round }}%; background: #3498db; border-radius: 10px;"></div>
        </div>
        <span style="font-weight: bold;">{{ c.qtd }}</span>
      </div>
      {% endfor %}
    </div>

    <div style="flex: 1; min-width: 250px; background: white; border-radius: 10px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
      <h3>🥗 Dietas</h3>
      <div style="display: flex; gap: 20px; justify-content: center; margin: 20px 0;">
        {% for d in dietas_sal %}
        <div style="text-align: center;">
          <div style="font-size: 2em;">{{ '🧂' if d.com_sal else '🚫' }}</div>
          <div style="font-size: 1.5em; font-weight: bold;">{{ d.qtd }}</div>
          <div style="color: #666;">{{ 'Com sal' if d.com_sal else 'Sem sal' }}</div>
        </div>
        {% endfor %}
      </div>
      <div style="font-size: 0.85em; color: #7f8c8d; text-align: center;">
        {{ dietas_sal|map(attribute='qtd')|sum }} dietas no total
      </div>
    </div>
  </div>

  <div style="margin-top: 30px; text-align: center; color: #95a5a6; font-size: 0.85em;">
    <p>Use o menu acima para navegar entre as tabelas e gerenciar os dados.</p>
  </div>
</div>
{% endblock %}
'''


# ─── SETUP ────────────────────────────────────────────────────────────────

admin = Admin(app, name='Cardápio Hospitalar', theme=Bootstrap4Theme(),
              index_view=DashboardView())

admin.add_view(IngredienteView(Ingrediente, db, name='Ingredientes'))
#admin.add_view(IngredienteView(Ingrediente, db.session))
admin.add_view(TipoPratoView(TipoPrato, db, name='Tipos Prato'))
admin.add_view(PratoView(Prato, db, name='Pratos'))
admin.add_view(DietaView(Dieta, db, name='Dietas'))

# Adicione estas linhas após as views existentes
admin.add_view(TipoRefeicaoView(TipoRefeicao, db, name='Tipos Refeição', category='Regras'))
admin.add_view(RegraComposicaoView(RegraComposicao, db, name='Composição Refeições', category='Regras'))
admin.add_view(DietaRefeicaoView(DietaRefeicao, db, name='Dietas x Refeições', category='Regras'))
admin.add_view(RegraElegibilidadeDietaView(RegraElegibilidadeDieta, db, name='Elegibilidade Dietas', category='Regras'))
admin.add_view(RestricaoNutricionalDietaView(RestricaoNutricionalDieta, db, name='Restrições Nutricionais', category='Regras'))
admin.add_view(RegraSensorialGeralView(RegraSensorialGeral, db, name='Regras Sensoriais', category='Regras'))
admin.add_view(RegraVariedadeView(RegraVariedade, db, name='Regras Variedade', category='Regras'))
admin.add_view(PratoComposicaoView(PratoComposicao, db, name='Composição de Pratos'))
admin.add_view(VwPratosNutricionalView(VwPratosNutricional, db, name='📊 Nutrientes (view)', category='Consultas'))
admin.add_link(MenuLink(name='🍽️ Ajustar Composição', url='/composicao-view', category='Consultas'))


@app.route('/')
def root():
    return redirect(url_for('admin.index'))


# ══════════════════════════════════════════════════════════════════
# API REST — Composição de Pratos (interface customizada)
# ══════════════════════════════════════════════════════════════════

@app.route('/api/pratos')
def api_pratos():
    """Lista todos os pratos ativos com tipo"""
    pratos = db.session.execute(
        text("""
            SELECT p.id, p.nome, p.porcao_padrao_g, tp.nome AS tipo,
                   COUNT(pc.ingrediente_id) AS qtd_ingredientes,
                   ROUND(SUM(pc.quantidade_g), 2) AS massa_total
            FROM pratos p
            LEFT JOIN tipos_preparacoes tp ON p.tipo_prato_id = tp.id
            LEFT JOIN prato_composicao pc ON p.id = pc.prato_id AND pc.desativado = 0
            WHERE p.desativado = 0
            GROUP BY p.id
            ORDER BY p.nome
        """)
    ).mappings().all()

    return jsonify([dict(r) for r in pratos])


@app.route('/api/pratos/<int:prato_id>/composicao')
def api_prato_composicao(prato_id):
    """Detalhes do prato + ingredientes"""
    prato = db.session.execute(
        text("""
            SELECT p.id, p.nome, p.porcao_padrao_g, tp.nome AS tipo,
                   p.consistencia, p.textura, p.temperatura_servimento
            FROM pratos p
            LEFT JOIN tipos_preparacoes tp ON p.tipo_prato_id = tp.id
            WHERE p.id = :pid AND p.desativado = 0
        """), {'pid': prato_id}
    ).mappings().first()

    if not prato:
        return jsonify({'error': 'Prato não encontrado'}), 404

    ingredientes = db.session.execute(
        text("""
            SELECT pc.ingrediente_id, i.nome AS ingrediente, pc.quantidade_g
            FROM prato_composicao pc
            JOIN ingredientes i ON i.id = pc.ingrediente_id
            WHERE pc.prato_id = :pid AND pc.desativado = 0
            ORDER BY i.nome
        """), {'pid': prato_id}
    ).mappings().all()

    massa_calculada = sum(float(r['quantidade_g'] or 0) for r in ingredientes)
    porcao = float(prato['porcao_padrao_g'] or 0)
    diferenca = round(massa_calculada - porcao, 2)
    ok = abs(diferenca) < 0.01

    return jsonify({
        'prato': dict(prato),
        'ingredientes': [dict(r) for r in ingredientes],
        'massa_calculada': massa_calculada,
        'diferenca': diferenca,
        'ok': ok
    })


@app.route('/api/pratos/<int:prato_id>/porcao', methods=['POST'])
def api_update_porcao(prato_id):
    """Atualiza porcao_padrao_g do prato"""
    data = request.get_json()
    novo_valor = data.get('porcao_padrao_g')
    if novo_valor is None or float(novo_valor) <= 0:
        return jsonify({'error': 'Valor inválido'}), 400

    db.session.execute(
        text("UPDATE pratos SET porcao_padrao_g = :val, editado_em = CURRENT_TIMESTAMP WHERE id = :pid"),
        {'val': float(novo_valor), 'pid': prato_id}
    )
    db.session.commit()
    return jsonify({'success': True, 'porcao_padrao_g': float(novo_valor)})


@app.route('/api/composicao/<int:prato_id>/<int:ingrediente_id>', methods=['POST'])
def api_update_composicao(prato_id, ingrediente_id):
    """Atualiza quantidade_g de um ingrediente na composição"""
    data = request.get_json()
    nova_qtd = data.get('quantidade_g')
    if nova_qtd is None or float(nova_qtd) <= 0:
        return jsonify({'error': 'Quantidade inválida'}), 400

    db.session.execute(
        text("""
            UPDATE prato_composicao
            SET quantidade_g = :qtd, editado_em = CURRENT_TIMESTAMP
            WHERE prato_id = :pid AND ingrediente_id = :iid AND desativado = 0
        """),
        {'qtd': float(nova_qtd), 'pid': prato_id, 'iid': ingrediente_id}
    )
    db.session.commit()
    return jsonify({'success': True, 'quantidade_g': float(nova_qtd)})


@app.route('/api/ingredientes')
def api_ingredientes():
    """Lista todos os ingredientes ativos"""
    ingredientes = db.session.execute(
        text("SELECT id, nome, tipo_alimento FROM ingredientes WHERE desativado = 0 ORDER BY nome")
    ).mappings().all()
    return jsonify([dict(r) for r in ingredientes])


@app.route('/api/composicao/<int:prato_id>/add/<int:ingrediente_id>', methods=['POST'])
def api_add_composicao(prato_id, ingrediente_id):
    """Adiciona um ingrediente ao prato"""
    data = request.get_json() or {}
    qtd = float(data.get('quantidade_g', 10))

    if qtd <= 0:
        return jsonify({'error': 'Quantidade deve ser positiva'}), 400

    # Verifica se já existe
    existente = db.session.execute(
        text("SELECT 1 FROM prato_composicao WHERE prato_id = :pid AND ingrediente_id = :iid"),
        {'pid': prato_id, 'iid': ingrediente_id}
    ).scalar()

    if existente:
        return jsonify({'error': 'Ingrediente já pertence ao prato'}), 409

    db.session.execute(
        text("""
            INSERT INTO prato_composicao (prato_id, ingrediente_id, quantidade_g)
            VALUES (:pid, :iid, :qtd)
        """),
        {'pid': prato_id, 'iid': ingrediente_id, 'qtd': qtd}
    )
    db.session.commit()
    return jsonify({'success': True, 'quantidade_g': qtd}), 201


@app.route('/api/composicao/<int:prato_id>/<int:ingrediente_id>', methods=['DELETE'])
def api_remove_composicao(prato_id, ingrediente_id):
    """Remove um ingrediente do prato (soft delete)"""
    db.session.execute(
        text("""
            UPDATE prato_composicao
            SET desativado = 1, editado_em = CURRENT_TIMESTAMP
            WHERE prato_id = :pid AND ingrediente_id = :iid
        """),
        {'pid': prato_id, 'iid': ingrediente_id}
    )
    db.session.commit()
    return jsonify({'success': True})


@app.route('/composicao-view')
def composicao_view():
    """Interface customizada de composição de pratos"""
    return render_template_string(COMPOSICAO_TEMPLATE)


# ══════════════════════════════════════════════════════════════════
# TEMPLATE HTML — Composição de Pratos
# ══════════════════════════════════════════════════════════════════

COMPOSICAO_TEMPLATE = '''
<!DOCTYPE html>
<html lang="pt-br" data-theme="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Composição de Pratos</title>
<style>
  :root {
    --bg: #1a1a2e;
    --surface: #16213e;
    --surface2: #0f3460;
    --text: #e0e0e0;
    --text2: #a0a0a0;
    --primary: #4fc3f7;
    --success: #66bb6a;
    --danger: #ef5350;
    --warning: #ffa726;
    --border: #2a2a4a;
    --radius: 8px;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: var(--bg); color: var(--text); height: 100vh;
    display: flex; flex-direction: column;
  }
  header {
    background: var(--surface); padding: 16px 24px;
    border-bottom: 1px solid var(--border);
    display: flex; align-items: center; justify-content: space-between;
  }
  header h1 { font-size: 1.3rem; font-weight: 600; }
  header a { color: var(--primary); text-decoration: none; font-size: 0.9rem; }
  .container { display: flex; flex: 1; overflow: hidden; }
  .panel-left {
    width: 380px; min-width: 280px;
    background: var(--surface); border-right: 1px solid var(--border);
    display: flex; flex-direction: column;
  }
  .panel-right { flex: 1; padding: 24px; overflow-y: auto; }
  .search-box {
    padding: 12px; border-bottom: 1px solid var(--border);
  }
  .search-box input {
    width: 100%; padding: 10px 14px; border-radius: var(--radius);
    border: 1px solid var(--border); background: var(--bg);
    color: var(--text); font-size: 0.9rem; outline: none;
  }
  .search-box input:focus { border-color: var(--primary); }
  .prato-list { flex: 1; overflow-y: auto; }
  .prato-item {
    padding: 12px 16px; cursor: pointer; border-bottom: 1px solid var(--border);
    display: flex; justify-content: space-between; align-items: center;
    transition: background 0.15s;
  }
  .prato-item:hover { background: var(--surface2); }
  .prato-item.active { background: var(--surface2); border-left: 3px solid var(--primary); }
  .prato-item .nome { font-size: 0.9rem; }
  .prato-item .tipo { font-size: 0.75rem; color: var(--text2); }
  .prato-item .badge {
    font-size: 0.7rem; padding: 2px 8px; border-radius: 12px;
    background: var(--surface2); color: var(--text2);
  }
  .prato-item .badge.ok { background: #1b5e20; color: var(--success); }
  .prato-item .badge.warn { background: #e65100; color: var(--warning); }
  .prato-item .badge.empty { background: #4a148c; color: #ce93d8; }

  .prato-detail h2 {
    font-size: 1.4rem; margin-bottom: 4px;
  }
  .prato-detail .subtitulo {
    font-size: 0.85rem; color: var(--text2); margin-bottom: 20px;
  }
  .porcao-row {
    display: flex; align-items: center; gap: 12px; margin-bottom: 24px;
    padding: 16px; background: var(--surface); border-radius: var(--radius);
  }
  .porcao-row label { font-size: 0.85rem; color: var(--text2); }
  .porcao-row input[type="number"] {
    width: 100px; padding: 8px 12px; border-radius: var(--radius);
    border: 1px solid var(--border); background: var(--bg);
    color: var(--text); font-size: 1rem; text-align: center;
  }
  .porcao-row .status { display: flex; align-items: center; gap: 8px; font-size: 0.9rem; }
  .porcao-row .status.ok { color: var(--success); }
  .porcao-row .status.warn { color: var(--warning); }
  .porcao-row .diferenca { font-weight: 600; }
  .btn {
    padding: 8px 16px; border-radius: var(--radius); border: none;
    cursor: pointer; font-size: 0.85rem; font-weight: 500;
    transition: opacity 0.15s;
  }
  .btn:hover { opacity: 0.85; }
  .btn-primary { background: var(--primary); color: #000; }
  .btn-sm { padding: 4px 10px; font-size: 0.75rem; }

  table { width: 100%; border-collapse: collapse; }
  th { text-align: left; padding: 10px 12px; font-size: 0.8rem; color: var(--text2); border-bottom: 2px solid var(--border); }
  td { padding: 10px 12px; border-bottom: 1px solid var(--border); font-size: 0.9rem; }
  td input[type="number"] {
    width: 80px; padding: 6px 8px; border-radius: var(--radius);
    border: 1px solid var(--border); background: var(--bg);
    color: var(--text); text-align: center;
  }
  .ingrediente-nome { font-weight: 500; }
  .saved-msg { color: var(--success); font-size: 0.75rem; margin-left: 8px; opacity: 0; transition: opacity 0.3s; }
  .saved-msg.show { opacity: 1; }
  .total-row td { border-top: 2px solid var(--border); font-weight: 600; }
  .empty-state {
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    height: 100%; color: var(--text2); text-align: center; gap: 12px;
  }
  .empty-state .icon { font-size: 3rem; }
  .loading { text-align: center; padding: 40px; color: var(--text2); }
  .loading::after { content: "..."; animation: dots 1.5s infinite; }
  @keyframes dots { 0%,20% { content: "."; } 40% { content: ".."; } 60%,100% { content: "..."; } }
  .stats-bar {
    padding: 8px 16px; font-size: 0.75rem; color: var(--text2);
    border-top: 1px solid var(--border); background: var(--surface);
  }
</style>
</head>
<body>
<header>
  <h1>🍽️ Composição de Pratos</h1>
  <a href="/admin/">&larr; Voltar ao Admin</a>
</header>
<div class="container">
  <div class="panel-left">
    <div class="search-box">
      <input type="text" id="searchInput" placeholder="Buscar prato..." oninput="filtrarPratos()">
    </div>
    <div class="prato-list" id="pratoList">
      <div class="loading">Carregando pratos</div>
    </div>
    <div class="stats-bar" id="statsBar"></div>
  </div>
  <div class="panel-right" id="panelRight">
    <div class="empty-state">
      <div class="icon">👈</div>
      <p>Selecione um prato na lista ao lado<br>para ver sua composição</p>
    </div>
  </div>
</div>
<script>
let pratos = [];
let pratoAtivo = null;
let ingredientesCache = {};

async function carregarPratos() {
  const r = await fetch('/api/pratos');
  pratos = await r.json();
  document.getElementById('statsBar').textContent = `${pratos.length} pratos cadastrados`;
  renderPratos(pratos);
}

function renderPratos(lista) {
  const el = document.getElementById('pratoList');
  if (lista.length === 0) {
    el.innerHTML = '<div style="padding: 24px; text-align: center; color: var(--text2);">Nenhum prato encontrado</div>';
    return;
  }
  el.innerHTML = lista.map(p => {
    let badge = '<span class="badge empty">sem composição</span>';
    if (p.qtd_ingredientes > 0) {
      const diff = Math.abs(parseFloat(p.massa_total || 0) - parseFloat(p.porcao_padrao_g || 0));
      badge = diff < 0.01
        ? '<span class="badge ok">✓ ok</span>'
        : `<span class="badge warn">⚠ ${diff.toFixed(1)}g</span>`;
    }
    return `<div class="prato-item${pratoAtivo === p.id ? ' active' : ''}" onclick="selecionarPrato(${p.id})" data-nome="${p.nome.toLowerCase()}">
      <div><div class="nome">${p.nome}</div><div class="tipo">${p.tipo || ''}</div></div>
      ${badge}
    </div>`;
  }).join('');
}

function filtrarPratos() {
  const q = document.getElementById('searchInput').value.toLowerCase();
  const filtrados = pratos.filter(p => p.nome.toLowerCase().includes(q));
  renderPratos(filtrados);
}

async function selecionarPrato(id) {
  pratoAtivo = id;
  renderPratos(pratos);

  const panel = document.getElementById('panelRight');
  panel.innerHTML = '<div class="loading">Carregando composição</div>';

  const r = await fetch(`/api/pratos/${id}/composicao`);
  const data = await r.json();

  if (data.error) {
    panel.innerHTML = `<div class="empty-state"><p>${data.error}</p></div>`;
    return;
  }

  renderComposicao(data);
}

function renderComposicao(data) {
  const { prato, ingredientes, massa_calculada, diferenca, ok } = data;
  const porcao = parseFloat(prato.porcao_padrao_g || 0);

  const statusClass = ok ? 'ok' : 'warn';
  const statusIcon = ok ? '✅' : '⚠️';
  const statusText = ok ? 'Massas coincidem' : `Diferença de ${Math.abs(diferenca).toFixed(1)}g`;

  const panel = document.getElementById('panelRight');
  panel.innerHTML = `
    <div class="prato-detail">
      <h2>${prato.nome}</h2>
      <div class="subtitulo">${prato.tipo || ''} &middot; ${prato.consistencia || '—'} &middot; ${prato.temperatura_servimento || '—'}</div>

      <div class="porcao-row">
        <label>Porção padrão (g)</label>
        <input type="number" step="0.5" id="porcaoInput" value="${porcao}" onchange="salvarPorcao(${prato.id})">
        <div class="status ${statusClass}">
          <span>${statusIcon}</span>
          <span class="diferenca">${massa_calculada.toFixed(1)}g calculados</span>
          <span>— ${statusText}</span>
        </div>
        <button class="btn btn-primary btn-sm" onclick="salvarPorcao(${prato.id})">Salvar</button>
        <span class="saved-msg" id="porcaoSaved">✓ salvo</span>
      </div>

      <table>
        <thead>
          <tr><th>Ingrediente</th><th style="width:120px;text-align:center;">Quantidade (g)</th><th style="width:120px;"></th></tr>
        </thead>
        <tbody>
          ${ingredientes.map(ing => `
            <tr>
              <td class="ingrediente-nome">${ing.ingrediente}</td>
              <td style="text-align:center;">
                <input type="number" step="0.5" id="qtd_${ing.ingrediente_id}" value="${parseFloat(ing.quantidade_g).toFixed(1)}"
                       onchange="salvarComposicao(${prato.id}, ${ing.ingrediente_id})">
              </td>
              <td>
                <button class="btn btn-primary btn-sm" onclick="salvarComposicao(${prato.id}, ${ing.ingrediente_id})">Salvar</button>
                <span class="saved-msg" id="saved_${ing.ingrediente_id}">✓</span>
                <button class="btn btn-sm" style="background:var(--danger);color:#fff;margin-left:4px;" onclick="removerIngrediente(${prato.id}, ${ing.ingrediente_id}, '${ing.ingrediente}')">✕</button>
              </td>
            </tr>
          `).join('')}
        </tbody>
        <tfoot>
          <tr class="total-row">
            <td><strong>Total</strong></td>
            <td style="text-align:center;"><strong>${massa_calculada.toFixed(1)}g</strong></td>
            <td></td>
          </tr>
        </tfoot>
      </table>

      <div style="margin-top: 24px; padding: 16px; background: var(--surface); border-radius: var(--radius);">
        <h4 style="margin-bottom: 12px; font-size: 0.95rem;">➕ Adicionar Ingrediente</h4>
        <div style="display: flex; gap: 8px; margin-bottom: 12px;">
          <input type="text" id="addIngSearch" placeholder="Buscar ingrediente..." oninput="filtrarIngredientesDisponiveis()"
                 style="flex:1; padding: 10px 14px; border-radius: var(--radius); border: 1px solid var(--border); background: var(--bg); color: var(--text); font-size: 0.9rem; outline: none;">
          <input type="number" id="addIngQtd" value="10" step="0.5" min="0.5"
                 style="width: 80px; padding: 10px; border-radius: var(--radius); border: 1px solid var(--border); background: var(--bg); color: var(--text); text-align: center; font-size: 0.9rem; outline: none;">
          <span style="color:var(--text2); display:flex; align-items:center; font-size:0.85rem;">g</span>
        </div>
        <div id="ingredientesDisponiveis" style="max-height: 200px; overflow-y: auto; display: flex; flex-wrap: wrap; gap: 4px;">
          <div style="color: var(--text2); font-size: 0.85rem; padding: 8px;">Carregando...</div>
        </div>
      </div>
    </div>
  `;
  filtrarIngredientesDisponiveis();
}

async function salvarPorcao(pratoId) {
  const input = document.getElementById('porcaoInput');
  const val = input.value;
  const r = await fetch(`/api/pratos/${pratoId}/porcao`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ porcao_padrao_g: val })
  });
  const data = await r.json();
  if (data.success) {
    const msg = document.getElementById('porcaoSaved');
    msg.classList.add('show');
    setTimeout(() => msg.classList.remove('show'), 2000);
    // Recarrega para mostrar status atualizado
    selecionarPrato(pratoId);
    carregarPratos(); // atualiza lista
  }
}

async function salvarComposicao(pratoId, ingredienteId) {
  const input = document.getElementById(`qtd_${ingredienteId}`);
  const val = input.value;
  const r = await fetch(`/api/composicao/${pratoId}/${ingredienteId}`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ quantidade_g: val })
  });
  const data = await r.json();
  if (data.success) {
    const msg = document.getElementById(`saved_${ingredienteId}`);
    msg.classList.add('show');
    setTimeout(() => msg.classList.remove('show'), 2000);
    // Recarrega para recalcular massas
    selecionarPrato(pratoId);
    carregarPratos(); // atualiza lista
  }
}

let todosIngredientes = [];

async function carregarIngredientes() {
  const r = await fetch('/api/ingredientes');
  todosIngredientes = await r.json();
}

function filtrarIngredientesDisponiveis() {
  if (!pratoAtivo || !todosIngredientes.length) return;
  const q = document.getElementById('addIngSearch').value.toLowerCase();
  const idsNoPrato = new Set(
    Array.from(document.querySelectorAll('.prato-detail table tbody tr')).map(tr => {
      const btn = tr.querySelector('button[style*="var(--danger)"]');
      if (btn) {
        const match = btn.getAttribute('onclick').match(/removerIngrediente\(\d+, (\d+)/);
        return match ? parseInt(match[1]) : null;
      }
      return null;
    }).filter(Boolean)
  );
  const disponiveis = todosIngredientes.filter(i =>
    !idsNoPrato.has(i.id) && i.nome.toLowerCase().includes(q)
  ).slice(0, 100);
  const el = document.getElementById('ingredientesDisponiveis');
  if (disponiveis.length === 0) {
    el.innerHTML = '<div style="color:var(--text2);font-size:0.85rem;padding:4px;">Nenhum ingrediente disponível</div>';
    return;
  }
  el.innerHTML = disponiveis.map(i =>
    `<button class="btn btn-sm" style="background:var(--surface2);color:var(--text);margin:2px;white-space:nowrap;"
            onclick="adicionarIngrediente(${pratoAtivo}, ${i.id}, '${i.nome.replace(/'/g, "\\'")}')">
       ${i.nome}
     </button>`
  ).join('');
}

async function adicionarIngrediente(pratoId, ingredienteId, nome) {
  const qtd = parseFloat(document.getElementById('addIngQtd').value) || 10;
  const r = await fetch(`/api/composicao/${pratoId}/add/${ingredienteId}`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ quantidade_g: qtd })
  });
  if (r.ok) {
    selecionarPrato(pratoId);
    carregarPratos();
  } else {
    const err = await r.json();
    alert(err.error || 'Erro ao adicionar ingrediente');
  }
}

async function removerIngrediente(pratoId, ingredienteId, nome) {
  if (!confirm(`Remover "${nome}" do prato?`)) return;
  const r = await fetch(`/api/composicao/${pratoId}/${ingredienteId}`, {
    method: 'DELETE'
  });
  if (r.ok) {
    selecionarPrato(pratoId);
    carregarPratos();
  }
}

carregarPratos();
carregarIngredientes();
</script>
</body>
</html>
'''


if __name__ == '__main__':
    # Cria o diretório de templates se não existir
    templates_dir = os.path.join(os.path.dirname(__file__), 'templates', 'admin')
    os.makedirs(templates_dir, exist_ok=True)

    # Escreve o template do dashboard
    dashboard_path = os.path.join(templates_dir, 'dashboard.html')
    with open(dashboard_path, 'w', encoding="utf-8") as f:
        f.write(DASHBOARD_TEMPLATE)

    print("=" * 60)
    print("🏥  Cardápio Hospitalar — Admin Interface")
    print("=" * 60)
    #print(f"📍  http://10.0.0.6:5000")
    print(f"📁  BD: {app.config['SQLALCHEMY_DATABASE_URI']}")
    print("=" * 60)
    app.run(debug=True, host='0.0.0.0', port=5002)
