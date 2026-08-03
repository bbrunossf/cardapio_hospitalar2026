from flask_admin import AdminIndexView, expose
from sqlalchemy import text
from models import Ingrediente, Prato, Dieta, TipoRefeicao
from extensions import db


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

        # ... (cole EXATAMENTE o restante das queries do método index,
        #      linhas 412–439, sem alteração)
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
