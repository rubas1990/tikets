# models/time_traking.py
from datetime import datetime
import pytz
from .db import get_db

def registrar_inicio_trabajo(app, project_id):
    """Registra el inicio de un periodo de trabajo en un proyecto.
       Si hay un periodo abierto (sin 'fin'), lo cierra antes de abrir uno nuevo."""
    tz = pytz.timezone("America/Monterrey")
    now = datetime.now(tz).isoformat()
    db = get_db(app)
    cur = db.cursor()

    # 🔹 Cierra cualquier sesión abierta sin fin (por seguridad)
    cur.execute("""
        UPDATE project_tiempo
        SET fin = ?, duracion_horas = (julianday(?) - julianday(inicio)) * 24
        WHERE project_id = ? AND fin IS NULL;
    """, (now, now, project_id))

    # 🔹 Inicia nuevo periodo
    cur.execute("""
        INSERT INTO project_tiempo (project_id, inicio)
        VALUES (?, ?);
    """, (project_id, now))
    db.commit()


def registrar_fin_trabajo(app, project_id):
    """Cierra el periodo de trabajo más reciente (si no tiene 'fin')."""
    tz = pytz.timezone("America/Monterrey")
    now = datetime.now(tz)
    db = get_db(app)
    cur = db.cursor()

    # Busca el último registro sin cierre
    cur.execute("""
        SELECT id, inicio
        FROM project_tiempo
        WHERE project_id = ? AND fin IS NULL
        ORDER BY inicio DESC LIMIT 1;
    """, (project_id,))
    row = cur.fetchone()

    if not row:
        return  # Nada que cerrar

    inicio = datetime.fromisoformat(row['inicio'])
    duracion = (now - inicio).total_seconds() / 3600.0

    # Actualiza el registro
    cur.execute("""
        UPDATE project_tiempo
        SET fin = ?, duracion_horas = ?
        WHERE id = ?;
    """, (now.isoformat(), round(duracion, 2), row['id']))
    db.commit()


def auto_detener_proyectos_fuera_de_horario(app):
    """Detiene automáticamente proyectos 'Trabajando' después del horario laboral."""
    tz = pytz.timezone("America/Monterrey")
    now = datetime.now(tz)

    if now.hour > 17 or (now.hour == 17 and now.minute >= 6):
        db = get_db(app)
        cur = db.cursor()
        cur.execute("SELECT id FROM projects WHERE status='Trabajando';")
        activos = cur.fetchall()

        for p in activos:
            # 🔹 Cierra el registro de tiempo también
            registrar_fin_trabajo(app, p['id'])
            cur.execute("UPDATE projects SET status='Detenido' WHERE id=?;", (p['id'],))
        
        db.commit()




def cerrar_tiempos_subtareas_abiertas(app, project_id):
    """Cierra automáticamente todos los registros de tiempo abiertos de las subtareas
    pertenecientes a un proyecto dado."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    tz = ZoneInfo("America/Monterrey")
    now = datetime.now(tz).isoformat()

    db = get_db(app)
    cur = db.cursor()

    # Busca todas las subtareas del proyecto
    cur.execute("SELECT id FROM subtasks WHERE project_id=?;", (project_id,))
    subtareas = cur.fetchall()

    for s in subtareas:
        sub_id = s["id"]
        # Cierra todos los registros abiertos de esa subtarea
        cur.execute("""
            UPDATE subtask_tiempo
            SET fin=?, duracion_min=(julianday(?) - julianday(inicio)) * 24 * 60
            WHERE subtask_id=? AND fin IS NULL;
        """, (now, now, sub_id))

    db.commit()
