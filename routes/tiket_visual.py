from flask import Blueprint, render_template, current_app
from models import get_db

visual_bp = Blueprint('visual', __name__)

@visual_bp.route('/visual_tikets')
def visualizar_tikets():
    """
    Vista jerárquica de tickets agrupados por proyecto y KR (Key Result).
    """
    db = get_db(current_app)
    cur = db.cursor()

    # 1️⃣ Obtener proyectos
    cur.execute("SELECT id, nombre FROM projects ORDER BY nombre;")
    proyectos = cur.fetchall()

    data = []

    # 2️⃣ Para cada proyecto, obtener subtareas agrupadas por KR
    for p in proyectos:
        cur.execute("""
            SELECT kr, id, numero_de_queja, nombre_subtarea, cerrado, dificultad, prioridad
            FROM subtasks
            WHERE project_id = ?
            ORDER BY kr, cerrado, dificultad DESC;
        """, (p['id'],))
        subtareas = cur.fetchall()

        # Agrupar subtareas por KR (si no tiene KR, mostrar "Sin KR")
        krs = {}
        for s in subtareas:
            grupo = s['kr'] if s['kr'] else "Sin KR"
            krs.setdefault(grupo, []).append(s)

        data.append({
            "proyecto": p['nombre'],
            "krs": krs
        })

    return render_template('visual_tikets.html', data=data)
