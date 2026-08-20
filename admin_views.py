from flask import abort, redirect, request, url_for
from flask_admin.contrib.sqla import ModelView
from flask_admin.menu import MenuLink
from flask_login import current_user
from wtforms import PasswordField

from models import (
    Ingrediente, TipoPrato, Prato, PratoComposicao,
    Dieta, TipoRefeicao, RegraComposicao, DietaRefeicao,
    RegraElegibilidadeDieta, RestricaoNutricionalDieta,
    RegraSensorialGeral, RegraVariedade, VwPratosNutricional
)
from models_rotulo import AlimentoIndustrializado, AlimentoVersao, VwAlimentosIndustrializados100g
from models_paciente import Paciente
from models_auth import Usuario
from authz import is_admin
from extensions import db, admin


# ─── BaseModelView ──────────────────────────────────────────────────────
class BaseModelView(ModelView):
    can_export = True
    create_modal = False
    edit_modal = False
    page_size = 15
    column_display_pk = False
    column_hide_backrefs = False

    # ─── Controle de acesso (docs/autenticacao.md) ─────────────────────────
    # papeis_acesso: quem vê a view no menu. papeis_escrita: quem pode CRUD.
    # escopo_por_dono: filtra por pacientes.criado_por (não-admin).
    papeis_acesso = ("admin", "nutricionista", "leitura")
    papeis_escrita = ("admin", "nutricionista")
    escopo_por_dono = False

    def is_accessible(self):
        if not current_user.is_authenticated:
            return False
        return current_user.papel in self.papeis_acesso

    def inaccessible_callback(self, name, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login", next=request.url))
        return abort(403)

    def _pode_escrever(self):
        return current_user.is_authenticated and current_user.papel in self.papeis_escrita

    @property
    def can_create(self):
        return self._pode_escrever()

    @property
    def can_edit(self):
        return self._pode_escrever()

    @property
    def can_delete(self):
        return self._pode_escrever()

    # Escopo por dono (equivalente a RLS na aplicação — SQLite não tem RLS)
    def get_query(self):
        q = super().get_query()
        if self.escopo_por_dono and not is_admin():
            q = q.filter(self.model.criado_por == current_user.id)
        return q

    def get_count_query(self):
        q = super().get_count_query()
        if self.escopo_por_dono and not is_admin():
            q = q.filter(self.model.criado_por == current_user.id)
        return q

    def get_one(self, id):
        obj = super().get_one(id)
        if obj is None:
            return None
        if self.escopo_por_dono and not is_admin() and obj.criado_por != current_user.id:
            return None
        return obj


# ─── Usuários (só admin; senha nunca listada; soft delete) ──────────────
class UsuarioView(BaseModelView):
    papeis_acesso = ("admin",)
    papeis_escrita = ("admin",)
    can_delete = False  # desativar em vez de apagar (pacientes referenciam)

    column_list = ["nome", "email", "papel", "ultimo_login", "desativado", "criado_em"]
    column_searchable_list = ["nome", "email"]
    column_filters = ["papel", "desativado"]
    column_choices = {
        "papel": [("admin", "admin"), ("nutricionista", "nutricionista"), ("leitura", "leitura")],
    }
    column_labels = {
        "nome": "Nome", "email": "E-mail", "papel": "Papel",
        "ultimo_login": "Último login", "desativado": "Inativo", "criado_em": "Criado em",
    }
    form_excluded_columns = ["senha_hash", "criado_em", "editado_em", "ultimo_login"]
    form_extra_fields = {
        "senha": PasswordField("Senha"),
        "confirmar": PasswordField("Confirmar senha"),
    }

    def validate_form(self, form):
        if not super().validate_form(form):
            return False
        if form.senha.data and form.senha.data != form.confirmar.data:
            form.confirmar.errors.append("As senhas não conferem.")
            return False
        if request.endpoint and request.endpoint.endswith("create_view") and not form.senha.data:
            form.senha.errors.append("Senha é obrigatória no cadastro.")
            return False
        return True

    def on_model_change(self, form, model, is_created):
        if form.senha.data:
            model.set_senha(form.senha.data)


# ─── Catálogo (nutricionista pode CRUD) ─────────────────────────────────
class IngredienteView(BaseModelView):
    column_list = ['nome', 'tipo_alimento', 'qtde', 'unidade_medida', 'energia_kcal', 'carboidrato_g', 'proteina_g', 'lipidios_g', 'fibra_alimentar_g', 'calcio_mg',
    'ferro_mg', 'sodio_mg', 'potassio_mg', 'fosforo_mg', 'vit_c_mg', 'vit_a_mg',
    'gordura_saturada_g', 'colesterol_mg',


    'custo_por_100g', 'disponibilidade', 'observacoes', 'fonte', 'desativado']

    list_template = 'admin/ingrediente_list.html'
    edit_template = 'admin/ingrediente_edit.html'

    column_searchable_list = ['nome', 'tipo_alimento']
    column_filters = ['tipo_alimento', 'disponibilidade', 'desativado']
    column_editable_list = ['disponibilidade', 'custo_por_100g']
    # 'composicoes' (backref to-many p/ prato_composicao) NÃO pode entrar no form:
    # a PK de prato_composicao é (prato_id, ingrediente_id) e o campo vazio faria o
    # SQLAlchemy tentar NULLar ingrediente_id ao salvar (AssertionError
    # "tried to blank-out primary key column"). Composição se edita na Ficha Técnica.
    form_excluded_columns = ['criado_em', 'editado_em', 'composicoes']

    # Labels com \n = quebra de linha no header (nome na 1ª linha, unidade na 2ª).
    # \u00a0 = espaço não-quebrável: nomes compostos não quebram no meio.
    # No form de edição o \n vira espaço normal ("Carboidrato (g)"), sem efeito visual.
    column_labels = {
        'nome': 'Nome', 'tipo_alimento': 'Tipo',
        'qtde': 'Qtde', 'unidade_medida': 'Unidade',
        'energia_kcal': 'Energia\n(kcal)',
        'carboidrato_g': 'Carboidrato\n(g)',
        'proteina_g': 'Proteína\n(g)',
        'lipidios_g': 'Lipídios\n(g)',
        'fibra_alimentar_g': 'Fibra\u00a0Alimentar\n(g)',
        'calcio_mg': 'Cálcio\n(mg)',
        'ferro_mg': 'Ferro\n(mg)',
        'sodio_mg': 'Sódio\n(mg)',
        'potassio_mg': 'Potássio\n(mg)',
        'fosforo_mg': 'Fósforo\n(mg)',
        'vit_c_mg': 'Vitamina\u00a0C\n(mg)',
        'vit_a_mg': 'Vitamina\u00a0A\n(mg)',
        'gordura_saturada_g': 'Gordura\u00a0Saturada\n(g)',
        'colesterol_mg': 'Colesterol\n(mg)',
        'custo_por_100g': 'Custo\n(R$/100g)',
        'disponibilidade': 'Disponível',
        'observacoes': 'Observações',
        'fonte': 'Fonte',
        'desativado': 'Inativo'
    }
# class IngredienteView(ModelView):
    # pass

class TipoPratoView(BaseModelView):
    papeis_escrita = ("admin",)
    column_list = ['nome', 'ordem_servico']
    column_searchable_list = ['nome']
    # Backrefs to-many fora do form: campo vazio NULLaria as FKs (regras_composicao/
    # regras_variedade são nuláveis no schema) e orfanaria linhas silenciosamente.
    form_excluded_columns = ['criado_em', 'editado_em', 'pratos', 'regras_composicao', 'regras_variedade']


class PratoView(BaseModelView):
    column_list = ['nome', 'tipo_prato', 'consistencia', 'temperatura_servimento']
    column_searchable_list = ['nome']
    column_filters = ['tipo_prato', 'consistencia', 'temperatura_servimento']
    # 'composicoes' (backref to-many p/ prato_composicao): PK composta não-nulável —
    # o campo vazio no form estoura AssertionError ao salvar (mesmo caso do Ingrediente).
    form_excluded_columns = ['criado_em', 'editado_em', 'prato_preparacoes', 'passos_preparo', 'composicoes']
    column_labels = {
        'tipo_prato': 'Tipo', 'consistencia': 'Consistência',
        'temperatura_servimento': 'Temperatura'
    }


# ─── Regras globais (config do motor — só admin edita) ──────────────────
class DietaView(BaseModelView):
    papeis_escrita = ("admin",)
    column_list = ['nome', 'com_sal', 'descricao']
    column_searchable_list = ['nome']
    column_filters = ['com_sal']
    # Backrefs to-many fora do form: campo vazio NULLaria as FKs (nuláveis no schema)
    # e orfanaria dieta_refeicoes/regras silenciosamente ao salvar.
    form_excluded_columns = ['criado_em', 'editado_em', 'variacoes',
                             'dieta_refeicoes', 'regras_elegibilidade', 'restricoes_nutricionais']
    column_labels = {'com_sal': 'Com sal?', 'descricao': 'Descrição'}
    column_editable_list = ['com_sal']


class PratoComposicaoView(BaseModelView):
    column_list = ['prato', 'ingrediente', 'quantidade_g', 'desativado']
    column_searchable_list = ['prato.nome', 'ingrediente.nome']
    column_filters = ['desativado']
    column_editable_list = ['quantidade_g', 'desativado']
    form_excluded_columns = ['criado_em', 'editado_em', 'prato', 'ingrediente']
    column_labels = {
        'prato': 'Prato', 'ingrediente': 'Ingrediente',
        'quantidade_g': 'Quantidade (g)', 'desativado': 'Inativo',
        # labels dos campos de busca (placeholder limpo da caixa de pesquisa)
        'prato.nome': 'Prato', 'ingrediente.nome': 'Ingrediente',
    }
    column_sortable_list = ['quantidade_g', 'desativado']


# ==========================================
# NOVAS VIEWS ADMIN PARA REGRAS
# ==========================================

class TipoRefeicaoView(BaseModelView):
    papeis_escrita = ("admin",)
    column_list = ['nome', 'horario_padrao', 'descricao']
    column_searchable_list = ['nome']
    form_excluded_columns = ['criado_em', 'editado_em', 'regras_composicao', 'dieta_refeicoes', 'regras_sensoriais']

class RegraComposicaoView(BaseModelView):
    papeis_escrita = ("admin",)
    column_list = ['tipo_refeicao', 'tipo_prato', 'qtd_minima', 'qtd_maxima', 'obrigatorio']
    column_filters = ['tipo_refeicao', 'tipo_prato', 'obrigatorio']
    form_excluded_columns = ['id']

class DietaRefeicaoView(BaseModelView):
    papeis_escrita = ("admin",)
    column_list = ['dieta', 'tipo_refeicao']
    column_filters = ['dieta', 'tipo_refeicao']
    form_excluded_columns = ['id']

class RegraElegibilidadeDietaView(BaseModelView):
    papeis_escrita = ("admin",)
    column_list = ['dieta', 'atributo', 'valores_permitidos', 'operador']
    column_filters = ['dieta', 'atributo', 'operador']
    column_searchable_list = ['valores_permitidos']
    form_excluded_columns = ['id']
    form_widget_args = {
        'valores_permitidos': {'rows': 3} # Campo de texto maior para JSON
    }

class RestricaoNutricionalDietaView(BaseModelView):
    papeis_escrita = ("admin",)
    column_list = ['dieta', 'nutriente', 'valor_minimo', 'valor_maximo', 'periodo']
    column_filters = ['dieta', 'nutriente', 'periodo']
    form_excluded_columns = ['id']

class RegraSensorialGeralView(BaseModelView):
    papeis_escrita = ("admin",)
    column_list = ['tipo_refeicao', 'regra', 'valor_limite', 'grupos_afetados']
    column_filters = ['tipo_refeicao', 'regra']
    form_excluded_columns = ['id']
    form_widget_args = {
        'grupos_afetados': {'rows': 3}
    }

class RegraVariedadeView(BaseModelView):
    papeis_escrita = ("admin",)
    column_list = ['tipo_prato', 'dias_minimos_repeticao', 'frequencia_maxima_semanal']
    column_filters = ['tipo_prato']
    form_excluded_columns = ['id']


# ─── Consultas (somente leitura para todos) ─────────────────────────────
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


class AlimentoIndustrializadoView(BaseModelView):
    column_list = [
        'nome', 'marca', 'codigo_barras', 'peso_liquido', 'unidade_peso',
        'porcao_qtd', 'porcao_unidade', 'energia_kcal', 'carboidratos_g',
        'proteinas_g', 'gorduras_totais_g', 'fonte', 'versao', 'desativado'
    ]
    column_searchable_list = ['nome', 'marca', 'codigo_barras']
    column_filters = ['marca', 'fonte', 'desativado']
    form_excluded_columns = ['criado_em', 'editado_em', 'versoes']
    column_labels = {
        'nome': 'Nome', 'marca': 'Marca', 'codigo_barras': 'Código de Barras',
        'peso_liquido': 'Peso Líquido', 'unidade_peso': 'Unidade',
        'porcao_qtd': 'Porção', 'porcao_unidade': 'Unid. Porção',
        'energia_kcal': 'Energia (kcal)', 'carboidratos_g': 'Carboidratos (g)',
        'proteinas_g': 'Proteínas (g)', 'gorduras_totais_g': 'Gorduras Totais (g)',
        'fonte': 'Fonte', 'versao': 'Versão', 'desativado': 'Desativado'
    }


class AlimentoVersaoView(BaseModelView):
    can_create = False
    can_edit = False
    can_delete = False
    column_list = ['alimento', 'versao', 'motivo', 'criado_em']
    column_filters = ['versao', 'motivo']
    form_excluded_columns = ['criado_em']
    column_labels = {
        'alimento': 'Alimento', 'versao': 'Versão', 'motivo': 'Motivo', 'criado_em': 'Data'
    }


class VwAlimentosIndustrializados100gView(BaseModelView):
    can_create = False
    can_edit = False
    can_delete = False
    column_list = [
        'nome', 'marca', 'energia_kcal_100g', 'carboidratos_g_100g',
        'proteinas_g_100g', 'gorduras_totais_g_100g', 'fibras_g_100g', 'sodio_mg_100g'
    ]
    column_searchable_list = ['nome', 'marca']
    column_labels = {
        'nome': 'Nome', 'marca': 'Marca',
        'energia_kcal_100g': 'Energia/100g', 'carboidratos_g_100g': 'Carboidratos/100g',
        'proteinas_g_100g': 'Proteínas/100g', 'gorduras_totais_g_100g': 'Gorduras/100g',
        'fibras_g_100g': 'Fibras/100g', 'sodio_mg_100g': 'Sódio/100g'
    }


class PacienteView(BaseModelView):
    escopo_por_dono = True  # nutricionista só vê os próprios (criado_por)
    column_list = [
        'nome', 'sexo', 'data_nascimento', 'peso_kg', 'altura_cm',
        'cintura_cm', 'quadril_cm', 'objetivo', 'desativado'
    ]
    column_searchable_list = ['nome']
    column_filters = ['sexo', 'objetivo', 'desativado']
    form_excluded_columns = ['criado_em', 'editado_em', 'criado_por']
    column_labels = {
        'nome': 'Nome', 'sexo': 'Sexo', 'data_nascimento': 'Nascimento',
        'peso_kg': 'Peso (kg)', 'altura_cm': 'Altura (cm)',
        'cintura_cm': 'Cintura (cm)', 'quadril_cm': 'Quadril (cm)',
        'objetivo': 'Objetivo', 'desativado': 'Desativado'
    }



# ─── Função de setup ────────────────────────────────────────────────────
def setup_admin():
    """Registra todas as views no admin."""

    admin.add_view(UsuarioView(Usuario, db, name='Usuários'))
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
    admin.add_view(AlimentoIndustrializadoView(AlimentoIndustrializado, db, name='Alimentos Industrializados'))
    admin.add_view(AlimentoVersaoView(AlimentoVersao, db, name='Versões de Alimentos'))
    admin.add_view(VwPratosNutricionalView(VwPratosNutricional, db, name='Nutrientes (view)', category='Consultas'))
    admin.add_view(VwAlimentosIndustrializados100gView(VwAlimentosIndustrializados100g, db, name='Alimentos 100g (view)', category='Consultas'))
    admin.add_link(MenuLink(name='Ficha Técnica', url='/composicao-view', category='Ferramentas'))
    admin.add_view(PacienteView(Paciente, db, name='Pacientes (tabela)', endpoint="admin_paciente",))

    # Ferramentas — páginas standalone (fora do chrome do admin)
    admin.add_link(MenuLink(name='Pacientes', url='/pacientes', category='Ferramentas'))
    admin.add_link(MenuLink(name='Cadastro por Rótulo', url='/rotulo', category='Ferramentas'))
    admin.add_link(MenuLink(name='Otimização de Cardápio', url='/otimizacao', category='Ferramentas'))
    admin.add_link(MenuLink(name='Posso Comer?', url='/posso-comer', category='Ferramentas'))
    admin.add_link(MenuLink(name='Alimentos Semelhantes', url='/busca-semelhantes', category='Ferramentas'))
