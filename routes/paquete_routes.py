# routes/paquete_routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from auth import login_required, role_required
from models.db import get_db

paquete_bp = Blueprint('paquete', __name__, url_prefix="/paquetes")


# 🧩 Página principal de gestión
@paquete_bp.route("/", methods=["GET", "POST"])
@login_required
@role_required('admin')
def admin_paquetes():
    db = get_db(current_app)
    cur = db.cursor()

    # 🔹 Crear nuevo paquete
    if request.method == "POST" and "nuevo_paquete" in request.form:
        nombre = request.form.get("nombre", "").strip()
        descripcion = request.form.get("descripcion", "").strip()
        usuario = request.form.get("creado_por", "admin")
        if nombre:
            cur.execute(
                "INSERT INTO paquete_subtareas (nombre, descripcion, creado_por) VALUES (?, ?, ?)",
                (nombre, descripcion, usuario)
            )
            db.commit()
            flash("✅ Paquete creado correctamente.", "success")
        else:
            flash("⚠️ Debes escribir un nombre.", "warning")
        return redirect(url_for("paquete.admin_paquetes"))

    # 🔹 Eliminar paquete
    eliminar_id = request.args.get("delete")
    if eliminar_id:
        cur.execute("DELETE FROM paquete_subtareas WHERE id = ?", (eliminar_id,))
        db.commit()
        flash("🗑️ Paquete eliminado.", "info")
        return redirect(url_for("paquete.admin_paquetes"))

    # 🔹 Consultar todos los paquetes
    cur.execute("SELECT * FROM paquete_subtareas ORDER BY id DESC;")
    paquetes = cur.fetchall()

    return render_template("admin_paquetes.html", paquetes=paquetes)





@paquete_bp.route("/detalles", methods=["GET", "POST"])
@login_required
@role_required('admin')
def admin_subdetalles():
    db = get_db(current_app)
    cur = db.cursor()

    # 🔹 Filtro por paquete
    paquete_id = request.args.get("paquete_id")

    # 🔹 Crear subdetalle nuevo
    if request.method == "POST":
        nombre_subtarea = request.form.get("nombre_subtarea", "").strip()
        categoria = request.form.get("categoria", "")
        prioridad = request.form.get("prioridad", "")
        tecnologia = request.form.get("tecnologia", "")
        dificultad = request.form.get("dificultad", 1)
        tiempo = request.form.get("tiempo_objetivo_horas", 0)
        comentarios = request.form.get("comentarios", "")
        aprendizaje = request.form.get("aprendizaje", "")
        kr = request.form.get("kr", "")
        paquete_id_form = request.form.get("paquete_id")

        if nombre_subtarea and paquete_id_form:
            cur.execute("""
                INSERT INTO paquete_subtareas_detalle 
                (paquete_id, nombre_subtarea, categoria, prioridad, tecnologia, dificultad, 
                 tiempo_objetivo_horas, comentarios, aprendizaje, kr)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (paquete_id_form, nombre_subtarea, categoria, prioridad, tecnologia,
                  dificultad, tiempo, comentarios, aprendizaje, kr))
            db.commit()
            flash("✅ Subdetalle agregado correctamente.", "success")
            return redirect(url_for("paquete.admin_subdetalles", paquete_id=paquete_id_form))

    # 🔹 Cargar lista de paquetes para el filtro
    cur.execute("SELECT id, nombre FROM paquete_subtareas ORDER BY id DESC;")
    paquetes = cur.fetchall()

    # 🔹 Cargar subdetalles (filtrados o todos)
    if paquete_id:
        cur.execute("""
            SELECT sd.*, p.nombre AS paquete_nombre
            FROM paquete_subtareas_detalle sd
            JOIN paquete_subtareas p ON p.id = sd.paquete_id
            WHERE p.id = ?
            ORDER BY sd.id DESC;
        """, (paquete_id,))
    else:
        cur.execute("""
            SELECT sd.*, p.nombre AS paquete_nombre
            FROM paquete_subtareas_detalle sd
            JOIN paquete_subtareas p ON p.id = sd.paquete_id
            ORDER BY sd.id DESC;
        """)
    subdetalles = cur.fetchall()

    cur.execute("""
    SELECT categoria, GROUP_CONCAT(palabra, ', ') AS palabras, COUNT(*) AS total
    FROM categoria_reglas
    GROUP BY categoria
    ORDER BY categoria;
""")
    reglas = cur.fetchall()

    # 🔹 Cargar todos los OKR activos ordenados por categoría y nombre
    cur.execute("""
        SELECT categoria, kr
        FROM okr_kr
        WHERE activo = 1
        ORDER BY categoria, kr;
    """)
    okrs = cur.fetchall()




    return render_template("admin_paquete_detalle.html",
                           paquetes=paquetes,
                           subdetalles=subdetalles,
                           paquete_id=paquete_id,
                           reglas=reglas,
                           okrs=okrs)
