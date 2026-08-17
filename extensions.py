from flask_sqlalchemy import SQLAlchemy
from flask_admin import Admin
from flask_admin.theme import Bootstrap4Theme
from flask_login import LoginManager

db = SQLAlchemy()
admin = Admin(name='Cardápio Hospitalar', theme=Bootstrap4Theme())
login_manager = LoginManager()
