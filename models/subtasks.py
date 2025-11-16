#route: models/subtasks.py
from datetime import datetime
from zoneinfo import ZoneInfo
from .db import get_db
from models.normalize_subtasks import categorizar_subtarea

def get_subtasks_for_project(app, project_id, filter_status='all'):
    db = get_db(app)
    cur = db.cursor()
    query = "SELECT * FROM subtasks WHERE project_id=?"
    params = [project_id]
    if filter_status == 'open':
        query += " AND cerrado=0"
    elif filter_status == 'closed':
        query += " AND cerrado=1"
    query += " ORDER BY id ASC;"
    cur.execute(query, params)
    return cur.fetchall()

def create_subtask(app, project_id, nombre_subtarea, tiempo_objetivo_horas=8.0):
    """
    Crea una nueva subtarea (ticket) asignando un tiempo objetivo en horas
    y clasificando automáticamente la categoría según el texto.
    """
    db = get_db(app)
    cur = db.cursor()

    # 🔹 Obtener número base del proyecto
    cur.execute("SELECT numero_de_queja FROM projects WHERE id=?;", (project_id,))
    proj = cur.fetchone()
    if not proj:
        return None

    base = proj['numero_de_queja']

    # 🔹 Generar número de secuencia incremental
    cur.execute("SELECT COUNT(*) AS c FROM subtasks WHERE project_id=?;", (project_id,))
    seq = cur.fetchone()['c'] + 1
    sub_q = f"{base}-{seq}"

    # 🔹 Clasificar categoría automáticamente
    categoria = categorizar_subtarea(nombre_subtarea)

    # 🔹 Fecha de apertura actual
    now_iso = datetime.now(ZoneInfo("America/Monterrey")).isoformat()

    # 🔹 Insertar nueva subtarea con categoría detectada
    cur.execute("""
        INSERT INTO subtasks (
            project_id, numero_de_queja, nombre_subtarea, categoria,
            cerrado, fecha_apertura, tiempo_objetivo_horas
        )
        VALUES (?, ?, ?, ?, 0, ?, ?)
    """, (project_id, sub_q, nombre_subtarea, categoria, now_iso, tiempo_objetivo_horas))

    db.commit()
    print(f"🧩 Nueva subtarea creada: {sub_q} | Categoría: {categoria}")
    return cur.lastrowid


def update_subtask_status(app, subtask_id, cerrado_bool):
    db = get_db(app)
    cur = db.cursor()
    if cerrado_bool:
        now_iso = datetime.utcnow().isoformat()
        cur.execute("""
            UPDATE subtasks SET cerrado=1, fecha_cierre=COALESCE(fecha_cierre, ?) WHERE id=?;
        """, (now_iso, subtask_id))
    else:
        cur.execute("UPDATE subtasks SET cerrado=0, fecha_cierre=NULL WHERE id=?;", (subtask_id,))
    db.commit()


def get_subtask(app, subtask_id):
    db = get_db(app)
    cur = db.cursor()
    cur.execute("SELECT * FROM subtasks WHERE id=?;", (subtask_id,))
    return cur.fetchone()



from datetime import datetime
from zoneinfo import ZoneInfo
from .db import get_db


# -----------------------------------------------------------
# Iniciar trabajo en una subtarea
# -----------------------------------------------------------
def iniciar_tiempo_subtarea(app, subtask_id, username):
    db = get_db(app)
    cur = db.cursor()

    # 🔹 Cerrar cualquier otra subtarea activa del usuario
    cur.execute("""
        SELECT id, inicio FROM subtask_tiempo
        WHERE username=? AND fin IS NULL;
    """, (username,))
    activos = cur.fetchall()
    for a in activos:
        fin = datetime.now(ZoneInfo("America/Monterrey"))
        inicio = datetime.fromisoformat(a['inicio'])
        duracion = (fin - inicio).total_seconds() / 60.0
        cur.execute("""
            UPDATE subtask_tiempo
            SET fin=?, duracion_min=?
            WHERE id=?;
        """, (fin.isoformat(), duracion, a['id']))

    # 🔹 Registrar nuevo inicio
    now = datetime.now(ZoneInfo("America/Monterrey")).isoformat()
    cur.execute("""
        INSERT INTO subtask_tiempo (subtask_id, username, inicio)
        VALUES (?, ?, ?);
    """, (subtask_id, username, now))
    db.commit()


# -----------------------------------------------------------
# Detener trabajo en una subtarea
# -----------------------------------------------------------
def detener_tiempo_subtarea(app, subtask_id, username):
    """Detiene el tiempo activo de una subtarea (sin importar quién lo inició)."""
    db = get_db(app)
    cur = db.cursor()

    # 🔹 Buscar el registro activo (aunque sea de otro usuario)
    cur.execute("""
        SELECT id, inicio FROM subtask_tiempo
        WHERE subtask_id=? AND fin IS NULL
        ORDER BY inicio DESC LIMIT 1;
    """, (subtask_id,))
    row = cur.fetchone()

    if not row:
        print(f"[info] No hay sesión activa para subtask_id={subtask_id}.")
        return False

    fin = datetime.now(ZoneInfo("America/Monterrey"))
    inicio = datetime.fromisoformat(row['inicio'])
    duracion = (fin - inicio).total_seconds() / 60.0

    # 🔹 Cierra la sesión (sin filtrar por usuario)
    cur.execute("""
        UPDATE subtask_tiempo
        SET fin=?, duracion_min=?
        WHERE id=?;
    """, (fin.isoformat(), duracion, row['id']))

    db.commit()
    print(f"[ok] Tiempo detenido para subtask_id={subtask_id}, duración={duracion:.2f} min ✅")
    return True


# -----------------------------------------------------------
# Verificar si el usuario está trabajando en una subtarea
# -----------------------------------------------------------
def esta_trabajando_en_subtarea(app, subtask_id, username):
    db = get_db(app)
    cur = db.cursor()
    cur.execute("""
        SELECT COUNT(*) AS c FROM subtask_tiempo
        WHERE subtask_id=? AND username=? AND fin IS NULL;
    """, (subtask_id, username))
    return cur.fetchone()['c'] > 0



def esta_trabajando_en_subtarea(app, subtask_id, username):
    """Devuelve True si el usuario tiene la subtarea activa (sin fin registrado)."""
    db = get_db(app)
    cur = db.cursor()
    cur.execute("""
        SELECT 1
        FROM subtask_tiempo
        WHERE subtask_id=? AND username=? AND fin IS NULL
        LIMIT 1;
    """, (subtask_id, username))
    return cur.fetchone() is not None
