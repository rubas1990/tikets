#routes/project_routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, session
from auth import login_required, role_required
from models import (
    get_project, create_project, update_project,
    get_subtasks_for_project, create_subtask, append_project_comment,
    project_progress, get_db
)
from models.subtasks import (
    iniciar_tiempo_subtarea, detener_tiempo_subtarea, esta_trabajando_en_subtarea
)
from datetime import datetime
import pytz
from models.okr import get_okrs

project_bp = Blueprint('project', __name__)


# 🟢 Crear nuevo proyecto
# 🟢 Crear nuevo proyecto
@project_bp.route('/projects/new', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def project_new():
    if request.method == 'POST':
        data = {
            'nombre': request.form.get('nombre', '').strip(),
            'sitio': request.form.get('sitio', '').strip(),
            'prioridad': request.form.get('prioridad', 'Alta'),
            'status': request.form.get('status', 'Planeado'),
            'comentarios': request.form.get('comentarios', '').strip(),
            'ahorro': request.form.get('ahorro', '0').strip(),
            'gasto': request.form.get('gasto', '0').strip()
        }

        if not data['nombre'] or not data['sitio']:
            flash("Nombre y sitio son obligatorios.", "warning")
            return render_template('project_form.html', mode='new', project=None)

        try:
            pid = create_project(current_app, data)
            flash("Proyecto creado correctamente con número autogenerado.", "success")
            return redirect(url_for('project.project_detail', project_id=pid))
        except Exception as e:
            flash(f"Error creando proyecto: {e}", "danger")

    return render_template('project_form.html', mode='new', project=None)





# 🟡 Editar proyecto
@project_bp.route('/projects/<int:project_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def project_edit(project_id):
    from models import registrar_inicio_trabajo, registrar_fin_trabajo
    from models.time_tracking import cerrar_tiempos_subtareas_abiertas  # 👈 nuevo import aquí

    p = get_project(current_app, project_id)
    if not p:
        flash("Proyecto no encontrado.", "warning")
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        data = {
            'nombre': request.form.get('nombre', '').strip(),
            'sitio': request.form.get('sitio', '').strip(),
            'prioridad': request.form.get('prioridad', 'Alta'),
            'status': request.form.get('status', 'Planeado'),
            'comentarios': request.form.get('comentarios', '').strip(),
            'ahorro': request.form.get('ahorro', '0').strip(),
            'gasto': request.form.get('gasto', '0').strip()
        }

        try:
            db = get_db(current_app)
            cur = db.cursor()

            # 🔹 Si se activa “Trabajando”
            if data['status'] == 'Trabajando':
                cur.execute("SELECT id, nombre FROM projects WHERE status='Trabajando' AND id != ?;", (project_id,))
                active = cur.fetchone()
                if active:
                    cur.execute("UPDATE projects SET status='Detenido' WHERE id=?;", (active['id'],))
                    db.commit()
                    registrar_fin_trabajo(current_app, active['id'])
                    flash(f"El proyecto '{active['nombre']}' se cambió automáticamente a 'Detenido'.", "info")

                registrar_inicio_trabajo(current_app, project_id)

            # 🔹 Si estaba trabajando y se detiene o cierra
            elif p['status'] == 'Trabajando' and data['status'] != 'Trabajando':
                registrar_fin_trabajo(current_app, project_id)

                # 🔹 Cerrar automáticamente tiempos de subtareas abiertas
                cerrar_tiempos_subtareas_abiertas(current_app, project_id)
                flash("⏹️ Se detuvieron los tiempos de las subtareas activas.", "info")

            # 🔹 Finalmente actualizar proyecto
            update_project(current_app, project_id, data)
            flash("Proyecto actualizado correctamente.", "success")
            return redirect(url_for('project.project_detail', project_id=project_id))

        except Exception as e:
            flash(f"Error actualizando proyecto: {e}", "danger")

    return render_template('project_form.html', mode='edit', project=p)







# 🔵 Detalle de proyecto
@project_bp.route('/projects/<int:project_id>', methods=['GET', 'POST'])
@login_required
def project_detail(project_id):
    from models import agregar_historial
    from models.db import get_db

    p = get_project(current_app, project_id)
    if not p:
        flash("Proyecto no encontrado.", "warning")
        return redirect(url_for('main.index'))

    filter_status = request.args.get('filter', 'all')
    subs = get_subtasks_for_project(current_app, project_id, filter_status)
    avance = project_progress(current_app, project_id)

    username = session.get('username', 'user')
    subtareas = []
    for s in subs:
        d = dict(s)
        d['trabajando'] = esta_trabajando_en_subtarea(current_app, d['id'], username)
        subtareas.append(d)

    # 🔹 Comentarios
    if request.method == 'POST' and 'comment_text' in request.form:
        text = request.form.get('comment_text', '').strip()
        if text:
            user = session.get('username', 'user')
            append_project_comment(current_app, project_id, user, text)
            detalle = f"{user} agregó un comentario en '{p['nombre']}': \"{text[:100]}...\""
            agregar_historial(current_app, tipo="proyecto", ref_id=project_id,
                              accion="Comentario", detalle=detalle, usuario=user)
            flash("Comentario agregado correctamente.", "success")
            return redirect(url_for('project.project_detail', project_id=project_id, filter=filter_status))

    # 🔹 Historial
    db = get_db(current_app)
    cur = db.cursor()
    cur.execute("""
        SELECT * FROM historial
        WHERE (tipo='subtarea' AND ref_id IN (SELECT id FROM subtasks WHERE project_id=?))
           OR (tipo='proyecto' AND ref_id=?)
        ORDER BY datetime(fecha) DESC;
    """, (project_id, project_id))
    historial = cur.fetchall()

    # 🔹 Reglas de categorización automática (usando categoria_reglas)
    cur.execute("""
        SELECT categoria, GROUP_CONCAT(palabra, ', ') AS palabras, COUNT(*) AS total
        FROM categoria_reglas
        GROUP BY categoria
        ORDER BY categoria;
    """)
    reglas = cur.fetchall()

    # 🔹 Cargar paquetes disponibles dinámicamente
    cur.execute("SELECT id, nombre FROM paquete_subtareas ORDER BY id;")
    paquetes = cur.fetchall()


    okrs = get_okrs(current_app)

    return render_template(
        'project_detail.html',
        project=p,
        subtasks=subtareas,
        avance=avance,
        filter_status=filter_status,
        historial=historial,
        reglas=reglas,
        paquetes=paquetes,
        okrs=okrs  # 👈 agregado aquí
    )






# 🟣 Crear nueva subtarea
@project_bp.route('/projects/<int:project_id>/subtasks/new', methods=['POST'])
@login_required
@role_required('admin')
def subtask_new(project_id):
    from flask import current_app, session, request, flash, redirect, url_for
    from models.subtasks_utils import create_subtask_with_metadata
    from models import get_project, agregar_historial

    nombre = request.form.get('nombre_subtarea', '').strip()
    tiempo_objetivo = float(request.form.get('tiempo_objetivo_horas', 8))
    tecnologia = request.form.get('tecnologia', 'Otro')
    dificultad = int(request.form.get('dificultad', 1))
    kr = request.form.get('kr', '')
    usuario = session.get('username')

    if not nombre:
        flash("⚠️ El nombre de la subtarea es obligatorio.", "warning")
        return redirect(url_for('project.project_detail', project_id=project_id))

    proyecto = get_project(current_app, project_id)
    if not proyecto:
        flash("Proyecto no encontrado.", "danger")
        return redirect(url_for('main.index'))

    if proyecto['status'] != 'Trabajando':
        flash("⚠️ Solo puedes agregar subtareas cuando el proyecto está en estado 'Trabajando'.", "warning")
        return redirect(url_for('project.project_detail', project_id=project_id))

    try:
        # 🧩 Nueva función centralizada (usa la original + IA)
        subtask_id, analisis = create_subtask_with_metadata(
            current_app, project_id, nombre, tiempo_objetivo, tecnologia, dificultad, kr, usuario
        )

        if subtask_id:
            detalle = (
                f"Se creó la subtarea '{nombre}' (objetivo: {tiempo_objetivo}h, "
                f"KR:{kr}, Tec:{tecnologia}, Dif:{dificultad}) por {usuario}."
            )
            agregar_historial(current_app, tipo="subtarea", ref_id=subtask_id,
                              accion="Creada", detalle=detalle, usuario=usuario)

            flash("✅ Subtarea creada correctamente.", "success")
        else:
            flash("⚠️ No se pudo crear la subtarea.", "danger")

    except Exception as e:
        flash(f"Error al crear subtarea: {e}", "danger")

    return redirect(url_for('project.project_detail', project_id=project_id))








# 🔻 Alternar estado cerrado / abierto
@project_bp.route('/subtasks/<int:subtask_id>/toggle', methods=['POST'])
@login_required
@role_required('admin')
def subtask_toggle(subtask_id):
    from models import agregar_historial

    db = get_db(current_app)
    cur = db.cursor()
    cur.execute("""
        SELECT s.id, s.nombre_subtarea, s.cerrado, s.project_id,
               p.nombre AS project_nombre, p.status AS project_status
        FROM subtasks s
        JOIN projects p ON s.project_id = p.id
        WHERE s.id=?;
    """, (subtask_id,))
    sub = cur.fetchone()

    if not sub:
        flash("Subtarea no encontrada.", "warning")
        return redirect(url_for('main.index'))

    if sub['project_status'] != 'Trabajando':
        flash("⚠️ No puedes cerrar o reabrir subtareas mientras el proyecto no esté 'Trabajando'.", "warning")
        return redirect(url_for('project.project_detail', project_id=sub['project_id']))

    try:
        nuevo_estado = 0 if sub['cerrado'] == 1 else 1
        fecha_cierre = datetime.now().isoformat() if nuevo_estado == 1 else None
        cur.execute("UPDATE subtasks SET cerrado=?, fecha_cierre=? WHERE id=?;", (nuevo_estado, fecha_cierre, subtask_id))
        db.commit()

        accion = "Cerrado" if nuevo_estado == 1 else "Reabierto"
        detalle = f"La subtarea '{sub['nombre_subtarea']}' del proyecto '{sub['project_nombre']}' fue {accion.lower()} por {session.get('username')}."
        agregar_historial(current_app, tipo="subtarea", ref_id=subtask_id,
                          accion=accion, detalle=detalle, usuario=session.get('username'))
        flash("Estado de subtarea actualizado.", "success")

    except Exception as e:
        flash(f"Error actualizando subtarea: {e}", "danger")

    return redirect(url_for('project.project_detail', project_id=sub['project_id']))


# 🟠 Iniciar / detener tiempo de subtarea
@project_bp.route('/subtasks/<int:subtask_id>/timer', methods=['POST'])
@login_required
def subtask_timer_toggle(subtask_id):
    """Inicia o detiene el tiempo de trabajo en una subtarea."""
    username = session.get('username', 'user')
    trabajando = esta_trabajando_en_subtarea(current_app, subtask_id, username)

    if trabajando:
        detener_tiempo_subtarea(current_app, subtask_id, username)
        flash("⏸ Tiempo detenido para esta subtarea.", "info")
    else:
        iniciar_tiempo_subtarea(current_app, subtask_id, username)
        flash("▶️ Tiempo iniciado para esta subtarea.", "success")

    db = get_db(current_app)
    cur = db.cursor()
    cur.execute("SELECT project_id FROM subtasks WHERE id=?;", (subtask_id,))
    pid = cur.fetchone()['project_id']

    return redirect(url_for('project.project_detail', project_id=pid))
