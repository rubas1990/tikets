# routes/personal_routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, session, jsonify
from auth import login_required
from models import get_db
from models.personal import get_open_subtasks
from models.habits import get_user_habits, get_habit_logs, update_habit_name, toggle_habit
from datetime import datetime, date
import pytz

personal_bp = Blueprint('personal', __name__)


# 🟢 Vista principal de tareas personales
# 🟢 Vista principal de tareas personales
@personal_bp.route('/personal')
@login_required
def personal_view():
    """Muestra todas las tareas personales y de proyecto, además de hábitos."""
    tz = pytz.timezone("America/Monterrey")
    hoy = datetime.now(tz).date().isoformat()
    username = session.get('username', 'user')

    db = get_db(current_app)
    cur = db.cursor()

    # 🔹 Mostrar TODAS las tareas del usuario (no solo las de hoy)
    cur.execute("""
        SELECT id, fecha, tipo, numero_tarea, descripcion, project_id, username
        FROM personal_tasks
        WHERE username = ?
        ORDER BY date(fecha) DESC, id DESC;
    """, (username,))
    tareas = cur.fetchall()

    # 🔹 Subtareas abiertas (para seleccionar desde modal)
    subtareas_abiertas = get_open_subtasks(current_app)

    # 🔹 Contador de tareas del día (solo para limitar creación)
    cur.execute("""
        SELECT COUNT(*) AS c
        FROM personal_tasks
        WHERE username = ? AND fecha = ?;
    """, (username, hoy))
    count = cur.fetchone()['c']

    # 🔹 Hábitos del usuario
    year = date.today().year
    month = date.today().month
    habits = get_user_habits(current_app, username)
    logs = get_habit_logs(current_app, [h['id'] for h in habits], year, month)



        # 💧 Hidratación diaria
    cur.execute("SELECT * FROM agua_diaria WHERE fecha=? AND usuario=?;", (hoy, username))
    agua = cur.fetchone()

    # Si no existe registro para hoy → crear uno nuevo
    if not agua:
        cur.execute("""
            INSERT INTO agua_diaria (fecha, cantidad_actual, objetivo, usuario)
            VALUES (?, ?, ?, ?)
        """, (hoy, 0, 6, username))
        db.commit()
        cur.execute("SELECT * FROM agua_diaria WHERE fecha=? AND usuario=?;", (hoy, username))
        agua = cur.fetchone()

    progreso = (agua["cantidad_actual"] / agua["objetivo"]) * 100 if agua["objetivo"] else 0



    return render_template(
        'personal.html',
        tareas=tareas,
        subtareas=subtareas_abiertas,
        fecha=hoy,
        count=count,
        habits=habits,
        logs=logs,
        year=year,
        month=month,
        agua=agua,
        progreso=progreso
    )


# 🟡 Agregar nueva tarea personal o de proyecto
@personal_bp.route('/personal/add', methods=['POST'])
@login_required
def personal_add():
    """Agrega una nueva tarea (personal o de proyecto)."""
    tz = pytz.timezone("America/Monterrey")
    hoy = datetime.now(tz).date().isoformat()

    username = session.get('username', 'user')
    tipo = request.form.get('tipo')
    numero_tarea = request.form.get('numero_tarea')
    descripcion = request.form.get('descripcion', '').strip()
    project_id = request.form.get('project_id') if tipo == 'Proyecto' else None

    db = get_db(current_app)
    cur = db.cursor()

    # 🔹 Límite diario (10 tareas)
    cur.execute("SELECT COUNT(*) AS c FROM personal_tasks WHERE username=? AND fecha=?;", (username, hoy))
    count = cur.fetchone()['c']
    if count >= 10:
        flash("Ya tienes 10 tareas para hoy.", "warning")
        return redirect(url_for('personal.personal_view'))

    # 🔹 Inserción
    cur.execute("""
        INSERT INTO personal_tasks (fecha, tipo, numero_tarea, descripcion, project_id, username)
        VALUES (?, ?, ?, ?, ?, ?);
    """, (hoy, tipo, numero_tarea, descripcion, project_id, username))
    db.commit()

    flash("Tarea agregada correctamente.", "success")
    return redirect(url_for('personal.personal_view'))


# 🔴 Eliminar tarea
@personal_bp.route('/personal/delete/<int:task_id>', methods=['POST'])
@login_required
def personal_delete(task_id):
    """Elimina una tarea personal."""
    db = get_db(current_app)
    cur = db.cursor()
    cur.execute("DELETE FROM personal_tasks WHERE id=?;", (task_id,))
    db.commit()
    flash("Tarea eliminada.", "info")
    return redirect(url_for('personal.personal_view'))


# 🟣 Vista de hábitos
@personal_bp.route('/personal/habits')
@login_required
def personal_habits():
    """Muestra los hábitos del usuario con su progreso mensual."""
    username = session.get("username")
    hoy = date.today()
    year, month = hoy.year, hoy.month

    habits = get_user_habits(current_app, username)
    logs = get_habit_logs(current_app, [h['id'] for h in habits], year, month)

    return render_template(
        "personal.html",
        habits=habits,
        logs=logs,
        year=year,
        month=month,
        tareas=[],          # prevenir errores en template
        subtareas=[],       # prevenir errores
        fecha=hoy.isoformat(),
        count=0
    )


# 🟢 Marcar / desmarcar un hábito en un día
@personal_bp.route('/personal/habits/toggle', methods=['POST'])
@login_required
def personal_habits_toggle():
    habit_id = request.form['habit_id']
    fecha = request.form['fecha']
    toggle_habit(current_app, habit_id, fecha)
    return ("", 204)


# 🟠 Editar nombre de hábito
@personal_bp.route('/personal/habits/edit', methods=['POST'])
@login_required
def personal_habits_edit():
    habit_id = request.form['habit_id']
    nombre = request.form['nombre']
    update_habit_name(current_app, habit_id, nombre)
    flash("✅ Hábito actualizado correctamente.", "success")
    return redirect(url_for('personal.personal_habits'))


# 🟡 Agregar nuevo hábito
@personal_bp.route('/personal/habits/add', methods=['POST'])
@login_required
def personal_habit_add():
    nombre = request.form['nombre'].strip()
    username = session.get("username")

    if not nombre:
        flash("El nombre del hábito no puede estar vacío.", "warning")
        return redirect(url_for('personal.personal_habits'))

    db = get_db(current_app)
    cur = db.cursor()

    # Límite de 5 hábitos
    cur.execute("SELECT COUNT(*) AS c FROM habits WHERE username = ?", (username,))
    count = cur.fetchone()['c']
    if count >= 5:
        flash("⚠️ Solo puedes tener hasta 5 hábitos activos.", "warning")
        return redirect(url_for('personal.personal_habits'))

    cur.execute("INSERT INTO habits (username, nombre, posicion) VALUES (?, ?, ?)", (username, nombre, count + 1))
    db.commit()

    flash("✅ Hábito agregado correctamente.", "success")
    return redirect(url_for('personal.personal_habits'))









# 💧 AGUA DIARIA
@personal_bp.route("/personal/agua/add", methods=["POST"])
@login_required
def personal_agua_add():
    db = get_db(current_app)
    usuario = session.get("username", "ruben")
    hoy = datetime.now().date().isoformat()

    cur = db.cursor()
    cur.execute("SELECT cantidad_actual, objetivo FROM agua_diaria WHERE fecha=? AND usuario=?", (hoy, usuario))
    row = cur.fetchone()

    if row and row["cantidad_actual"] < row["objetivo"]:
        nuevo = row["cantidad_actual"] + 1
        cur.execute("UPDATE agua_diaria SET cantidad_actual=? WHERE fecha=? AND usuario=?", (nuevo, hoy, usuario))
        db.commit()
        progreso = (nuevo / row["objetivo"]) * 100
        return jsonify({"ok": True, "cantidad": nuevo, "progreso": progreso})
    else:
        return jsonify({"ok": False})