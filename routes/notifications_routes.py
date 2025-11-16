# routes/notifications_routes.py

from flask import Blueprint, render_template, jsonify, current_app
from auth import login_required
from models.db import get_db

notifications_bp = Blueprint('notifications', __name__, url_prefix="/notificaciones")


# ✅ Página con lista completa
@notifications_bp.route("/")
@login_required
def listar():
    db = get_db(current_app)
    cur = db.cursor()

    cur.execute("SELECT * FROM notifications ORDER BY datetime(fecha) DESC")
    notis = cur.fetchall()

    cur.execute("UPDATE notifications SET visto = 1 WHERE visto = 0")
    db.commit()

    return render_template("notificaciones.html", notificaciones=notis)


# ✅ API: Para mostrar número en 🔔
@notifications_bp.route("/pendientes")
@login_required
def pendientes():
    db = get_db(current_app)
    cur = db.cursor()
    cur.execute("SELECT COUNT(*) AS c FROM notifications WHERE visto = 0")
    c = cur.fetchone()["c"]
    return jsonify({"pendientes": c})


# ✅ API: Feed para el Modal con scroll
@notifications_bp.route("/feed")
@login_required
def feed():
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


# ✅ API: Marcar todas como vistas
@notifications_bp.route("/marcar_vistas")
@login_required
def marcar_vistas():
    db = get_db(current_app)
    cur = db.cursor()

    cur.execute("UPDATE notifications SET visto = 1")
    db.commit()

    return jsonify({"status": "ok"})
