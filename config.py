import os
from dotenv import load_dotenv

load_dotenv()

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or os.urandom(32).hex()

    # Поддержка PostgreSQL (Render.com использует postgres://, SQLAlchemy требует postgresql://)
    _database_url = os.environ.get('DATABASE_URL')
    if _database_url and _database_url.startswith('postgres://'):
        _database_url = _database_url.replace('postgres://', 'postgresql://', 1)

    SQLALCHEMY_DATABASE_URI = _database_url or \
        'sqlite:///' + os.path.join(basedir, 'nii_aem.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
