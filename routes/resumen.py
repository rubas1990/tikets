# routes/resumen.py
from flask import Blueprint, render_template, current_app, g
from datetime import datetime
from models import get_db
import pytz

resumen_bp = Blueprint('resumen', __name__)

@resumen_bp.route('/resumen_dia')
def resumen_dia():
    """
    Dashboard diario: muestra subtareas cerradas, horas efectivas y score promedio.
    Compatible con tablas 'subtasks', 'projects' y 'project_tiempo'.
    """
    tz = pytz.timezone("America/Monterrey")
    hoy = datetime.now(tz).date()
    db = get_db(current_app)
    cur = db.cursor()

    # ⚙️ Usuario actual (por ahora Ruben por defecto)
    username = getattr(g, "user", {}).get("username", "ruben")

    # 🎯 Subtareas cerradas hoy
    cur.execute("""
        SELECT COUNT(*) AS cerradas 
        FROM subtasks 
        WHERE DATE(fecha_cierre) = ? AND cerrado = 1;
    """, (hoy,))
    subtareas_cerradas = cur.fetchone()["cerradas"]

    # 🕓 Tiempo total trabajado hoy (por proyectos)
    cur.execute("""
        SELECT p.nombre, p.status,
            COALESCE(ROUND(SUM((JULIANDAY(fin) - JULIANDAY(inicio)) * 24), 2), 0) AS horas
        FROM project_tiempo t
        JOIN projects p ON p.id = t.project_id
        WHERE DATE(t.inicio) = DATE(?)
        GROUP BY p.id
        ORDER BY p.nombre;
    """, (hoy,))
    rows = cur.fetchall()
    proyectos = [dict(r) for r in rows]  # ✅ convertir Row a dict

    horas_totales = sum((p["horas"] if p["horas"] is not None else 0) for p in proyectos) if proyectos else 0


    # 🔢 Score simulado (temporal si no existe emocional_log)
    for p in proyectos:
        p["score"] = 70 + hash(p["nombre"]) % 20  # genera número entre 70–89

    score_prom = round(sum(p["score"] for p in proyectos) / len(proyectos), 1) if proyectos else 0

    # 📈 Histórico últimos 7 días (subtareas cerradas)
    cur.execute("""
        SELECT DATE(fecha_cierre) AS fecha, COUNT(*) AS cerradas
        FROM subtasks
        WHERE cerrado = 1
        GROUP BY DATE(fecha_cierre)
        ORDER BY DATE(fecha_cierre) DESC
        LIMIT 7;
    """)
    historico_rows = cur.fetchall()
    historico = [dict(r) for r in historico_rows][::-1]  # más antiguo → más nuevo

    # 🏆 Mejor día (récord)
    if historico:
        record = max(historico, key=lambda x: x["cerradas"])
        record_val = record["cerradas"]
        record_fecha = record["fecha"]
    else:
        record_val = 0
        record_fecha = None


        # 📋 Subtareas cerradas hoy (lista detallada)
    cur.execute("""
        SELECT s.nombre_subtarea, p.nombre AS nombre_proyecto
        FROM subtasks s
        JOIN projects p ON p.id = s.project_id
        WHERE s.cerrado = 1 AND DATE(s.fecha_cierre) = DATE(?)
        ORDER BY s.fecha_cierre DESC;
    """, (hoy,))
    subtareas_lista = [dict(r) for r in cur.fetchall()]


    return render_template(
        "resumen_dia.html",
        hoy=hoy,
        subtareas_cerradas=subtareas_cerradas,
        horas_totales=horas_totales,
        proyectos=proyectos,
        score_prom=score_prom,
        historico=historico,
        record_val=record_val,
        record_fecha=record_fecha,
        subtareas_lista=subtareas_lista,  # 👈 aquí
    )

