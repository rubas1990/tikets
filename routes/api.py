# routes/api.py
from flask import Blueprint, jsonify
from datetime import datetime
import pytz
from models import get_db
from flask import current_app

api_bp = Blueprint('api', __name__)

@api_bp.route('/api/subtareas_cerradas_hoy')
def api_subtareas_cerradas_hoy():
    """Devuelve el número de subtareas cerradas hoy"""
    tz = pytz.timezone("America/Monterrey")
    hoy = datetime.now(tz).date()
    db = get_db(current_app)
    cur = db.cursor()
    cur.execute("""
        SELECT COUNT(*) AS cerradas
        FROM subtasks
        WHERE DATE(fecha_cierre) = ? AND cerrado = 1;
    """, (hoy,))
    row = cur.fetchone()
    return jsonify({"cerradas": row["cerradas"] if row else 0})
