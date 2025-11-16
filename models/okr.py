# models/okr.py
from models.db import get_db

def get_okrs(app):
    """Devuelve todos los KR activos ordenados por categoría."""
    db = get_db(app)
    cur = db.cursor()
    cur.execute("""
        SELECT categoria, kr
        FROM okr_kr
        WHERE activo = 1
        ORDER BY categoria, kr;
    """)
    return cur.fetchall()
