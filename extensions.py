from flask_sqlalchemy import SQLAlchemy
from flask_admin import Admin
from flask_admin.theme import Bootstrap4Theme

db = SQLAlchemy()
admin = Admin(name='Cardápio Hospitalar', theme=Bootstrap4Theme())
