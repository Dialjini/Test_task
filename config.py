import os
basedir = os.path.abspath(os.path.dirname(__file__))

DEBUG = True
SECRET_KEY = 'f932b03c797e880432f11149'
SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'app.db')
SQLALCHEMY_MIGRATE_REPO = os.path.join(basedir, 'db_repository')
SQLALCHEMY_TRACK_MODIFICATIONS = False
