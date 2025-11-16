# routes/dashboard_routes.py
from flask import Blueprint, render_template, request, current_app
from auth import login_required
from models import dashboard_metrics, get_db
from datetime import datetime
from models.estado_emocional import (
    registrar_estado_emocional_diario,
    resumen_emocional_por_categoria,
    historial_categoria,
    regenerar_emocional_desde_historial
)

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/dashboard')
@login_required
def dashboard():
    db = get_db(current_app)
    cur = db.cursor()
    
     # 🔹 Luego continúa normal
    registrar_estado_emocional_diario(db)
    categorias_data = resumen_emocional_por_categoria(db, dias=7)
    categoria = request.args.get("categoria")
    detalle = historial_categoria(db, categoria) if categoria else []
    # Año actual
    current_year = datetime.utcnow().year
    year_str = request.args.get('year')
    year = int(year_str) if year_str and year_str.isdigit() else current_year

    # 🔹 Filtros opcionales
    fecha_inicio = request.args.get('from') or None
    fecha_fin = request.args.get('to') or None
    sin_filtro = request.args.get('all') == '1'

    # Normaliza: si una fecha está vacía, ignora el filtro
    if (fecha_inicio and not fecha_fin) or (fecha_fin and not fecha_inicio):
        fecha_inicio = fecha_fin = None

    # 🔹 Llamar a la función principal con rango
    m = dashboard_metrics(current_app, fecha_inicio=fecha_inicio, fecha_fin=fecha_fin, sin_filtro=sin_filtro)

    # 🔹 Promedio de avance (no afecta por rango)
    m['promedio_avance'] = (
        round(sum(p['avance_pct'] for p in m['por_proyecto']) / len(m['por_proyecto']), 2)
        if m['por_proyecto'] else 0
    )

    # === 📊 Gráfica de subtareas ===
    if fecha_inicio and fecha_fin and not sin_filtro:
        # Filtro por rango de fechas
        cur.execute("""
            SELECT strftime('%m', fecha_apertura) AS mes, COUNT(*) AS total
            FROM subtasks
            WHERE fecha_apertura IS NOT NULL
              AND date(fecha_apertura) BETWEEN ? AND ?
            GROUP BY mes ORDER BY mes;
        """, (fecha_inicio, fecha_fin))
        creadas = {int(r['mes']): r['total'] for r in cur.fetchall()}

        cur.execute("""
            SELECT strftime('%m', fecha_cierre) AS mes, COUNT(*) AS total
            FROM subtasks
            WHERE cerrado=1 AND fecha_cierre IS NOT NULL
              AND date(fecha_cierre) BETWEEN ? AND ?
            GROUP BY mes ORDER BY mes;
        """, (fecha_inicio, fecha_fin))
        cerradas = {int(r['mes']): r['total'] for r in cur.fetchall()}

        chart_title = f"{fecha_inicio} → {fecha_fin}"
    else:
        # Filtro anual (por defecto)
        cur.execute("""
            SELECT strftime('%m', fecha_apertura) AS mes, COUNT(*) AS total
            FROM subtasks
            WHERE fecha_apertura IS NOT NULL AND strftime('%Y', fecha_apertura)=?
            GROUP BY mes ORDER BY mes;
        """, (str(year),))
        creadas = {int(r['mes']): r['total'] for r in cur.fetchall()}

        cur.execute("""
            SELECT strftime('%m', fecha_cierre) AS mes, COUNT(*) AS total
            FROM subtasks
            WHERE cerrado=1 AND fecha_cierre IS NOT NULL AND strftime('%Y', fecha_cierre)=?
            GROUP BY mes ORDER BY mes;
        """, (str(year),))
        cerradas = {int(r['mes']): r['total'] for r in cur.fetchall()}

        chart_title = f"{year}"

    # === 🔹 Datos para Chart.js ===
    meses = [datetime(1900, i, 1).strftime('%b') for i in range(1, 13)]
    creadas_vals = [creadas.get(i, 0) for i in range(1, 13)]
    cerradas_vals = [cerradas.get(i, 0) for i in range(1, 13)]

    # === 🔹 Años disponibles ===
    cur.execute("SELECT DISTINCT strftime('%Y', fecha_apertura) AS y FROM subtasks WHERE fecha_apertura IS NOT NULL;")
    years = sorted([int(r['y']) for r in cur.fetchall()]) or [current_year]

    # === 🔹 Renderiza ===
    return render_template(
        'dashboard.html',
        metrics=m,
        year=year,
        available_years=years,
        chart_labels=meses,
        chart_creadas=creadas_vals,
        chart_cerradas=cerradas_vals,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        chart_title=chart_title,
        sin_filtro=sin_filtro
    )



@dashboard_bp.route("/dashboard/emocional")
@login_required
def dashboard_emocional():
    db = get_db(current_app)

    from models.estado_emocional import (
        registrar_estado_emocional_diario,
        resumen_emocional_por_categoria,
        historial_categoria,
        regenerar_emocional_desde_historial
    )

    # 🧠 Generar histórico retroactivo (solo la primera vez, después comentar)
    regenerar_emocional_desde_historial(db, dias=90)

    # 🧠 Registrar día si no está
    registrar_estado_emocional_diario(db)

    # 🔹 Datos principales
    categorias_data = resumen_emocional_por_categoria(db, dias=7)

    # 🔹 Filtro de categoría
    categoria = request.args.get("categoria")
    if not categoria and categorias_data:
        categoria = categorias_data[0]["categoria"]

    detalle = historial_categoria(db, categoria) if categoria else []

    # ⚠️ Detectar alerta de fatiga
    alerta_fatiga = None
    for c in categorias_data:
        if c["prom_horas"] >= 6:
            alerta_fatiga = f"⚠️ Fatiga alta detectada en la categoría {c['categoria']} (promedio {c['prom_horas']}h/día)"
            break

    return render_template(
        "dashboard_emocional.html",
        categorias=categorias_data,
        categoria_seleccionada=categoria,
        detalle=detalle,
        alerta_fatiga=alerta_fatiga
    )
