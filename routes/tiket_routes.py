#route: routes/tiket_routes.py
# ==========================================================
# 🎫 RUTAS DE TICKETS (DETALLE, LISTA, COMENTARIOS, TIEMPO)
# ==========================================================
from flask import Blueprint, render_template, request, current_app, flash, redirect, url_for, session
from auth import login_required
from models import get_db
from models.recomendador import recomendar_similares
from models.estado_emocional import evaluar_fatiga_operador
from models.predictor_tiket import analizar_tiket  # 🧠 IA Predictiva


tiket_bp = Blueprint('tiket', __name__)

# ==========================================================
# 🔹 LISTA DE TICKETS
# ==========================================================
@tiket_bp.route('/tiket')
@login_required
def tiket_list():
    """Lista todas las subtareas (tickets) con filtros por estado y proyecto."""
    db = get_db(current_app)
    cur = db.cursor()

    filter_status = request.args.get('filter', 'all')
    project_id = request.args.get('project_id', '')

    # 🔹 Cargar lista de proyectos para el filtro
    cur.execute("SELECT id, nombre, numero_de_queja FROM projects ORDER BY nombre ASC;")
    proyectos = cur.fetchall()

    # 🔹 Consulta base de subtareas
    query = """
        SELECT 
            s.id,
            s.nombre_subtarea,
            s.numero_de_queja,
            s.cerrado,
            s.fecha_apertura,
            s.fecha_cierre,
            s.tiempo_objetivo_horas,
            p.nombre AS proyecto_nombre,
            p.id AS proyecto_id
        FROM subtasks s
        JOIN projects p ON s.project_id = p.id
        WHERE 1=1
    """
    params = []

    if project_id:
        query += " AND p.id = ?"
        params.append(project_id)

    if filter_status == 'open':
        query += " AND s.cerrado = 0"
    elif filter_status == 'closed':
        query += " AND s.cerrado = 1"

    query += " ORDER BY datetime(s.fecha_apertura) DESC;"
    cur.execute(query, params)
    rows = cur.fetchall()

    subtareas = []
    for r in rows:
        s = dict(r)

        # 🔹 Suma total de minutos trabajados por subtarea
        cur.execute("""
            SELECT SUM(CAST(duracion_min AS REAL)) AS total_min
            FROM subtask_tiempo
            WHERE subtask_id = ?;
        """, (s['id'],))
        row_time = cur.fetchone()
        total_min = row_time['total_min'] if row_time and row_time['total_min'] is not None else 0

        # 🔹 Formato mixto: si < 60 muestra minutos, si >= 60 muestra horas y minutos
        if total_min >= 60:
            horas = int(total_min // 60)
            mins = int(total_min % 60)
            s['tiempo'] = f"{horas}h {mins}m"
        else:
            s['tiempo'] = f"{round(total_min, 2)} min"

        # 🔹 Verifica si hay sesión activa (sin fin)
        cur.execute("""
            SELECT COUNT(*) AS activos
            FROM subtask_tiempo
            WHERE subtask_id = ? AND fin IS NULL;
        """, (s['id'],))
        s['trabajando'] = cur.fetchone()['activos'] > 0

        subtareas.append(s)

    # 🔹 Ordenar: primero los que están trabajando (estrella activa)
    subtareas.sort(key=lambda s: not s['trabajando'])

    return render_template(
        'tiket_list.html',
        subtareas=subtareas,
        filter_status=filter_status,
        proyectos=proyectos,
        project_id=int(project_id) if project_id else None
    )


# ==========================================================
# 🔹 DETALLE DEL TICKET
# ==========================================================
@tiket_bp.route('/tikets/<int:subtask_id>')
@login_required
def tiket_detail(subtask_id):
    """Muestra el detalle completo de un ticket con IA, rendimiento, estado emocional y análisis del KR."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    db = get_db(current_app)
    cur = db.cursor()

    # 🔹 Obtener información del ticket
    cur.execute("""
        SELECT 
            s.id,
            s.nombre_subtarea,
            s.numero_de_queja,
            s.cerrado,
            s.fecha_apertura,
            s.fecha_cierre,
            s.comentarios,
            s.tiempo_objetivo_horas,
            s.project_id,
            s.tecnologia,
            p.nombre AS proyecto_nombre,
            p.status AS proyecto_status
        FROM subtasks s
        JOIN projects p ON s.project_id = p.id
        WHERE s.id = ?;
    """, (subtask_id,))
    tiket_row = cur.fetchone()

    if not tiket_row:
        flash("Ticket no encontrado.", "warning")
        return redirect(url_for('tiket.tiket_list'))

    # ✅ Convertir Row → dict
    tiket = dict(tiket_row)
    tiket['tiempo_objetivo_horas'] = tiket.get('tiempo_objetivo_horas') or 0
    tecnologia = tiket.get('tecnologia', 'Otro')

    # 🔹 Calcular total de minutos trabajados
    cur.execute("""
        SELECT SUM(CAST(duracion_min AS REAL)) AS total_min
        FROM subtask_tiempo
        WHERE subtask_id = ?;
    """, (subtask_id,))
    total_min = cur.fetchone()['total_min'] or 0

    # 🔹 Sesión activa
    cur.execute("""
        SELECT inicio FROM subtask_tiempo
        WHERE subtask_id = ? AND fin IS NULL
        ORDER BY inicio DESC LIMIT 1;
    """, (subtask_id,))
    activo = cur.fetchone()
    en_trabajo = activo is not None
    inicio_actual = activo['inicio'] if activo else None

    # 🔹 Historial de sesiones
    cur.execute("""
        SELECT username, inicio, fin, ROUND(duracion_min, 2) AS duracion_min
        FROM subtask_tiempo
        WHERE subtask_id = ?
        ORDER BY inicio DESC;
    """, (subtask_id,))
    sesiones = cur.fetchall()

    # 🧮 Métricas de rendimiento
    tiempo_trabajado = round(total_min / 60, 2)
    tiempo_objetivo = tiket['tiempo_objetivo_horas']
    eficiencia = 0
    avance = 0
    if tiempo_objetivo > 0 and tiempo_trabajado > 0:
        eficiencia = round((tiempo_objetivo / tiempo_trabajado) * 100, 1)
        avance = min(round((tiempo_trabajado / tiempo_objetivo) * 100, 1), 100)

    # 🧠 IA: Recomendaciones + Predicción
    db = get_db(current_app)
    recomendaciones = recomendar_similares(db, subtask_id)


    analisis = analizar_tiket(current_app, tiket['project_id'], subtask_id, session.get("username"))


    # 🧘 Estado emocional del operador
    username = session.get("username")
    estado_emocional = evaluar_fatiga_operador(db, username)

    # ==========================================================
    # 🎯 Checklist dinámico y análisis por KR
    # ==========================================================
    cur.execute("SELECT kr FROM subtasks WHERE id=?;", (subtask_id,))
    row_kr = cur.fetchone()
    kr = row_kr['kr'] if row_kr and row_kr['kr'] else 'Otro'

    # Cargar checklist asociado a ese KR
    cur.execute("""
        SELECT punto 
        FROM checklist_rules
        WHERE LOWER(kr)=LOWER(?)
        ORDER BY orden ASC;
    """, (kr,))
    checklist_items = [r['punto'] for r in cur.fetchall()]

    # ==========================================================
    # 📊 Análisis de KR: frecuencia, promedio, y usos previos
    # ==========================================================
    # Total de usos
    cur.execute("""
        SELECT COUNT(*) AS total_usos
        FROM subtasks
        WHERE LOWER(kr)=LOWER(?);
    """, (kr,))
    total_usos = cur.fetchone()['total_usos']

    # Promedio de duración total (solo cerrados)
    cur.execute("""
        SELECT AVG(total_min) AS promedio_min
        FROM (
            SELECT s.id, SUM(CAST(st.duracion_min AS REAL)) AS total_min
            FROM subtasks s
            LEFT JOIN subtask_tiempo st ON st.subtask_id = s.id
            WHERE LOWER(s.kr)=LOWER(?) AND s.cerrado=1
            GROUP BY s.id
        );
    """, (kr,))
    row_duracion = cur.fetchone()
    promedio_min = round(row_duracion['promedio_min'], 2) if row_duracion and row_duracion['promedio_min'] else 0

    # Promedio de dificultad
    cur.execute("""
        SELECT AVG(CAST(dificultad AS REAL)) AS promedio_dif
        FROM subtasks
        WHERE LOWER(kr)=LOWER(?);
    """, (kr,))
    row_dif = cur.fetchone()
    promedio_dificultad = round(row_dif['promedio_dif'], 1) if row_dif and row_dif['promedio_dif'] else None

    # 🔹 Lista detallada de otros tickets que usan este KR
    cur.execute("""
        SELECT 
            s.id, s.nombre_subtarea, s.numero_de_queja, s.tecnologia,
            s.cerrado, s.fecha_cierre,
            ROUND(SUM(CAST(st.duracion_min AS REAL)), 2) AS total_min
        FROM subtasks s
        LEFT JOIN subtask_tiempo st ON st.subtask_id = s.id
        WHERE LOWER(s.kr)=LOWER(?) 
        GROUP BY s.id
        ORDER BY s.fecha_apertura DESC;
    """, (kr,))
    usos_previos = cur.fetchall()

    # ==========================================================
    # 🧩 Información del KR desde tabla okr_kr
    # ==========================================================
    cur.execute("""
        SELECT categoria, kr, comentarios, kr_resultado, peso
        FROM okr_kr
        WHERE LOWER(kr)=LOWER(?) AND activo=1
        LIMIT 1;
    """, (kr,))
    row_okr = cur.fetchone()

    if row_okr:
        kr_categoria = row_okr['categoria']
        kr_nombre = row_okr['kr']
        kr_comentarios = row_okr['comentarios'] or "Sin comentarios."
        kr_resultado = row_okr['kr_resultado'] or "Sin resultado aún."
        kr_peso = row_okr['peso']
    else:
        kr_categoria = "Sin categoría"
        kr_nombre = kr
        kr_comentarios = "No hay información registrada en OKR."
        kr_resultado = "Sin resultado aún."
        kr_peso = 1

    # ==========================================================
    # 🖥️ Renderizado final
    # ==========================================================
    return render_template(
        'tikets_detail.html',
        tiket=tiket,
        sesiones=sesiones,
        tiempo_trabajado=tiempo_trabajado,
        tiempo_objetivo=tiempo_objetivo,
        eficiencia=eficiencia,
        avance=avance,
        en_trabajo=en_trabajo,
        inicio_actual=inicio_actual,
        total_min=total_min,
        recomendaciones=recomendaciones,
        analisis=analisis,
        estado_emocional=estado_emocional,
        checklist_items=checklist_items,
        tecnologia=tecnologia,
        total_usos=total_usos,
        promedio_min=promedio_min,
        promedio_dificultad=promedio_dificultad,
        kr_nombre=kr_nombre,
        kr_categoria=kr_categoria,
        kr_comentarios=kr_comentarios,
        kr_resultado=kr_resultado,
        kr_peso=kr_peso,
        usos_previos=usos_previos
    )




# ==========================================================
# 🔹 INICIAR / DETENER TIEMPO
# ==========================================================
@tiket_bp.route('/subtask/<int:subtask_id>/timer_toggle', methods=['POST'])
@login_required
def subtask_timer_toggle(subtask_id):
    """Inicia o detiene el tiempo de trabajo en un ticket."""
    from models.subtasks import iniciar_tiempo_subtarea, detener_tiempo_subtarea, esta_trabajando_en_subtarea

    db = get_db(current_app)
    username = session.get('username') or 'user'

    trabajando = esta_trabajando_en_subtarea(current_app, subtask_id, username)

    if trabajando:
        detener_tiempo_subtarea(current_app, subtask_id, username)
        flash("⏸ Tiempo detenido para este ticket.", "info")
    else:
        iniciar_tiempo_subtarea(current_app, subtask_id, username)
        flash("▶️ Tiempo iniciado para este ticket.", "success")

    return redirect(url_for('tiket.tiket_detail', subtask_id=subtask_id))


# ==========================================================
# 🔹 AGREGAR COMENTARIOS
# ==========================================================
@tiket_bp.route('/subtask/<int:subtask_id>/comment', methods=['POST'])
@login_required
def subtask_comment_add(subtask_id):
    """Agrega o concatena un comentario dentro del ticket."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    comentario = request.form.get('comentario', '').strip()
    if not comentario:
        flash("⚠️ No puedes enviar un comentario vacío.", "warning")
        return redirect(request.referrer)

    username = session.get('username') or session.get('correo') or 'user'

    db = get_db(current_app)
    cur = db.cursor()

    # 🔹 Obtener comentarios previos
    cur.execute("SELECT comentarios FROM subtasks WHERE id=?;", (subtask_id,))
    row = cur.fetchone()
    prev = row['comentarios'] if row and row['comentarios'] else ""

    now_str = datetime.now(ZoneInfo("America/Monterrey")).strftime("%d/%m/%Y %I:%M %p")
    nuevo = prev + f"\n[{now_str}] {username}: {comentario}"

    cur.execute("UPDATE subtasks SET comentarios=? WHERE id=?;", (nuevo, subtask_id))
    db.commit()

    flash("💬 Comentario agregado correctamente.", "success")
    return redirect(url_for('tiket.tiket_detail', subtask_id=subtask_id))
