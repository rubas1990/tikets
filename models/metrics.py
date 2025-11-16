from datetime import datetime
from .db import get_db


# -----------------------------------------------------------
# Calcula el % de avance de un proyecto según sus subtareas
# -----------------------------------------------------------
def project_progress(app, project_id):
    db = get_db(app)
    cur = db.cursor()

    # Total de subtareas
    cur.execute("SELECT COUNT(*) AS total FROM subtasks WHERE project_id=?;", (project_id,))
    total = cur.fetchone()['total']

    if total == 0:
        return 0.0

    # Cerradas
    cur.execute("SELECT COUNT(*) AS cerradas FROM subtasks WHERE project_id=? AND cerrado=1;", (project_id,))
    cerradas = cur.fetchone()['cerradas']

    return round((cerradas / total) * 100.0, 2)


# -----------------------------------------------------------
# Inserta una entrada en el historial general
# -----------------------------------------------------------
def agregar_historial(app, tipo, ref_id, accion, detalle, usuario):
    db = get_db(app)
    cur = db.cursor()

    fecha_local = datetime.now().isoformat()
    cur.execute("""
        INSERT INTO historial (tipo, ref_id, fecha, accion, detalle, usuario)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (tipo, ref_id, fecha_local, accion, detalle, usuario))

    db.commit()


# -----------------------------------------------------------
# Métricas para el Dashboard
# -----------------------------------------------------------
from datetime import datetime
from .db import get_db


def dashboard_metrics(app, fecha_inicio=None, fecha_fin=None, sin_filtro=False):
    """Dashboard: KPIs y gráfica filtrados por fecha (tabla siempre completa)."""
    db = get_db(app)
    cur = db.cursor()

    # ======================================================
    # 🧱 1️⃣ TABLA COMPLETA (NO FILTRADA)
    # ======================================================
    cur.execute("""
        SELECT 
            p.id AS project_id, 
            p.nombre, 
            p.prioridad, 
            p.numero_de_queja,
            p.status,
            COUNT(s.id) AS subtareas_total,
            SUM(CASE WHEN s.cerrado=1 THEN 1 ELSE 0 END) AS subtareas_cerradas,
            SUM(CASE WHEN s.cerrado=0 THEN 1 ELSE 0 END) AS subtareas_abiertas,
            ROUND(AVG(
                CASE WHEN s.fecha_cierre IS NOT NULL AND s.fecha_apertura IS NOT NULL
                     THEN (julianday(s.fecha_cierre) - julianday(s.fecha_apertura)) * 24 END
            ), 2) AS promedio_cierre_horas,
            ROUND(AVG(
                CASE 
                    WHEN s.tiempo_objetivo_horas IS NOT NULL 
                         AND s.tiempo_objetivo_horas > 0 
                         AND s.cerrado = 1
                    THEN (
                        s.tiempo_objetivo_horas /
                        NULLIF(
                            (SELECT IFNULL(SUM(duracion_min)/60.0, 0)
                             FROM subtask_tiempo t 
                             WHERE t.subtask_id = s.id), 0
                        )
                    ) * 100
                END
            ), 2) AS eficiencia_pct,
            IFNULL(p.ahorro, 0) AS ahorro,
            IFNULL(p.gasto, 0) AS gasto
        FROM projects p
        LEFT JOIN subtasks s ON s.project_id = p.id
        GROUP BY p.id
        ORDER BY 
            CASE 
                WHEN p.prioridad GLOB '[0-9]' THEN CAST(p.prioridad AS INTEGER)
                ELSE 99
            END ASC;
    """)
    rows = cur.fetchall()

    por_proyecto = []
    eficiencias_globales = []
    total_ahorro = total_gasto = total_tikets = total_abiertas = total_cerradas = 0
    total_proyectos_abiertos = total_proyectos_cerrados = 0

    for r in rows:
        total = r['subtareas_total'] or 0
        cerradas = r['subtareas_cerradas'] or 0
        avance_pct = round((cerradas / total) * 100, 2) if total > 0 else 0

        # 🔹 Horas trabajadas totales
        cur.execute("SELECT SUM(duracion_horas) AS total_horas FROM project_tiempo WHERE project_id=?;", (r['project_id'],))
        total_horas = cur.fetchone()['total_horas'] or 0

        # 🔹 Acumuladores globales
        if r['eficiencia_pct'] and r['eficiencia_pct'] > 0:
            eficiencias_globales.append(r['eficiencia_pct'])
        total_ahorro += r['ahorro'] or 0
        total_gasto += r['gasto'] or 0
        total_tikets += total
        total_abiertas += r['subtareas_abiertas'] or 0
        total_cerradas += cerradas
        if avance_pct >= 100:
            total_proyectos_cerrados += 1
        else:
            total_proyectos_abiertos += 1

        # 🔮 Predicción visual
        if avance_pct == 0:
            prediccion = "🔴 No progress yet"
        elif avance_pct < 50:
            prediccion = "⚠️ Low progress — possible delay"
        elif 50 <= avance_pct < 100:
            prediccion = "🟡 Near closure"
        else:
            prediccion = "✅ Closed"

        por_proyecto.append({
            **r,
            "avance_pct": avance_pct,
            "horas_trabajadas": round(total_horas, 2),
            "prediccion": prediccion
        })

    # ======================================================
    # 🎯 2️⃣ KPIs — Filtrados por subtasks.fecha_apertura
    # ======================================================
    filtro = ""
    params = []
    if fecha_inicio and fecha_fin and not sin_filtro:
        filtro = "WHERE strftime('%Y-%m-%d', s.fecha_apertura) BETWEEN ? AND ?"
        params = [fecha_inicio, fecha_fin]

    # --- 🔹 Tickets filtrados
    cur.execute(f"""
        SELECT 
            COUNT(s.id) AS total_tikets,
            SUM(CASE WHEN s.cerrado=1 THEN 1 ELSE 0 END) AS cerradas,
            SUM(CASE WHEN s.cerrado=0 THEN 1 ELSE 0 END) AS abiertas
        FROM subtasks s
        {filtro};
    """, params)
    row_t = cur.fetchone() or {'total_tikets': 0, 'cerradas': 0, 'abiertas': 0}

    # --- 🔹 Promedio eficiencia (filtrada)
    cur.execute(f"""
        SELECT ROUND(AVG(
            CASE 
                WHEN s.tiempo_objetivo_horas IS NOT NULL 
                     AND s.tiempo_objetivo_horas > 0 
                     AND s.cerrado = 1
                THEN (
                    s.tiempo_objetivo_horas /
                    NULLIF(
                        (SELECT IFNULL(SUM(duracion_min)/60.0, 0)
                         FROM subtask_tiempo t 
                         WHERE t.subtask_id = s.id), 0
                    )
                ) * 100
            END
        ), 2) AS eficiencia_prom
        FROM subtasks s
        {filtro};
    """, params)
    eficiencia_f = cur.fetchone()['eficiencia_prom'] or 0

    # --- 🔹 Ahorro y gasto (filtrados por proyectos vinculados a subtareas del rango)
    cur.execute(f"""
        SELECT 
            IFNULL(SUM(p.ahorro), 0) AS ahorro_f,
            IFNULL(SUM(p.gasto), 0) AS gasto_f
        FROM projects p
        WHERE p.id IN (
            SELECT DISTINCT s.project_id
            FROM subtasks s
            {filtro}
        );
    """, params)
    row_ag = cur.fetchone() or {'ahorro_f': 0, 'gasto_f': 0}

    # ======================================================
    # 🧮 3️⃣ Resultado final
    # ======================================================
    promedio_eficiencia = (
        eficiencia_f or
        (round(sum(eficiencias_globales) / len(eficiencias_globales), 2)
         if eficiencias_globales else 0)
    )




    # ======================================================
    # 🧩 4️⃣ DISTRIBUCIÓN DE CATEGORÍAS
    # ======================================================
    cur.execute("""
        SELECT categoria, COUNT(*) AS total
        FROM subtasks
        WHERE categoria IS NOT NULL AND categoria <> ''
        GROUP BY categoria
        ORDER BY total DESC;
    """)
    categorias_data = cur.fetchall()

    categorias_labels = [r["categoria"] for r in categorias_data]
    categorias_values = [r["total"] for r in categorias_data]

    return {
        "por_proyecto": por_proyecto,
        "total_ahorro": round(row_ag["ahorro_f"] or total_ahorro, 2),
        "total_gasto": round(row_ag["gasto_f"] or total_gasto, 2),
        "total_tikets": row_t["total_tikets"] or total_tikets,
        "total_abiertas": row_t["abiertas"] or total_abiertas,
        "total_cerradas": row_t["cerradas"] or total_cerradas,
        "total_proyectos_abiertos": total_proyectos_abiertos,
        "total_proyectos_cerrados": total_proyectos_cerrados,
        "promedio_eficiencia": promedio_eficiencia,
        # 🔹 Nuevo bloque para gráfica de categorías
        "categorias_labels": categorias_labels,
        "categorias_values": categorias_values
    }
