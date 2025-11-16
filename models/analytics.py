# models/analytics.py
from datetime import date
from calendar import monthrange

def get_exec_metrics(db, year: int, month: int):
    """
    Executive analytics dashboard (English version)
    --------------------------------------------------
    Returns:
      - hours_by_project: list[{project, actual_hours, target_hours, status}]
      - closed_by_week: list[{week_label, closed}]
      - top_operators: list[{username, efficiency_pct, actual_hours, target_hours}]
      - ahorro_total: total savings (USD)
      - proj_cierre_mes: projected closures this month
      - data_insights: short textual executive insights
    """
    cur = db.cursor()

    # 📆 Month range
    start = f"{year:04d}-{month:02d}-01"
    end_day = monthrange(year, month)[1]
    end = f"{year:04d}-{month:02d}-{end_day:02d}"

    # ------------------------------------------------------
    # ⏱ Hours per project (actual vs target) + STATUS
    # ------------------------------------------------------
    cur.execute("""
        SELECT 
            p.id AS project_id,
            p.nombre AS project,
            p.status AS status_db,
            IFNULL(SUM(CASE 
                WHEN DATE(t.inicio) BETWEEN ? AND ? 
                THEN CAST(t.duracion_min AS REAL) ELSE 0 END), 0) / 60.0 AS actual_hours
        FROM projects p
        LEFT JOIN subtasks s ON s.project_id = p.id
        LEFT JOIN subtask_tiempo t ON t.subtask_id = s.id
        GROUP BY p.id, p.nombre, p.status
        ORDER BY p.nombre;
    """, (start, end))
    real_rows = {r["project_id"]: dict(r) for r in cur.fetchall()}

    cur.execute("""
        SELECT 
            p.id AS project_id, 
            p.nombre AS project,
            IFNULL(SUM(COALESCE(s.tiempo_objetivo_horas, 0)), 0) AS target_hours
        FROM projects p
        LEFT JOIN subtasks s ON s.project_id = p.id
        WHERE DATE(s.fecha_apertura) BETWEEN ? AND ?
        GROUP BY p.id, p.nombre
        ORDER BY p.nombre;
    """, (start, end))
    objetivo_rows = {r["project_id"]: dict(r) for r in cur.fetchall()}

    hours_by_project = []
    for pid, data in real_rows.items():
        target_hours = objetivo_rows.get(pid, {}).get("target_hours", 0) if objetivo_rows.get(pid) else 0
        estado = (data.get("status_db") or "").strip().lower()

        # 🟢 Translate & assign color
        if estado == "cerrado":
            status_label = "Closed"
            badge = "bg-success"
        elif estado == "trabajando":
            status_label = "In Progress"
            badge = "bg-warning text-dark"
        elif estado == "detenido":
            status_label = "On Hold"
            badge = "bg-danger"
        else:
            status_label = "Unknown"
            badge = "bg-secondary"

        hours_by_project.append({
            "project": data["project"],
            "actual_hours": round(data["actual_hours"] or 0, 2),
            "target_hours": round(target_hours or 0, 2),
            "status": status_label,
            "badge": badge
        })

    # Add projects that only have target but no real hours
    for pid, data in objetivo_rows.items():
        if pid not in real_rows:
            hours_by_project.append({
                "project": data["project"],
                "actual_hours": 0.0,
                "target_hours": round(data["target_hours"] or 0, 2),
                "status": "On Hold",
                "badge": "bg-danger"
            })
    # 🔹 Contadores de estado de proyectos
    projects_closed = sum(1 for p in hours_by_project if p["status"] == "Closed")
    projects_working = sum(1 for p in hours_by_project if p["status"] == "In Progress")
    projects_stopped = sum(1 for p in hours_by_project if p["status"] == "On Hold")

    # (Opcional: calcular % cerrados)
    projects_closed_pct = round(projects_closed / len(hours_by_project) * 100, 1) if hours_by_project else 0

    # ------------------------------------------------------
    # 📅 Weekly closures
    # ------------------------------------------------------
    cur.execute("""
        SELECT strftime('%W', s.fecha_cierre) AS week_num, COUNT(*) AS closed
        FROM subtasks s
        WHERE s.cerrado = 1 AND DATE(s.fecha_cierre) BETWEEN ? AND ?
        GROUP BY week_num ORDER BY week_num;
    """, (start, end))
    closed_by_week = [{"week_label": f"W{r['week_num']}", "cerrados": r["closed"]} for r in cur.fetchall()]

    # ------------------------------------------------------
    # 🧑‍🔧 Top 3 most efficient operators
    # ------------------------------------------------------
    cur.execute("""
        WITH work AS (
            SELECT t.username, t.subtask_id,
                   SUM(CASE WHEN DATE(t.inicio) BETWEEN ? AND ? THEN CAST(t.duracion_min AS REAL) ELSE 0 END) AS min_tot
            FROM subtask_tiempo t
            GROUP BY t.username, t.subtask_id
        ),
        obj AS (
            SELECT w.username, SUM(COALESCE(s.tiempo_objetivo_horas, 0)) AS obj_h
            FROM work w
            JOIN subtasks s ON s.id = w.subtask_id
            WHERE w.min_tot > 0
            GROUP BY w.username
        ),
        real AS (
            SELECT w.username, SUM(w.min_tot)/60.0 AS real_h
            FROM work w WHERE w.min_tot > 0 GROUP BY w.username
        )
        SELECT r.username,
               ROUND(COALESCE(o.obj_h, 0), 2) AS target_hours,
               ROUND(COALESCE(r.real_h, 0), 2) AS actual_hours,
               CASE WHEN r.real_h > 0 THEN ROUND((o.obj_h / r.real_h) * 100, 1) ELSE 0 END AS efficiency_pct
        FROM real r
        LEFT JOIN obj o ON o.username = r.username
        WHERE r.username IS NOT NULL AND r.username <> ''
        ORDER BY efficiency_pct DESC
        LIMIT 3;
    """, (start, end))
    top_operators = [dict(r) for r in cur.fetchall()]

    # ------------------------------------------------------
    # 💰 Total savings
    # ------------------------------------------------------
    cur.execute("""
        SELECT IFNULL(SUM(p.ahorro), 0) AS ahorro_total
        FROM projects p
        WHERE DATE(p.fecha_cierre) BETWEEN ? AND ?
           OR p.status IN ('Trabajando', 'Detenido');
    """, (start, end))
    ahorro_total = round((cur.fetchone()["ahorro_total"] or 0), 2)

    # ------------------------------------------------------
    # 📈 Projection of closures
    # ------------------------------------------------------
    today = date.today()
    total_days = monthrange(year, month)[1]
    elapsed = today.day if (today.year == year and today.month == month) else total_days
    cur.execute("""
        SELECT COUNT(*) AS closed
        FROM subtasks
        WHERE cerrado = 1 AND DATE(fecha_cierre) BETWEEN ? AND ?;
    """, (start, f"{year:04d}-{month:02d}-{min(elapsed, total_days):02d}"))
    cerrados_hoy = cur.fetchone()["closed"] or 0
    pace = (cerrados_hoy / elapsed) if elapsed else 0
    proj_cierre_mes = round(pace * total_days, 0)

    # ------------------------------------------------------
    # 🧠 Executive Insights (automatic summary)
    # ------------------------------------------------------
    total_projects = len(hours_by_project)
    closed = sum(1 for p in hours_by_project if p["status"] == "Closed")
    working = sum(1 for p in hours_by_project if p["status"] == "In Progress")
    on_hold = sum(1 for p in hours_by_project if p["status"] == "On Hold")

    avg_efficiency = round(sum(p["actual_hours"] / p["target_hours"] * 100 for p in hours_by_project if p["target_hours"]) / len(hours_by_project), 1) if hours_by_project else 0

    data_insights = [
        f"Total projects analyzed: {total_projects}",
        f"Closed: {closed}, In Progress: {working}, On Hold: {on_hold}",
        f"Average project efficiency: {avg_efficiency}%",
        f"Projected closures this month: {proj_cierre_mes}",
        f"Total savings reported: ${ahorro_total}"
    ]

    if avg_efficiency < 90:
        data_insights.append("⚠️ Efficiency below target — potential delays expected.")
    elif avg_efficiency > 110:
        data_insights.append("✅ Efficiency above target — strong execution pace.")

    return {
    "period": {"year": year, "month": month, "start": start, "end": end},
    "hours_by_project": sorted(hours_by_project, key=lambda x: x["project"].lower()),
    "closed_by_week": closed_by_week,
    "top_operators": top_operators,
    "ahorro_total": ahorro_total,
    "proj_cierre_mes": int(proj_cierre_mes),
    "projects_closed": projects_closed,
    "projects_working": projects_working,
    "projects_stopped": projects_stopped,
    "projects_closed_pct": projects_closed_pct,
    "data_insights": data_insights,
}

