import sys
sys.path.insert(0, r \c:\Users\SINAN\padikkunnundo.app\')
from app import create_app
from sqlalchemy import inspect
from models import db

app = create_app()
with app.app_context():
    inspector = inspect(db.engine)
    cols = [c[\name\'] for c in inspector.get_columns(\users\')]
    print(\Current columns:\', cols)
