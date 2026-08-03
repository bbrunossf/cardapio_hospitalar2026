import os


class Config:
    SECRET_KEY = 'cardapio-hospitalar-secret'
    BASEDIR = os.path.abspath(os.path.dirname(__file__))
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(BASEDIR, 'cardapio_hospitalar.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
