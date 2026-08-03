from flask_admin.contrib.sqla import ModelView
from flask_admin.menu import MenuLink
from models import (
    Ingrediente, TipoPrato, Prato, PratoComposicao,
    Dieta, TipoRefeicao, RegraComposicao, DietaRefeicao,
    RegraElegibilidadeDieta, RestricaoNutricionalDieta,
    RegraSensorialGeral, RegraVariedade, VwPratosNutricional
)
from extensions import db, admin


# ─── BaseModelView ──────────────────────────────────────────────────────
class BaseModelView(ModelView):
    can_create = True
    can_edit = True
    can_delete = True
    can_export = True
    create_modal = False
    edit_modal = False
    page_size = 40
    column_display_pk = False
    column_hide_backrefs = False


# ─── (cole aqui TODAS as classes de view, L269–393) ────────────────────
# IngredienteView, TipoPratoView, PratoView, DietaView,
# PratoComposicaoView, TipoRefeicaoView, RegraComposicaoView,
# DietaRefeicaoView, RegraElegibilidadeDietaView,
# RestricaoNutricionalDietaView, RegraSensorialGeralView,
# RegraVariedadeView, VwPratosNutricionalView
#
#
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




# ─── Função de setup ────────────────────────────────────────────────────
def setup_admin():
    """Registra todas as views no admin."""

    admin.add_view(IngredienteView(Ingrediente, db, name='Ingredientes'))
    admin.add_view(TipoPratoView(TipoPrato, db, name='Tipos Prato'))
    admin.add_view(PratoView(Prato, db, name='Pratos'))
    admin.add_view(DietaView(Dieta, db, name='Dietas'))

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
