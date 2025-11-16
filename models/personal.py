# models/personal.py
from models.db import get_db
from datetime import datetime
from zoneinfo import ZoneInfo

from models.db import get_db

def get_open_subtasks(app):
    """Devuelve todas las subtareas abiertas (no cerradas) con info del proyecto."""
    db = get_db(app)
    cur = db.cursor()
    cur.execute("""
        SELECT s.id AS subtask_id,
               s.numero_de_queja,
               s.nombre_subtarea,
               p.id AS project_id,
               p.nombre AS proyecto_nombre
        FROM subtasks s
        JOIN projects p ON p.id = s.project_id
        WHERE s.cerrado = 0
        ORDER BY p.nombre, s.id ASC;
    """)
    return cur.fetchall()



def add_personal_task(app, username, tipo, numero_tarea, descripcion, project_id=None):
    """Agrega una tarea personal o de proyecto a la lista diaria."""
    db = get_db(app)
    cur = db.cursor()
    fecha_local = datetime.now(ZoneInfo("America/Monterrey")).date().isoformat()

    cur.execute("""
        INSERT INTO personal_tasks (fecha, tipo, numero_tarea, descripcion, project_id, username)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (fecha_local, tipo, numero_tarea, descripcion, project_id, username))
    db.commit()



def get_user_habits(app, username):
    db = get_db(app)
    cur = db.cursor()
    cur.execute("""
        SELECT id, nombre, posicion, fase, tipo
        FROM habits
        WHERE username = ?
        ORDER BY fase, posicion ASC;
    """, (username,))
    return cur.fetchall()




from datetime import datetime
from models.db import get_db

def get_current_activity(app, username):
    """Devuelve la actividad actual según la hora y usuario."""
    from datetime import datetime
    db = get_db(app)
    cur = db.cursor()

    # Hora local actual (HH:MM)
    from zoneinfo import ZoneInfo
    ahora = datetime.now(ZoneInfo("America/Monterrey")).strftime("%H:%M")

    cur.execute("""
        SELECT actividad, tipo, fase, hora_inicio, hora_fin
        FROM daily_schedule
        WHERE username = ?
          AND hora_inicio <= ?
          AND hora_fin > ?
        LIMIT 1;
    """, (username, ahora, ahora))

    row = cur.fetchone()
    if row:
        return dict(row)
    else:
        return {"actividad": "Sin actividades programadas ahora", "tipo": "", "fase": ""}
