# routes/main_routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_from_directory
from auth import login_required, role_required
from models import get_projects, project_progress, create_user, get_db
from datetime import datetime, date
import pytz
from models.normalize_subtasks import asignar_categorias, categorizar_subtarea
from flask import Response
import json

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
@login_required
def index():
    tz = pytz.timezone("America/Monterrey")
    now = datetime.now(tz)
    today = date.today()

    db = get_db(current_app)
    cur = db.cursor()

    last_auto_stop = current_app.config.get("last_auto_stop_date")

    # 🔹 Auto-stop diario (igual que antes ✅)
    if (now.hour > 17 or (now.hour == 17 and now.minute >= 6)) and last_auto_stop != today:
        cur.execute("SELECT COUNT(*) AS activos FROM projects WHERE status='Trabajando';")
        activos = cur.fetchone()['activos']
        if activos > 0:
            cur.execute("UPDATE projects SET status='Detenido' WHERE status='Trabajando';")
            db.commit()
            flash(f"Se cambiaron automáticamente {activos} proyecto(s) a 'Detenido'.", "info")
        current_app.config["last_auto_stop_date"] = today

    # ================================================
    # 🥷 DISCIPLINA SAMURÁI CORPORATIVA - SILENCIOSA 🤫
    # ================================================
    avisos = []

    # ✅ Regla 1: Subtareas abiertas más de 7 días
    cur.execute("""
        SELECT id, nombre_subtarea, fecha_apertura
        FROM subtasks
        WHERE cerrado = 0;
    """)
    abiertas = cur.fetchall()

    for s in abiertas:
        if s["fecha_apertura"]:
            fecha_ini = datetime.fromisoformat(s["fecha_apertura"]).date()
            dias = (today - fecha_ini).days
            if dias >= 7:
                avisos.append(f"⚠️ '{s['nombre_subtarea']}' lleva {dias} días abierta.")

    # ✅ Regla 2: Sin tiempo registrado en 3 días
    cur.execute("""
        SELECT s.id, s.nombre_subtarea,
               MAX(t.inicio) AS ultimo_inicio
        FROM subtasks s
        LEFT JOIN subtask_tiempo t ON t.subtask_id = s.id
        WHERE s.cerrado = 0
        GROUP BY s.id;
    """)
    tiempos = cur.fetchall()

    for t in tiempos:
        if t["ultimo_inicio"]:
            ultima = datetime.fromisoformat(t["ultimo_inicio"]).date()
            dias = (today - ultima).days
            if dias >= 3:
                avisos.append(f"🚨 '{t['nombre_subtarea']}' sin progreso {dias} días.")

    # ✅ Guardar SOLO notificaciones, sin flash()
    if avisos:
        cur.executemany(
            "INSERT INTO notifications (mensaje, fecha) VALUES (?, ?)",
            [(a, now.isoformat()) for a in avisos]
        )
        db.commit()

    # ================================================

    # 🔹 Filtro de búsqueda de proyectos
    query = request.args.get('q', '').strip().lower()
    projs = get_projects(current_app)
    if query:
        projs = [
            p for p in projs
            if query in p['nombre'].lower()
            or query in p['numero_de_queja'].lower()
            or query in p['sitio'].lower()
        ]

    enriched = [(p, project_progress(current_app, p['id'])) for p in projs]
    return render_template('index.html', projects=enriched, query=query)


@main_bp.route('/users/new', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def user_new():
    """Formulario para crear un nuevo usuario (solo admin)."""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        role = request.form.get('role', 'user')

        if not username or not password:
            flash("Usuario y contraseña son obligatorios.", "warning")
            return render_template('user_form.html')

        ok = create_user(current_app, username, password, role)
        if ok:
            flash("Usuario creado correctamente.", "success")
            return redirect(url_for('main.index'))
        else:
            flash("El nombre de usuario ya existe.", "danger")
    return render_template('user_form.html')




@main_bp.route('/estado_general')
@login_required
def estado_general():
    """Muestra un resumen rápido de proyectos activos, subtareas y estado de hidratación."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from flask import session

    tz = ZoneInfo("America/Monterrey")
    now = datetime.now(tz)

    db = get_db(current_app)
    cur = db.cursor()

    # =====================================================
    # 🔹 1. Proyectos activos
    # =====================================================
    cur.execute("""
        SELECT id, nombre, numero_de_queja
        FROM projects
        WHERE status='Trabajando';
    """)
    proyectos_activos = cur.fetchall()

    # =====================================================
    # 🔹 2. Subtareas con tiempo en curso
    # =====================================================
    cur.execute("""
        SELECT s.id, s.nombre_subtarea, s.numero_de_queja,
               p.nombre AS proyecto, t.username, t.inicio
        FROM subtask_tiempo t
        JOIN subtasks s ON s.id = t.subtask_id
        JOIN projects p ON p.id = s.project_id
        WHERE t.fin IS NULL
        ORDER BY datetime(t.inicio) ASC;
    """)
    subtareas_activas = cur.fetchall()

    # =====================================================
    # 🔹 3. Verificar tareas corriendo
    # =====================================================
    cur.execute("""
        SELECT COUNT(*) AS en_trabajo
        FROM subtask_tiempo
        WHERE inicio IS NOT NULL
          AND fin IS NULL;
    """)
    t = cur.fetchone()
    hay_tareas_corriendo = t['en_trabajo'] > 0

    # =====================================================
    # 🔹 4. Resumen rápido
    # =====================================================
    num_proyectos = len(proyectos_activos)
    num_subtareas = len(subtareas_activas)

    if num_proyectos == 0 and num_subtareas == 0:
        flash("✅ No hay proyectos ni subtareas abiertas actualmente.", "success")
    else:
        msg = []
        if num_proyectos > 0:
            msg.append(f"{num_proyectos} proyecto(s) activos.")
        if num_subtareas > 0:
            msg.append(f"{num_subtareas} subtarea(s) con tiempo en curso.")
        flash("⚠️ " + " ".join(msg), "warning")

    if hay_tareas_corriendo:
        flash("⏱️ Hay al menos una subtarea trabajando actualmente.", "info")

    # =====================================================
    # 💧 5. Estado de hidratación diaria
    # =====================================================
    username = session.get('username', '').strip()

    cur.execute("""
        SELECT cantidad_actual, objetivo, fecha
        FROM agua_diaria
        WHERE usuario = ?
        ORDER BY datetime(fecha) DESC
        LIMIT 1;
    """, (username,))
    agua = cur.fetchone()

    if agua:
        progreso = min(agua['cantidad_actual'] / agua['objetivo'], 1.0)
        porcentaje = round(progreso * 100)
    else:
        progreso = 0
        porcentaje = 0
        agua = {'cantidad_actual': 0, 'objetivo': 6, 'fecha': None}



    # =====================================================
    # 📈 6. Historial de agua (últimos 5 días)
    # =====================================================
    cur.execute("""
        SELECT fecha, cantidad_actual, objetivo
        FROM agua_diaria
        WHERE usuario = ?
        ORDER BY date(fecha) DESC
        LIMIT 5;
    """, (username,))
    historial = cur.fetchall()

    # Convertir y formatear para Chart.js
    fechas = []
    progreso_dias = []
    for h in reversed(historial):  # para que salgan del más antiguo al más reciente
        fechas.append(h['fecha'])
        progreso = round((h['cantidad_actual'] / h['objetivo']) * 100, 1) if h['objetivo'] else 0
        progreso_dias.append(progreso)
 
    # =====================================================
    # 🔹 Render final
    # =====================================================
    ahora = datetime.now(tz).isoformat()
    return render_template(
        "estado_general.html",
        proyectos_activos=proyectos_activos,
        subtareas_activas=subtareas_activas,
        ahora=ahora,
        hay_tareas_corriendo=hay_tareas_corriendo,
        agua=agua,
        porcentaje=porcentaje,
        fechas=fechas,
        progreso_dias=progreso_dias
    )






@main_bp.route('/service-worker.js')
def service_worker():
    """Entrega el service worker para modo app."""
    return send_from_directory(current_app.static_folder, 'service-worker.js')



@main_bp.route("/admin/categorizar")
def recategorizar_subtareas():
    """
    Reanaliza y actualiza la categoría de todas las subtareas,
    normalizando los nombres al formato oficial.
    """
  # asegúrate que esté importado

    db = get_db(current_app)
    cur = db.cursor()

    # 🔹 Mapeo de normalización oficial
    normalizacion = {
        "plc / control": "Control / automatización",
        "control / automatización": "Control / automatización",

        "cambio / ajuste": "Desarrollo / ajustes",
        "agregar / base de datos": "Desarrollo / ajustes",
        "interfaz / visualización": "Desarrollo / ajustes",
        "desarrollo / ajustes": "Desarrollo / ajustes",

        "documentos / reportes": "Reportes / documentos",
        "reportes / documentos": "Reportes / documentos",

        "comunicación / alertas": "Comunicación / usuarios",
        "usuarios / formularios": "Comunicación / usuarios",
        "comunicación / usuarios": "Comunicación / usuarios",

        "cámaras / visión": "Visión / imágenes",
        "visión / imágenes": "Visión / imágenes",

        "mantenimiento / falla": "Mantenimiento / falla",
    }

    cur.execute("SELECT id, nombre_subtarea FROM subtasks;")
    rows = cur.fetchall()
    total = 0

    for r in rows:
        categoria_detectada = categorizar_subtarea(r["nombre_subtarea"]) or "Sin categoría"

        # 🧩 Normalizar antes de guardar
        categoria_final = normalizacion.get(categoria_detectada.lower().strip(), categoria_detectada)

        cur.execute("UPDATE subtasks SET categoria=? WHERE id=?;", (categoria_final, r["id"]))
        total += 1

    db.commit()
    flash(f"✅ {total} subtareas recategorizadas automáticamente con formato oficial.", "success")
    return redirect(url_for('dashboard.dashboard'))




@main_bp.route("/admin/categorias", methods=["GET", "POST"])
def tabla_categorias():
    """Muestra y permite editar nombre_subtarea y categoria, y carga reglas dinámicamente."""
    db = get_db(current_app)
    cur = db.cursor()

    # 🔹 Actualización manual de nombre o categoría
    if request.method == "POST":
        subtask_id = request.form.get("id")
        nuevo_nombre = request.form.get("nombre_subtarea", "").strip()
        nueva_categoria = request.form.get("categoria", "").strip()

        if subtask_id:
            cur.execute("""
                UPDATE subtasks
                SET nombre_subtarea = ?, categoria = ?
                WHERE id = ?;
            """, (nuevo_nombre, nueva_categoria, subtask_id))
            db.commit()
            flash(f"✅ Subtarea {subtask_id} actualizada correctamente.", "success")

    # 🔹 Obtener todas las subtareas
    cur.execute("""
        SELECT id, nombre_subtarea, categoria
        FROM subtasks
        ORDER BY id DESC;
    """)
    subtareas = cur.fetchall()

    # 🔹 Obtener lista única de categorías existentes
    cur.execute("""
        SELECT DISTINCT categoria
        FROM subtasks
        WHERE categoria IS NOT NULL AND categoria <> '';
    """)
    categorias_existentes = sorted([r["categoria"] for r in cur.fetchall()])

    # 🔹 Cargar reglas de la tabla categoria_reglas
    cur.execute("""
        SELECT categoria, GROUP_CONCAT(palabra, ', ') AS palabras, COUNT(*) AS total
        FROM categoria_reglas
        GROUP BY categoria
        ORDER BY categoria;
    """)
    reglas = cur.fetchall()

    return render_template("admin_categorias.html",
                           subtareas=subtareas,
                           categorias_existentes=categorias_existentes,
                           reglas=reglas)



@main_bp.route("/ajustes")
def ajustes():
    """Página de ajustes con accesos rápidos a funciones administrativas."""
    return render_template("ajustes.html")



@main_bp.route("/admin/categoria-reglas", methods=["GET", "POST"])
def categoria_reglas_admin():
    """
    Vista administrativa para gestionar las reglas de categorización.
    Limpia y normaliza automáticamente las categorías para evitar duplicados.
    """
    db = get_db(current_app)
    cur = db.cursor()

    # ============================================================
    # 🔹 Agregar nueva palabra
    # ============================================================
    if request.method == "POST":
        palabra = request.form.get("palabra", "").strip().lower()
        categoria = request.form.get("categoria", "").strip().lower()

        # 🔧 Normalizar categoría
        categoria = categoria.replace("  ", " ").replace("/", " / ").strip()
        categoria = " / ".join([p.capitalize().strip() for p in categoria.split("/")])

        if palabra and categoria:
            cur.execute("SELECT COUNT(*) AS c FROM categoria_reglas WHERE palabra = ?;", (palabra,))
            if cur.fetchone()["c"] > 0:
                flash(f"⚠️ La palabra '{palabra}' ya existe.", "warning")
            else:
                cur.execute(
                    "INSERT INTO categoria_reglas (palabra, categoria) VALUES (?, ?);",
                    (palabra, categoria)
                )
                db.commit()
                flash(f"✅ Palabra '{palabra}' agregada correctamente en '{categoria}'.", "success")
        else:
            flash("❌ Debes ingresar una palabra y su categoría.", "danger")

        return redirect(url_for("main.categoria_reglas_admin"))

    # ============================================================
    # 🔹 Eliminar palabra
    # ============================================================
    eliminar_id = request.args.get("delete")
    if eliminar_id:
        cur.execute("DELETE FROM categoria_reglas WHERE id = ?;", (eliminar_id,))
        db.commit()
        flash("🗑️ Palabra eliminada correctamente.", "info")
        return redirect(url_for("main.categoria_reglas_admin"))

    # ============================================================
    # 🧹 LIMPIAR CATEGORÍAS (más riguroso)
    # ============================================================
    cur.execute("SELECT id, categoria FROM categoria_reglas;")
    filas = cur.fetchall()
    for f in filas:
        cat = (f["categoria"] or "").strip().lower()
        if not cat:
            continue

        # Normalización más estricta
        cat = cat.replace("  ", " ").replace(" /", "/").replace("/ ", "/")
        cat = cat.replace("/", " / ").strip()
        cat = " / ".join([p.capitalize().strip() for p in cat.split("/")])

        # 🔹 Actualizar si cambió
        cur.execute("UPDATE categoria_reglas SET categoria = ? WHERE id = ?;", (cat, f["id"]))
    db.commit()

    # ============================================================
    # 🔹 Obtener categorías únicas
    # ============================================================
    cur.execute("""
        SELECT DISTINCT categoria
        FROM categoria_reglas
        WHERE categoria IS NOT NULL AND categoria != ''
        ORDER BY LOWER(categoria);
    """)
    categorias_existentes = sorted(set([r["categoria"].strip() for r in cur.fetchall()]))

    # ============================================================
    # 🔹 Aplicar filtro
    # ============================================================
    categoria_filtro = request.args.get("categoria")
    if categoria_filtro and categoria_filtro != "Todas":
        cur.execute("""
            SELECT id, palabra, categoria
            FROM categoria_reglas
            WHERE categoria = ?
            ORDER BY palabra;
        """, (categoria_filtro,))
    else:
        cur.execute("""
            SELECT id, palabra, categoria
            FROM categoria_reglas
            ORDER BY categoria, palabra;
        """)
    reglas = cur.fetchall()

    # ============================================================
    # 🔹 Render final
    # ============================================================
    return render_template(
        "admin_categoria_reglas.html",
        reglas=reglas,
        categorias_existentes=categorias_existentes,
        categoria_filtro=categoria_filtro
    )






@main_bp.route("/admin/unificar-categorias")
def unificar_categorias():
    db = get_db(current_app)
    cur = db.cursor()

    mapeo = {
        "Plc / control": "Control / automatización",
        "Cambio / ajuste": "Desarrollo / ajustes",
        "Agregar / base de datos": "Desarrollo / ajustes",
        "Interfaz / visualización": "Desarrollo / ajustes",
        "Documentos / reportes": "Reportes / documentos",
        "Comunicación / alertas": "Comunicación / usuarios",
        "Usuarios / formularios": "Comunicación / usuarios",
        "Cámaras / visión": "Visión / imágenes",
        "Mantenimiento / falla": "Mantenimiento / falla",
    }

    for viejo, nuevo in mapeo.items():
        cur.execute("UPDATE categoria_reglas SET categoria = ? WHERE categoria = ?;", (nuevo, viejo))

    # 🔹 Eliminar duplicados exactos
    cur.execute("""
        DELETE FROM categoria_reglas
        WHERE rowid NOT IN (
            SELECT MIN(rowid)
            FROM categoria_reglas
            GROUP BY palabra
        );
    """)
    db.commit()

    flash("✅ Categorías unificadas correctamente.", "success")
    return redirect(url_for("main.categoria_reglas_admin"))




@main_bp.route("/admin/unificar-subtasks")
def unificar_subtasks():
    """Normaliza todas las categorías de subtareas al nuevo estándar."""
    db = get_db(current_app)
    cur = db.cursor()

    mapeo = {
        "plc / control": "Control / automatización",
        "control / automatización": "Control / automatización",

        "cambio / ajuste": "Desarrollo / ajustes",
        "agregar / base de datos": "Desarrollo / ajustes",
        "interfaz / visualización": "Desarrollo / ajustes",
        "desarrollo / ajustes": "Desarrollo / ajustes",

        "documentos / reportes": "Reportes / documentos",
        "reportes / documentos": "Reportes / documentos",

        "comunicación / alertas": "Comunicación / usuarios",
        "usuarios / formularios": "Comunicación / usuarios",
        "comunicación / usuarios": "Comunicación / usuarios",

        "cámaras / visión": "Visión / imágenes",
        "visión / imágenes": "Visión / imágenes",

        "mantenimiento / falla": "Mantenimiento / falla",
    }

    for viejo, nuevo in mapeo.items():
        cur.execute("UPDATE subtasks SET categoria = ? WHERE LOWER(categoria) = ?;", (nuevo, viejo.lower()))

    db.commit()
    flash("✅ Categorías de subtareas unificadas correctamente.", "success")
    return redirect(url_for("dashboard.dashboard"))





@main_bp.route("/notificaciones")
@login_required
def notificaciones_view():
    db = get_db(current_app)
    cur = db.cursor()

    cur.execute("SELECT * FROM notifications ORDER BY datetime(fecha) DESC")
    notis = cur.fetchall()

    # Marcar todas como vistas
    cur.execute("UPDATE notifications SET visto = 1 WHERE visto = 0")
    db.commit()

    return render_template("notificaciones.html", notificaciones=notis)



@main_bp.route("/api/notificaciones_pendientes")
@login_required
def notis_pendientes():
    db = get_db(current_app)
    cur = db.cursor()
    cur.execute("SELECT COUNT(*) AS c FROM notifications WHERE visto = 0")
    c = cur.fetchone()["c"]
    return {"pendientes": c}






from flask import Blueprint, jsonify, current_app
from auth import login_required
from models.db import get_db

growth_bp = Blueprint('growth', __name__, url_prefix="/growth")


@growth_bp.route("/notifs")
@login_required
def growth_notifs():
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


@main_bp.route("/notifs/marcar_vistas")
@login_required
def marcar_vistas():
    db = get_db(current_app)
    cur = db.cursor()
    cur.execute("""
        UPDATE notifications
        SET visto = 1;
    """)
    db.commit()
    return jsonify({"status": "ok"})



@main_bp.route("/api/estado_actual")
@login_required
def estado_actual():
    from flask import session, jsonify
    username = session.get("username")
    db = get_db(current_app)
    cur = db.cursor()

    # 🔹 Buscar actividad actual del día (la que está en curso según la hora)
    cur.execute("""
        SELECT actividad, tipo, hora_inicio, hora_fin
        FROM daily_schedule
        WHERE username = ?
          AND date('now', 'localtime') = date('now', 'localtime')
        ORDER BY hora_inicio DESC;
    """, (username,))
    rows = cur.fetchall()

    if not rows:
        return jsonify({"estado": "Sin actividad"})

    from datetime import datetime
    import pytz
    tz = pytz.timezone("America/Monterrey")
    now = datetime.now(tz)
    hora_actual = now.strftime("%H:%M")

    # 🔍 Encontrar cuál bloque está activo
    actividad_actual = None
    for r in rows:
        if r["hora_inicio"] <= hora_actual < r["hora_fin"]:
            actividad_actual = r
            break

    if actividad_actual:
        return Response(
    json.dumps({
        "tarea": actividad_actual["actividad"],
        "tipo": actividad_actual["tipo"] or "General",
        "hora_inicio": actividad_actual["hora_inicio"],
        "hora_fin": actividad_actual["hora_fin"],
        "estado": "Trabajando"
    }, ensure_ascii=False),
    content_type="application/json; charset=utf-8"
)

    else:
        return Response(
            json.dumps({"estado": "Sin actividad"}, ensure_ascii=False),
            content_type="application/json; charset=utf-8"
        )




@main_bp.route("/api/crear_paquete/<int:paquete_id>/<int:project_id>")
@login_required
def crear_paquete(paquete_id, project_id):
    """Copia todas las subtareas base de un paquete a la tabla subtasks real."""
    from flask import session
    db = get_db(current_app)
    cur = db.cursor()

    cur.execute("SELECT numero_de_queja FROM projects WHERE id = ?;", (project_id,))
    proyecto = cur.fetchone()
    if not proyecto:
        flash("❌ Proyecto no encontrado.", "danger")
        return redirect(url_for("main.index"))

    numero_queja = proyecto["numero_de_queja"]
    fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cur.execute("""
        SELECT nombre_subtarea, categoria, prioridad, tecnologia, dificultad,
               tiempo_objetivo_horas, comentarios, aprendizaje, kr
        FROM paquete_subtareas_detalle
        WHERE paquete_id = ?;
    """, (paquete_id,))
    filas = cur.fetchall()

    if not filas:
        flash("⚠️ Este paquete no tiene subtareas definidas.", "warning")
        return redirect(url_for("project.project_detail", project_id=project_id))

    for f in filas:
        cur.execute("""
            INSERT INTO subtasks (
                project_id, numero_de_queja, nombre_subtarea, cerrado,
                fecha_apertura, comentarios, tiempo_objetivo_horas,
                prioridad, tiempo_objetivo, categoria, aprendizaje,
                dificultad, tecnologia, kr
            )
            VALUES (?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            project_id, numero_queja, f["nombre_subtarea"], fecha_actual,
            f["comentarios"], f["tiempo_objetivo_horas"], f["prioridad"], 0,
            f["categoria"], f["aprendizaje"], f["dificultad"], f["tecnologia"], f["kr"]
        ))

    db.commit()
    flash(f"✅ Se aplicó el paquete con {len(filas)} subtareas base al proyecto.", "success")
    return redirect(url_for("project.project_detail", project_id=project_id))



@main_bp.route("/paquetes_disponibles/<int:project_id>")
@login_required
def paquetes_disponibles(project_id):
    """Muestra los paquetes disponibles desde la BD, dinámicamente."""
    db = get_db(current_app)
    cur = db.cursor()

    cur.execute("SELECT id, nombre, descripcion FROM paquete_subtareas ORDER BY id;")
    paquetes = cur.fetchall()

    return render_template("paquetes_modal.html", paquetes=paquetes, project_id=project_id)
