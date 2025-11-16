from flask import Blueprint, render_template, current_app
from auth import login_required
from models.db import get_db

growth_bp = Blueprint('growth', __name__, url_prefix="/growth")

@growth_bp.route('/')
@login_required
def dashboard():
    db = get_db(current_app)
    cur = db.cursor()

    # Total de subtareas cerradas
    cur.execute("""
        SELECT COUNT(*) AS total
        FROM subtasks
        WHERE cerrado = 1;
    """)
    total_cerradas = cur.fetchone()['total']

    # Total por KR
    cur.execute("""
        SELECT kr, COUNT(*) AS cnt
        FROM subtasks
        WHERE kr IS NOT NULL AND kr != '' AND cerrado = 1
        GROUP BY kr;
    """)
    kr_stats = cur.fetchall()

    # Dificultad
    cur.execute("""
        SELECT dificultad, COUNT(*) AS cnt
        FROM subtasks
        WHERE cerrado = 1
        GROUP BY dificultad;
    """)
    dificultad_stats = cur.fetchall()

    # Tecnologías
    cur.execute("""
        SELECT tecnologia, COUNT(*) AS cnt
        FROM subtasks
        WHERE tecnologia IS NOT NULL AND tecnologia != '' AND cerrado = 1
        GROUP BY tecnologia;
    """)
    tecnologia_stats = cur.fetchall()

    return render_template(
    "growth_dashboard.html",
    total_cerradas=int(total_cerradas) if total_cerradas else 0,
    kr_stats=[{"kr": row["kr"], "cnt": row["cnt"]} for row in kr_stats],
    dificultad_stats=[{"dificultad": row["dificultad"], "cnt": row["cnt"]} for row in dificultad_stats],
    tecnologia_stats=[{"tecnologia": row["tecnologia"], "cnt": row["cnt"]} for row in tecnologia_stats],
)


from flask import jsonify, current_app
from auth import login_required
from models.db import get_db

@growth_bp.route("/notifs")
@login_required
def growth_notifs():
    """Últimas notificaciones"""
    db = get_db(current_app)
    cur = db.cursor()
    cur.execute("""
        SELECT mensaje, fecha
        FROM notifications
        ORDER BY datetime(fecha) DESC
        LIMIT 20;
    """)
    rows = cur.fetchall()

    return jsonify([
        {"mensaje": r["mensaje"], "fecha": r["fecha"]}
        for r in rows
    ])


@growth_bp.route("/notifs/marcar_vistas")
@login_required
def growth_marcar_vistas():
    """Marcar notificaciones como leídas"""
    db = get_db(current_app)
    cur = db.cursor()
    cur.execute("UPDATE notifications SET visto = 1;")
    db.commit()
    return jsonify({"ok": True})
