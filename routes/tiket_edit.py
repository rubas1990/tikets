from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from models import get_db

edit_bp = Blueprint('edit', __name__)

@edit_bp.route('/tiket/<int:tiket_id>/edit', methods=['GET', 'POST'])
def edit_tiket(tiket_id):
    """
    Vista para modificar campos clave de un ticket:
    nombre_subtarea, tecnologia, kr, categoria, dificultad (numérica), comentarios
    """
    db = get_db(current_app)
    cur = db.cursor()

    if request.method == 'POST':
        nombre_subtarea = request.form['nombre_subtarea']
        tecnologia = request.form['tecnologia']
        kr = request.form['kr']
        categoria = request.form['categoria']
        dificultad = int(request.form['dificultad'])  # 🔹 numérico
        comentarios = request.form['comentarios']

        cur.execute("""
            UPDATE subtasks
            SET nombre_subtarea = ?, tecnologia = ?, kr = ?, categoria = ?, dificultad = ?, comentarios = ?
            WHERE id = ?;
        """, (nombre_subtarea, tecnologia, kr, categoria, dificultad, comentarios, tiket_id))
        db.commit()

        flash("✅ Ticket actualizado correctamente.", "success")
        return redirect(url_for('visual.visualizar_tikets'))

    # 🔹 GET → cargar datos existentes
    cur.execute("SELECT * FROM subtasks WHERE id = ?;", (tiket_id,))
    tiket = cur.fetchone()

    # 🔹 Cargar lista de OKR activos
    cur.execute("""
        SELECT categoria, kr
        FROM okr_kr
        WHERE activo = 1
        ORDER BY categoria, kr;
    """)
    okrs = cur.fetchall()

    # 🔹 Niveles numéricos 1–5 con etiquetas descriptivas
    niveles = [
        {"valor": 1, "etiqueta": "1 — Muy fácil"},
        {"valor": 2, "etiqueta": "2 — Fácil"},
        {"valor": 3, "etiqueta": "3 — Media"},
        {"valor": 4, "etiqueta": "4 — Difícil"},
        {"valor": 5, "etiqueta": "5 — Muy difícil"}
    ]

    return render_template('tiket_edit.html', tiket=tiket, okrs=okrs, niveles=niveles)
