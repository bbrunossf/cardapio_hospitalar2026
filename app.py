"""
App Flask + SQLAlchemy + Flask-Admin
Interface administrativa para o banco de Cardápio Hospitalar
"""
from flask import Flask, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_admin import Admin, AdminIndexView, expose
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
    desativado = db.Column(db.Boolean, default=False)

    def __str__(self):
        return self.nome


class FormaPreparo(db.Model):
    __tablename__ = 'formas_preparo'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nome = db.Column(db.String(50))
    descricao = db.Column(db.Text)
    fator_correcao = db.Column(db.Numeric(4,2))
    fator_parte_comestivel = db.Column(db.Numeric(4,2))
    criado_em = db.Column(db.DateTime, server_default=text('CURRENT_TIMESTAMP'))
    editado_em = db.Column(db.DateTime, server_default=text('CURRENT_TIMESTAMP'))
    desativado = db.Column(db.Boolean, default=False)

    def __str__(self):
        return self.nome or ''


class Preparacao(db.Model):
    __tablename__ = 'preparacoes'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ingrediente_id = db.Column(db.Integer, db.ForeignKey('ingredientes.id', ondelete='CASCADE'), nullable=False)
    forma_preparo_id = db.Column(db.Integer, db.ForeignKey('formas_preparo.id', ondelete='CASCADE'), nullable=False)
    nome_completo = db.Column(db.String(150))
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
    tempo_preparo_min = db.Column(db.Integer)
    dificuldade = db.Column(db.Integer)
    observacoes = db.Column(db.Text)
    criado_em = db.Column(db.DateTime, server_default=text('CURRENT_TIMESTAMP'))
    editado_em = db.Column(db.DateTime, server_default=text('CURRENT_TIMESTAMP'))
    desativado = db.Column(db.Boolean, default=False)

    ingrediente = db.relationship('Ingrediente', backref='preparacoes')
    forma_preparo = db.relationship('FormaPreparo', backref='preparacoes')

    def __str__(self):
        return self.nome_completo or ''


class TipoPrato(db.Model):
    __tablename__ = 'tipos_prato'
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
    tipo_prato_id = db.Column(db.Integer, db.ForeignKey('tipos_prato.id', ondelete='CASCADE'), nullable=False)
    cor_predominante = db.Column(db.String(30))
    consistencia = db.Column(db.String(30))
    textura = db.Column(db.String(50))
    temperatura_servimento = db.Column(db.String(30))
    porcao_padrao_g = db.Column(db.Numeric(8,2))
    energia_kcal = db.Column(db.Numeric(8,2))
    lipidios_g = db.Column(db.Numeric(8,2))
    proteina_g = db.Column(db.Numeric(8,2))
    carboidrato_g = db.Column(db.Numeric(8,2))
    fibra_alimentar_g = db.Column(db.Numeric(8,2))
    calcio_mg = db.Column(db.Numeric(8,2))
    ferro_mg = db.Column(db.Numeric(8,2))
    sodio_mg = db.Column(db.Numeric(8,2))
    custo_total = db.Column(db.Numeric(10,4))
    tempo_producao_min = db.Column(db.Integer)
    criado_em = db.Column(db.DateTime, server_default=text('CURRENT_TIMESTAMP'))
    editado_em = db.Column(db.DateTime, server_default=text('CURRENT_TIMESTAMP'))
    desativado = db.Column(db.Boolean, default=False)

    tipo_prato = db.relationship('TipoPrato', backref='pratos')

    def __str__(self):
        return self.nome or ''


class PratoPreparacao(db.Model):
    __tablename__ = 'prato_preparacoes'
    prato_id = db.Column(db.Integer, db.ForeignKey('pratos.id', ondelete='CASCADE'), primary_key=True)
    preparacao_id = db.Column(db.Integer, db.ForeignKey('preparacoes.id', ondelete='CASCADE'), primary_key=True)
    quantidade_g = db.Column(db.Numeric(8,2))
    percentual = db.Column(db.Numeric(5,2))
    criado_em = db.Column(db.DateTime, server_default=text('CURRENT_TIMESTAMP'))
    editado_em = db.Column(db.DateTime, server_default=text('CURRENT_TIMESTAMP'))
    desativado = db.Column(db.Boolean, default=False)

    prato = db.relationship('Prato', backref='prato_preparacoes')
    preparacao = db.relationship('Preparacao', backref='prato_preparacoes')


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


class VariacaoPreparacao(db.Model):
    __tablename__ = 'variacoes_preparacao'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    preparacao_id = db.Column(db.Integer, db.ForeignKey('preparacoes.id', ondelete='CASCADE'), nullable=False)
    dieta_id = db.Column(db.Integer, db.ForeignKey('dietas.id', ondelete='CASCADE'), nullable=False)
    nome_exibicao = db.Column(db.String(150))
    sodio_mg = db.Column(db.Numeric(8,2))
    energia_kcal = db.Column(db.Numeric(8,2))
    lipidios_g = db.Column(db.Numeric(8,2))
    gordura_saturada_g = db.Column(db.Numeric(8,2))
    carboidrato_g = db.Column(db.Numeric(8,2))
    proteina_g = db.Column(db.Numeric(8,2))
    fibra_alimentar_g = db.Column(db.Numeric(8,2))
    observacoes = db.Column(db.Text)
    criado_em = db.Column(db.DateTime, server_default=text('CURRENT_TIMESTAMP'))
    editado_em = db.Column(db.DateTime, server_default=text('CURRENT_TIMESTAMP'))
    desativado = db.Column(db.Boolean, default=False)

    preparacao = db.relationship('Preparacao', backref='variacoes')
    dieta = db.relationship('Dieta', backref='variacoes')

    def __str__(self):
        return self.nome_exibicao or ''


# ─── VIEWS ADMIN ──────────────────────────────────────────────────────────

class BaseModelView(ModelView):
    can_create = True
    can_edit = True
    can_delete = True
    can_export = True
    create_modal = True
    edit_modal = True
    page_size = 20

    column_display_pk = False  # hide PK column by default
    column_hide_backrefs = False


class IngredienteView(BaseModelView):
    column_list = ['nome', 'tipo_alimento', 'energia_kcal', 'proteina_g',
                   'lipidios_g', 'carboidrato_g', 'custo_por_100g', 'disponibilidade']
    column_searchable_list = ['nome', 'tipo_alimento']
    column_filters = ['tipo_alimento', 'disponibilidade', 'desativado']
    column_editable_list = ['disponibilidade', 'custo_por_100g']
    form_excluded_columns = ['criado_em', 'editado_em']
    column_labels = {
        'nome': 'Nome', 'tipo_alimento': 'Tipo', 'energia_kcal': 'Kcal',
        'proteina_g': 'Proteína (g)', 'lipidios_g': 'Lipídios (g)',
        'carboidrato_g': 'Carboidrato (g)', 'custo_por_100g': 'Custo R$',
        'disponibilidade': 'Disponível'
    }


class FormaPreparoView(BaseModelView):
    column_list = ['nome', 'descricao', 'fator_correcao', 'fator_parte_comestivel']
    column_searchable_list = ['nome']
    form_excluded_columns = ['criado_em', 'editado_em']


class PreparacaoView(BaseModelView):
    column_list = ['nome_completo', 'ingrediente', 'forma_preparo',
                   'energia_kcal', 'proteina_g', 'lipidios_g', 'sodio_mg']
    column_searchable_list = ['nome_completo']
    column_filters = ['forma_preparo', 'energia_kcal']
    form_excluded_columns = ['criado_em', 'editado_em', 'variacoes', 'prato_preparacoes']
    column_labels = {
        'nome_completo': 'Preparação', 'ingrediente': 'Ingrediente',
        'forma_preparo': 'Forma', 'energia_kcal': 'Kcal',
        'proteina_g': 'Proteína', 'lipidios_g': 'Lipídios', 'sodio_mg': 'Sódio'
    }


class TipoPratoView(BaseModelView):
    column_list = ['nome', 'ordem_servico']
    column_searchable_list = ['nome']
    form_excluded_columns = ['criado_em', 'editado_em', 'pratos']


class PratoView(BaseModelView):
    column_list = ['nome', 'tipo_prato', 'energia_kcal', 'proteina_g',
                   'lipidios_g', 'carboidrato_g', 'consistencia', 'temperatura_servimento']
    column_searchable_list = ['nome']
    column_filters = ['tipo_prato', 'consistencia', 'temperatura_servimento']
    form_excluded_columns = ['criado_em', 'editado_em', 'prato_preparacoes']
    column_labels = {
        'tipo_prato': 'Tipo', 'consistencia': 'Consistência',
        'temperatura_servimento': 'Temperatura'
    }


class PratoPreparacaoView(BaseModelView):
    column_list = ['prato', 'preparacao', 'quantidade_g', 'percentual']
    column_filters = ['prato', 'preparacao']
    form_excluded_columns = ['criado_em', 'editado_em']


class DietaView(BaseModelView):
    column_list = ['nome', 'com_sal', 'descricao']
    column_searchable_list = ['nome']
    column_filters = ['com_sal']
    form_excluded_columns = ['criado_em', 'editado_em', 'variacoes']
    column_labels = {'com_sal': 'Com sal?', 'descricao': 'Descrição'}
    column_editable_list = ['com_sal']


class VariacaoPreparacaoView(BaseModelView):
    column_list = ['nome_exibicao', 'preparacao', 'dieta', 'sodio_mg', 'energia_kcal']
    column_searchable_list = ['nome_exibicao']
    column_filters = ['dieta', 'sodio_mg']
    form_excluded_columns = ['criado_em', 'editado_em']
    column_labels = {
        'nome_exibicao': 'Nome', 'preparacao': 'Preparação',
        'dieta': 'Dieta', 'sodio_mg': 'Sódio (mg)', 'energia_kcal': 'Kcal'
    }


# ─── DASHBOARD ───────────────────────────────────────────────────────────

class DashboardView(AdminIndexView):

    @expose('/')
    def index(self):
        stats = {
            'ingredientes': Ingrediente.query.filter_by(desativado=False).count(),
            'preparacoes': Preparacao.query.filter_by(desativado=False).count(),
            'pratos': Prato.query.filter_by(desativado=False).count(),
            'dietas': Dieta.query.count(),
            'variacoes': VariacaoPreparacao.query.filter_by(desativado=False).count(),
        }

        # Top pratos mais calóricos
        top_kcal = db.session.execute(
            text("SELECT nome, energia_kcal, proteina_g FROM pratos ORDER BY energia_kcal DESC LIMIT 5")
        ).mappings().all()

        # Top ingredientes com mais proteína
        top_prot = db.session.execute(
            text("SELECT nome, proteina_g, tipo_alimento FROM ingredientes ORDER BY proteina_g DESC LIMIT 5")
        ).mappings().all()

        # Preparações com maior sódio (dieta com sal)
        top_sodio = db.session.execute(
            text("""
                SELECT p.nome_completo, v.sodio_mg
                FROM variacoes_preparacao v
                JOIN preparacoes p ON v.preparacao_id = p.id
                JOIN dietas d ON v.dieta_id = d.id
                WHERE d.nome = 'Padrão c/ sal'
                ORDER BY v.sodio_mg DESC LIMIT 5
            """)
        ).mappings().all()

        # Distribuição de consistência
        consistencias = db.session.execute(
            text("SELECT consistencia, COUNT(*) as qtd FROM pratos GROUP BY consistencia ORDER BY qtd DESC")
        ).mappings().all()

        # Dietas com/sem sal
        dietas_sal = db.session.execute(
            text("SELECT com_sal, COUNT(*) as qtd FROM dietas GROUP BY com_sal")
        ).mappings().all()

        return self.render('admin/dashboard.html',
                           stats=stats,
                           top_kcal=top_kcal,
                           top_prot=top_prot,
                           top_sodio=top_sodio,
                           consistencias=consistencias,
                           consistencias_total=sum(c.qtd for c in consistencias),
                           dietas_sal=dietas_sal)


# ─── TEMPLATE DASHBOARD ──────────────────────────────────────────────────

DASHBOARD_TEMPLATE = '''
{% extends 'admin/master.html' %}
{% block body %}
<div style="padding: 20px;">
  <h1>📊 Cardápio Hospitalar — Dashboard</h1>
  <p style="color: #666;">Épico 1: Gestão de Dados Mestres</p>

  <div style="display: flex; gap: 15px; flex-wrap: wrap; margin: 25px 0;">
    {% for label, count in [('🥩 Ingredientes', stats.ingredientes), ('🍳 Preparações', stats.preparacoes), ('🍽️ Pratos', stats.pratos), ('🥗 Dietas', stats.dietas), ('🔄 Variações', stats.variacoes)] %}
    <div style="flex: 1; min-width: 150px; background: #f8f9fa; border-radius: 10px; padding: 20px; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
      <div style="font-size: 2.5em; font-weight: bold; color: #2c3e50;">{{ count }}</div>
      <div style="color: #7f8c8d; margin-top: 5px;">{{ label }}</div>
    </div>
    {% endfor %}
  </div>

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
          <td style="padding: 6px;">{{ p.nome }}</td>
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
      <h3>🧂 + Sódio (c/ sal)</h3>
      <table style="width: 100%; border-collapse: collapse;">
        <tr style="border-bottom: 2px solid #eee;">
          <th style="text-align: left; padding: 8px;">Preparação</th>
          <th style="text-align: right; padding: 8px;">Sódio</th>
        </tr>
        {% for p in top_sodio %}
        <tr style="border-bottom: 1px solid #f0f0f0;">
          <td style="padding: 6px;">{{ p.nome_completo }}</td>
          <td style="text-align: right; padding: 6px; font-weight: bold;">{{ "%.0f"|format(p.sodio_mg|float) }}mg</td>
        </tr>
        {% endfor %}
      </table>
      <div style="margin-top: 15px; padding: 10px; background: #fff3cd; border-radius: 5px; font-size: 0.85em;">
        💡 Na dieta <strong>sem sal</strong>, todas zeram.
      </div>
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
admin.add_view(FormaPreparoView(FormaPreparo, db, name='Formas Preparo'))
admin.add_view(PreparacaoView(Preparacao, db, name='Preparações'))
admin.add_view(TipoPratoView(TipoPrato, db, name='Tipos Prato'))
admin.add_view(PratoView(Prato, db, name='Pratos'))
admin.add_view(PratoPreparacaoView(PratoPreparacao, db, name='Relações Prato-Prep'))
admin.add_view(DietaView(Dieta, db, name='Dietas'))
admin.add_view(VariacaoPreparacaoView(VariacaoPreparacao, db, name='Variações'))


@app.route('/')
def root():
    return redirect(url_for('admin.index'))


if __name__ == '__main__':
    # Cria o diretório de templates se não existir
    templates_dir = os.path.join(os.path.dirname(__file__), 'templates', 'admin')
    os.makedirs(templates_dir, exist_ok=True)

    # Escreve o template do dashboard
    dashboard_path = os.path.join(templates_dir, 'dashboard.html')
    with open(dashboard_path, 'w') as f:
        f.write(DASHBOARD_TEMPLATE)

    print("=" * 60)
    print("🏥  Cardápio Hospitalar — Admin Interface")
    print("=" * 60)
    print(f"📍  http://10.0.0.6:5000")
    print(f"📁  BD: {app.config['SQLALCHEMY_DATABASE_URI']}")
    print("=" * 60)
    app.run(debug=True, host='0.0.0.0', port=5000)
