from datetime import datetime
from zoneinfo import ZoneInfo
from .db import get_db

def create_project(app, data):
    db = get_db(app)
    cur = db.cursor()

    fecha_local = datetime.now(ZoneInfo("America/Monterrey"))
    year = fecha_local.strftime("%y")   # 25
    month = fecha_local.strftime("%m")  # 10
    prefix = "CONT"

    # 🔹 Generar consecutivo (busca el último del mismo mes/año)
    cur.execute("""
        SELECT numero_de_queja 
        FROM projects 
        WHERE numero_de_queja LIKE ? 
        ORDER BY id DESC LIMIT 1;
    """, (f"{prefix}-{year}-{month}-%",))
    last = cur.fetchone()

    if last:
        # Extraer número consecutivo del formato CONT-25-10-003 → 003
        last_num = int(last['numero_de_queja'].split('-')[-1])
        next_num = last_num + 1
    else:
        next_num = 1

    consecutivo = f"{next_num:03d}"
    numero_generado = f"{prefix}-{year}-{month}-{consecutivo}"

    # 🔹 Insertar nuevo proyecto con número generado
    cur.execute("""
        INSERT INTO projects (nombre, numero_de_queja, sitio, prioridad, status,
                              fecha_apertura, comentarios, ahorro, gasto)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (data['nombre'], numero_generado, data['sitio'],
          data['prioridad'], data['status'],
          fecha_local.isoformat(), data['comentarios'],
          data['ahorro'], data['gasto']))
    db.commit()
    return cur.lastrowid


def update_project(app, project_id, data):
    db = get_db(app)
    cur = db.cursor()

    nuevo_status = data.get('status')

    # ✅ Si el proyecto se marcará como TRABAJANDO => detener otros antes
    if nuevo_status == "Trabajando":
        # Buscar proyectos trabajando del mismo usuario (cuando agreguemos username)
        cur.execute("""
            SELECT id FROM projects 
            WHERE status='Trabajando' AND id != ?;
        """, (project_id,))
        trabajando = cur.fetchall()

        # Si había otros trabajando → detenerlos
        if trabajando:
            ids_a_detener = [str(p['id']) for p in trabajando]
            lista_ids = ",".join(ids_a_detener)

            print(f"[info] Deteniendo proyectos activos previos: {lista_ids}")

            cur.execute(f"""
                UPDATE projects SET status='Detenido'
                WHERE id IN ({lista_ids});
            """)

    # ✅ Si se cierra, guardamos fecha de cierre
    if nuevo_status == 'Cerrado':
        now_iso = datetime.now(ZoneInfo("America/Monterrey")).isoformat()
        cur.execute("""
            UPDATE projects
            SET nombre=?, sitio=?, prioridad=?, status=?, comentarios=?, ahorro=?, gasto=?, 
                fecha_cierre=COALESCE(fecha_cierre, ?)
            WHERE id=?
        """, (data['nombre'], data['sitio'], data['prioridad'], nuevo_status,
              data['comentarios'], data['ahorro'], data['gasto'], now_iso, project_id))

    else:
        # Actualización simple
        cur.execute("""
            UPDATE projects
            SET nombre=?, sitio=?, prioridad=?, status=?, comentarios=?, ahorro=?, gasto=?
            WHERE id=?
        """, (data['nombre'], data['sitio'], data['prioridad'], nuevo_status,
              data['comentarios'], data['ahorro'], data['gasto'], project_id))

    db.commit()





def get_projects(app):
    db = get_db(app)
    cur = db.cursor()
    cur.execute("SELECT * FROM projects ORDER BY fecha_apertura DESC;")
    return cur.fetchall()






def get_project(app, project_id):
    db = get_db(app)
    cur = db.cursor()
    cur.execute("SELECT * FROM projects WHERE id=?;", (project_id,))
    return cur.fetchone()






def get_project_by_queja(app, numero_de_queja):
    db = get_db(app)
    cur = db.cursor()
    cur.execute("SELECT * FROM projects WHERE numero_de_queja=?;", (numero_de_queja,))
    return cur.fetchone()





def append_project_comment(app, project_id, username, comment_text):
    db = get_db(app)
    cur = db.cursor()
    cur.execute("SELECT comentarios FROM projects WHERE id=?;", (project_id,))
    prev = cur.fetchone()['comentarios'] or ''
    ts = datetime.utcnow().isoformat()
    new_block = f"[{ts}] {username}: {comment_text}\n"
    cur.execute("UPDATE projects SET comentarios=? WHERE id=?;", (prev + new_block, project_id))
    db.commit()
