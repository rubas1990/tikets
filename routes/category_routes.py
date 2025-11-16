# routes/category_routes.py

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from auth import login_required, role_required
from models.db import get_db
from models.normalize_subtasks import categorizar_subtarea

category_bp = Blueprint('category', __name__, url_prefix="/admin")


# 🔹 Página principal de gestión de categorías
@category_bp.route("/categorias", methods=["GET", "POST"])
@login_required
@role_required('admin')
def tabla_categorias():
    db = get_db(current_app)
    cur = db.cursor()

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

    cur.execute("""
        SELECT id, nombre_subtarea, categoria
        FROM subtasks
        ORDER BY id DESC;
    """)
    subtareas = cur.fetchall()

    cur.execute("""
        SELECT DISTINCT categoria
        FROM subtasks
        WHERE categoria IS NOT NULL AND categoria <> '';
    """)
    categorias_existentes = sorted([r["categoria"] for r in cur.fetchall()])

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


# ✅ Re-Categorizar todas las subtareas automáticamente
@category_bp.route("/categorizar")
@login_required
def recategorizar_subtareas():
    db = get_db(current_app)
    cur = db.cursor()

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
        categoria_final = normalizacion.get(categoria_detectada.lower().strip(), categoria_detectada)
        cur.execute("UPDATE subtasks SET categoria=? WHERE id=?;", (categoria_final, r["id"]))
        total += 1

    db.commit()
    flash(f"✅ {total} subtareas recategorizadas automáticamente.", "success")
    return redirect(url_for('dashboard.dashboard'))


# ✅ Gestionar reglas de categorización
@category_bp.route("/categoria-reglas", methods=["GET", "POST"])
@login_required
@role_required('admin')
def categoria_reglas_admin():
    db = get_db(current_app)
    cur = db.cursor()

    if request.method == "POST":
        palabra = request.form.get("palabra", "").strip().lower()
        categoria = request.form.get("categoria", "").strip().lower()

        categoria = categoria.replace("  ", " ").replace("/", " / ").strip()
        categoria = " / ".join([p.capitalize().strip() for p in categoria.split("/")])

        if palabra and categoria:
            cur.execute("SELECT COUNT(*) AS c FROM categoria_reglas WHERE palabra = ?;", (palabra,))
            if cur.fetchone()["c"] > 0:
                flash(f"⚠️ La palabra '{palabra}' ya existe.", "warning")
            else:
                cur.execute("""
                    INSERT INTO categoria_reglas (palabra, categoria)
                    VALUES (?, ?);
                """, (palabra, categoria))
                db.commit()
                flash(f"✅ Palabra '{palabra}' agregada correctamente en '{categoria}'.", "success")
        else:
            flash("❌ Debes ingresar una palabra y su categoría.", "danger")

        return redirect(url_for("category.categoria_reglas_admin"))

    eliminar_id = request.args.get("delete")
    if eliminar_id:
        cur.execute("DELETE FROM categoria_reglas WHERE id = ?;", (eliminar_id,))
        db.commit()
        flash("🗑️ Palabra eliminada correctamente.", "info")
        return redirect(url_for("category.categoria_reglas_admin"))

    cur.execute("SELECT DISTINCT categoria FROM categoria_reglas ORDER BY LOWER(categoria);")
    categorias_existentes = sorted([c["categoria"] for c in cur.fetchall() if c["categoria"]])

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

    return render_template(
        "admin_categoria_reglas.html",
        reglas=reglas,
        categorias_existentes=categorias_existentes,
        categoria_filtro=categoria_filtro
    )


# ✅ Unificar reglas repetidas bajo una sola categoría limpia
@category_bp.route("/unificar-categorias")
@login_required
@role_required('admin')
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
    return redirect(url_for("category.categoria_reglas_admin"))
