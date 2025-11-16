# routes/agenda.py
# ==========================================================
# Vista Agenda estilo Google Calendar enfocada en proyectos
# ==========================================================


from flask import (
    Blueprint, render_template, current_app, request,
    session, redirect, url_for, flash
)
from auth import login_required
from models import get_db
from datetime import datetime, date
import pytz


# Blueprint para agenda
agenda_bp = Blueprint('agenda', __name__)


@agenda_bp.route('/agenda')
@login_required
def agenda_view():
    """
    Agenda tipo Google Calendar: muestra bloques de tiempo por PROYECTO.
    Cada registro en project_tiempo es una sesión de trabajo real.
    """
    # Zona horaria correcta
    tz = pytz.timezone("America/Monterrey")

    # 🔹 Fecha seleccionada por usuario (si no, hoy)
    fecha_str = request.args.get("fecha")
    if fecha_str:
        fecha_obj = datetime.strptime(fecha_str, "%Y-%m-%d").date()
    else:
        fecha_obj = datetime.now(tz).date()
        fecha_str = fecha_obj.isoformat()

    # Conexión DB
    db = get_db(current_app)
    cur = db.cursor()

    # 🔹 Traer tiempos de trabajo por proyecto
    cur.execute("""
        SELECT t.project_id,
               t.inicio,
               t.fin,
               p.nombre AS nombre_proyecto,
               p.status
        FROM project_tiempo t
        JOIN projects p ON p.id = t.project_id
        WHERE date(t.inicio) = date(?)
        ORDER BY datetime(t.inicio);
    """, (fecha_str,))
    rows = cur.fetchall()

    eventos = []

    # 🔹 Convertir a estructura manejable para la vista
    for r in rows:
        inicio = datetime.fromisoformat(r['inicio'])
        fin = datetime.fromisoformat(r['fin']) if r['fin'] else datetime.now(tz)

        # Referencia: Inicio del día a las 5:00 AM
        start_of_day = datetime.combine(
            inicio.date(),
            datetime.min.time()
        ).replace(hour=5, tzinfo=tz)

        # Distancia en minutos desde las 5:00 AM
        offset_min = max((inicio - start_of_day).total_seconds() / 60, 0)

        # Duración en minutos del bloque
        duracion_min = (fin - inicio).total_seconds() / 60

        # 🔹 Color del bloque según estado del proyecto
        if r['status'] == "Trabajando":
            color = "#4caf50"  # verde
        elif r['status'] == "Detenido":
            color = "#ff9800"  # naranja
        elif r['status'] == "Cerrado":
            color = "#2196f3"  # azul
        else:
            color = "#9e9e9e"  # gris por si acaso

        # Armar evento
        eventos.append({
            "proyecto": r['nombre_proyecto'],
            "inicio": inicio.strftime("%H:%M"),
            "fin": fin.strftime("%H:%M"),
            "duracion_min": duracion_min,
            "offset_min": offset_min,
            "color": color
        })

    # 🔹 Renderizar HTML
    return render_template(
        "agenda.html",
        eventos=eventos,
        fecha=fecha_str
    )




# ==========================================================
# 🧭 Editor de agenda diaria / reflexión
# ==========================================================
@agenda_bp.route('/agenda/editar', methods=['GET', 'POST'])
@login_required
def agenda_edit():
    from flask import session
    db = get_db(current_app)
    cur = db.cursor()
    username = session.get("username")

    if not username:
        flash("⚠️ Sesión expirada. Inicia sesión de nuevo.", "warning")
        return redirect(url_for("auth.login"))

    tz = pytz.timezone("America/Monterrey")
    hoy = datetime.now(tz).date().isoformat()

    # 🧠 POST: guardar reflexión o actividad
    if request.method == "POST":
        # 🌙 Si se envía reflexión
        if 'reflexion_dia' in request.form:
            texto_reflexion = request.form['reflexion_dia'].strip()

            # ✅ Siempre crear un nuevo registro (no sobrescribir)
        if texto_reflexion:
            cur.execute("""
                INSERT INTO reflexion_historia (username, fecha, reflexion, created_at)
                VALUES (?, ?, ?, datetime('now'));
            """, (username, hoy, texto_reflexion))

            db.commit()
            flash("🌙 Reflexión guardada (histórico actualizado).", "success")
            return redirect(url_for("agenda.agenda_edit"))


            db.commit()
            flash("🌙 Reflexión del día guardada correctamente.", "success")
            return redirect(url_for("agenda.agenda_edit"))

        # 🔸 Si no, actualizar una actividad individual
        actividad_id = request.form['id']
        hora_inicio = request.form['hora_inicio']
        hora_fin = request.form['hora_fin']
        actividad = request.form['actividad']
        tipo = request.form['tipo']
        completado = 1 if request.form.get('completado') else 0
        notas = request.form.get('notas', '')

        cur.execute("""
            UPDATE daily_schedule 
            SET hora_inicio=?, hora_fin=?, actividad=?, tipo=?, completado=?, notas=?
            WHERE id=? AND username=?;
        """, (hora_inicio, hora_fin, actividad, tipo, completado, notas, actividad_id, username))
        db.commit()
        flash("✅ Actividad actualizada.", "success")
        return redirect(url_for("agenda.agenda_edit"))

    # 🔹 Mostrar datos
    cur.execute("""
        SELECT id, hora_inicio, hora_fin, actividad, tipo, fase, completado, notas
        FROM daily_schedule
        WHERE username=?
        ORDER BY hora_inicio;
    """, (username,))
    actividades = cur.fetchall()

    # 🌙 Obtener reflexión de hoy
    cur.execute("""
        SELECT reflexion FROM reflexion_historia
        WHERE username=? AND date(fecha)=date(?)
        LIMIT 1;
    """, (username, hoy))
    fila_reflexion = cur.fetchone()
    reflexion_texto = fila_reflexion['reflexion'] if fila_reflexion else ""

    # 🕯 Historial de reflexiones (últimos 7 días)
    cur.execute("""
        SELECT fecha, reflexion, created_at
        FROM reflexion_historia
        WHERE username=?
        ORDER BY datetime(created_at) DESC;
    """, (username,))
    historial = cur.fetchall()



    return render_template(
        "agenda_edit.html",
        actividades=actividades,
        reflexion_texto=reflexion_texto,
        historial=historial
    )
