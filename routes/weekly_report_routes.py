# routes/weekly_report_routes.py
# ============================================================
# Weekly Execution Review – Amazon-style (L-J 05:00–17:00)
# Genera PDF ejecutivo con:
#  - KPIs (Horas totales, Execution Rate, Eficiencia vs objetivo, Backlog Exposure)
#  - What went well (wins)
#  - What needs attention (gaps) con semáforo
#  - Root cause y Plan de acción (auto)
#
# Rutas:
#   GET /weekly/generate[?when=prev|this][&iso=YYYY-Www]
#   GET /weekly/ping
# Dependencias externas: reportlab (indispensable para PDF)
# DB: usa get_db(current_app) y tablas: subtasks, subtask_tiempo, projects, notifications
# ============================================================

from flask import Blueprint, current_app, send_file, request, jsonify
from auth import login_required
from models.db import get_db
from datetime import datetime, timedelta, date, time
from zoneinfo import ZoneInfo  # stdlib 3.9+
import os

# ReportLab
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors

weekly_bp = Blueprint("weekly", __name__, url_prefix="/weekly")

# =============== PERSONALIZACIÓN DE PORTADA ===============
# Ajusta estos textos si quieres otro encabezado sin tocar el resto.
TITLE_LINE = "Weekly Execution Review – Dr. Bits"
SUBTITLE_LINE = "Corporate Controls Engineer – Planta Aldama"
WINDOW_LINE = "Semana Ejecutiva L–J"  # Se complementa con la etiqueta real calculada

# =============== UTILIDADES DE FECHA/TZ ===================

def _tz():
    """Zona horaria corporativa."""
    return ZoneInfo("America/Monterrey")

def _now():
    """Datetime actual con TZ."""
    return datetime.now(_tz())

def _monday_of_iso_week(year: int, week: int) -> date:
    """Devuelve el lunes (date) de la semana ISO dada."""
    fourth_jan = date(year, 1, 4)
    # Semana ISO que contiene el 4 de enero siempre es la 1
    delta = timedelta(days=fourth_jan.isoweekday() - 1)
    first_monday = fourth_jan - delta
    return first_monday + timedelta(weeks=week - 1)

def _compute_window(hint: str | None, iso_str: str | None):
    """
    Ventana laboral corporativa: Lunes 05:00 a Jueves 17:00 (Mon-Thu).
    Retorna (start_dt_aware, end_dt_aware, etiqueta_str).
    - hint: "prev" | "this" | None
    - iso_str: "YYYY-Www" (tiene prioridad si viene)
    """
    now = _now()
    if iso_str:
        try:
            y, w = iso_str.split("-W")
            year, week = int(y), int(w)
            monday = _monday_of_iso_week(year, week)
        except Exception:
            monday = _monday_of_iso_week(*now.isocalendar()[:2])
    else:
        monday = _monday_of_iso_week(*now.isocalendar()[:2])
        if hint == "prev":
            monday = monday - timedelta(days=7)

    # Construir datetimes aware (con TZ)
    start_dt = datetime.combine(monday, time(5, 0)).replace(tzinfo=_tz())
    end_dt = datetime.combine(monday + timedelta(days=3), time(17, 0)).replace(tzinfo=_tz())

    etiqueta = f"{WINDOW_LINE} | {monday.isoformat()} 05:00 → {(monday + timedelta(days=3)).isoformat()} 17:00"
    return start_dt, end_dt, etiqueta

def _parse_ts(ts: str | None):
    """
    Convierte string ISO a datetime aware en la TZ corporativa.
    Si ts es None, regresa None.
    Soporta timestamps sin TZ (naive almacenados como texto ISO).
    """
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts)
    except Exception:
        return None
    # Si viene naive, hacer aware en TZ corporativa
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_tz())
    return dt

def _overlap_minutes(a_start, a_end, b_start, b_end) -> float:
    """
    Minutos de superposición entre [a_start, a_end] y [b_start, b_end].
    - Asegura que todo sea aware y no None.
    - Si a_end es None, usa _now().
    """
    if a_start is None:
        return 0.0
    if a_start.tzinfo is None:
        a_start = a_start.replace(tzinfo=_tz())

    if a_end is None:
        a_end = _now()
    elif a_end.tzinfo is None:
        a_end = a_end.replace(tzinfo=_tz())

    if b_start.tzinfo is None:
        b_start = b_start.replace(tzinfo=_tz())
    if b_end.tzinfo is None:
        b_end = b_end.replace(tzinfo=_tz())

    start = max(a_start, b_start)
    end = min(a_end, b_end)
    if end <= start:
        return 0.0
    return (end - start).total_seconds() / 60.0

# ========================= CONSULTAS ======================

def _fetch_week_data(app, start_dt, end_dt):
    """
    Regresa payload con:
      - cerrados (list[dict])
      - pendientes (list[dict])
      - horas_total (float)
      - horas_por_categoria/tecnologia/proyecto (dict)
      - mejor_exito (dict|None)
      - peor_obstaculo (dict|None)
      - kpis (dict)
    """
    db = get_db(app)
    cur = db.cursor()

    # Cerrados dentro de la ventana (por fecha_cierre)
    cur.execute("""
        SELECT s.id, s.project_id, s.numero_de_queja, s.nombre_subtarea,
               s.fecha_apertura, s.fecha_cierre,
               s.tiempo_objetivo_horas, s.categoria, s.tecnologia
        FROM subtasks s
        WHERE s.cerrado = 1
          AND s.fecha_cierre IS NOT NULL
          AND datetime(s.fecha_cierre) >= datetime(?)
          AND datetime(s.fecha_cierre) <= datetime(?)
        ORDER BY datetime(s.fecha_cierre) DESC;
    """, (start_dt.isoformat(), end_dt.isoformat()))
    cerrados_rows = cur.fetchall()

    # Pendientes anteriores a fin de ventana
    cur.execute("""
        SELECT s.id, s.project_id, s.numero_de_queja, s.nombre_subtarea,
               s.fecha_apertura, s.cerrado, s.categoria, s.tecnologia
        FROM subtasks s
        WHERE s.cerrado = 0
          AND datetime(s.fecha_apertura) <= datetime(?)
        ORDER BY datetime(s.fecha_apertura) ASC;
    """, (end_dt.isoformat(),))
    pendientes_rows = cur.fetchall()

    # Mapa último inicio para inactividad
    cur.execute("""
        SELECT t.subtask_id, MAX(t.inicio) AS ultimo_inicio
        FROM subtask_tiempo t
        GROUP BY t.subtask_id;
    """)
    last_map = {row["subtask_id"]: row["ultimo_inicio"] for row in cur.fetchall()}

    # Entradas de tiempo que cruzan la ventana
    cur.execute("""
        SELECT t.subtask_id, t.inicio, t.fin, s.categoria, s.tecnologia, s.project_id
        FROM subtask_tiempo t
        JOIN subtasks s ON s.id = t.subtask_id
        WHERE datetime(t.inicio) <= datetime(?)
          AND (t.fin IS NULL OR datetime(t.fin) >= datetime(?));
    """, (end_dt.isoformat(), start_dt.isoformat()))
    tiempos = cur.fetchall()

    # Acumuladores
    min_total = 0.0
    cat_map, tec_map, prj_map = {}, {}, {}

    # Sumar solapamiento con ventana
    for r in tiempos:
        t_ini = _parse_ts(r["inicio"])
        t_fin = _parse_ts(r["fin"]) if r["fin"] else None
        mins = _overlap_minutes(t_ini, t_fin, start_dt, end_dt)
        if mins <= 0:
            continue
        min_total += mins
        cat = r["categoria"] or "Sin categoría"
        tec = r["tecnologia"] or "Otro"
        prj = r["project_id"]
        cat_map[cat] = cat_map.get(cat, 0.0) + mins
        tec_map[tec] = tec_map.get(tec, 0.0) + mins
        prj_map[prj] = prj_map.get(prj, 0.0) + mins

    # Estructuras limpias para PDF
    cerrados = []
    for s in cerrados_rows:
        cerrados.append({
            "id": s["id"],
            "numero": s["numero_de_queja"],
            "nombre": s["nombre_subtarea"],
            "categoria": s["categoria"] or "Sin categoría",
            "tecnologia": s["tecnologia"] or "Otro",
            "objetivo": float(s["tiempo_objetivo_horas"] or 0.0),
            "apertura": s["fecha_apertura"],
            "cierre": s["fecha_cierre"],
        })

    pendientes = []
    for s in pendientes_rows:
        fa = _parse_ts(s["fecha_apertura"]) or start_dt
        dias_abierto = (end_dt.date() - fa.date()).days
        ultimo = last_map.get(s["id"])
        ult_dt = _parse_ts(ultimo)
        dias_sin_prog = (end_dt.date() - (ult_dt.date() if ult_dt else fa.date())).days
        pendientes.append({
            "id": s["id"],
            "numero": s["numero_de_queja"],
            "nombre": s["nombre_subtarea"],
            "categoria": s["categoria"] or "Sin categoría",
            "tecnologia": s["tecnologia"] or "Otro",
            "dias_abierto": dias_abierto,
            "dias_sin_prog": dias_sin_prog
        })

    # Mejor éxito técnico (cerrado con mejor score: cumplió objetivo y horas)
    mejor, best_score = None, None
    for s in cerrados:
        # Sumar horas de su tiempo en la ventana
        cur.execute("""
            SELECT inicio, fin
            FROM subtask_tiempo
            WHERE subtask_id = ?
              AND datetime(inicio) <= datetime(?)
              AND (fin IS NULL OR datetime(fin) >= datetime(?));
        """, (s["id"], end_dt.isoformat(), start_dt.isoformat()))
        rows = cur.fetchall()
        mins = 0.0
        for t in rows:
            ti = _parse_ts(t["inicio"])
            tf = _parse_ts(t["fin"]) if t["fin"] else None
            mins += _overlap_minutes(ti, tf, start_dt, end_dt)
        hrs = round(mins / 60.0, 2)
        obj = s["objetivo"]
        cumplio = (obj > 0 and hrs <= obj + 0.01)
        score = (100 if cumplio else 0) + hrs
        if best_score is None or score > best_score:
            best_score = score
            mejor = {
                "id": s["id"], "nombre": s["nombre"], "numero": s["numero"],
                "horas": hrs, "objetivo": obj, "cumplio": cumplio,
                "categoria": s["categoria"], "tecnologia": s["tecnologia"]
            }

    # Peor obstáculo: prioriza sin progreso + días abierto
    peor, worst_score = None, None
    for s in pendientes:
        score = s["dias_sin_prog"] * 10 + s["dias_abierto"]
        if worst_score is None or score > worst_score:
            worst_score = score
            peor = s

    # KPIs ejecutivos
    horas_total = round(min_total / 60.0, 2)
    execution_rate = round((len(cerrados) / max(1, len(cerrados) + len(pendientes))) * 100.0, 1)
    backlog_exposure = sum(1 for s in pendientes if s["dias_abierto"] >= 7)
    objetivo_total = sum(s["objetivo"] for s in cerrados)
    eficiencia = 0.0
    if objetivo_total > 0:
        # Eficiencia = objetivo_total / horas_usadas_en_cerrados
        cur.execute("""
            SELECT s.id, t.inicio, t.fin
            FROM subtasks s
            JOIN subtask_tiempo t ON t.subtask_id = s.id
            WHERE s.id IN (%s)
              AND datetime(t.inicio) <= datetime(?)
              AND (t.fin IS NULL OR datetime(t.fin) >= datetime(?));
        """ % ",".join("?" * len(cerrados)) if cerrados else "SELECT 1 WHERE 0", 
        tuple([s["id"] for s in cerrados] + [end_dt.isoformat(), start_dt.isoformat()]))
        rows = cur.fetchall() if cerrados else []
        mins_cerrados = 0.0
        for r in rows:
            ti = _parse_ts(r["inicio"]); tf = _parse_ts(r["fin"]) if r["fin"] else None
            mins_cerrados += _overlap_minutes(ti, tf, start_dt, end_dt)
        hrs_cerrados = mins_cerrados / 60.0
        eficiencia = round((objetivo_total / max(0.01, hrs_cerrados)) * 100.0, 1)

    kpis = {
        "horas_total": horas_total,
        "execution_rate": execution_rate,  # %
        "eficiencia_vs_obj": eficiencia,   # %
        "backlog_exposure_7d": backlog_exposure
    }

    return {
        "cerrados": cerrados,
        "pendientes": pendientes,
        "horas_por_categoria": {k: round(v/60.0, 2) for k, v in cat_map.items()},
        "horas_por_tecnologia": {k: round(v/60.0, 2) for k, v in tec_map.items()},
        "horas_por_proyecto": {str(k): round(v/60.0, 2) for k, v in prj_map.items()},
        "mejor_exito": mejor,
        "peor_obstaculo": peor,
        "kpis": kpis
    }

# ===================== RENDER PDF (Amazon-style) =====================

# Paleta Amazon-like
AZUL = colors.HexColor("#0073bb")
AZUL_SUAVE = colors.HexColor("#e6f2fa")
VERDE = colors.HexColor("#1a7f37")
ROJO = colors.HexColor("#d62828")
GRIS = colors.HexColor("#6c757d")
NEGRO = colors.black

def _title_bar(c, etiqueta: str):
    """Barra superior con títulos corporativos."""
    c.setFillColor(AZUL)
    c.rect(0, 735, 612, 40, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(24, 753, TITLE_LINE)
    c.setFont("Helvetica", 10)
    c.drawString(24, 740, f"{SUBTITLE_LINE} | {etiqueta}")

def _kpi_cell(c, x, y, w, h, title, value, accent=AZUL):
    """Tarjeta KPI minimalista."""
    c.setFillColor(AZUL_SUAVE)
    c.roundRect(x, y - h, w, h, 8, stroke=0, fill=1)
    c.setFillColor(accent)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(x + 10, y - 18, title)
    c.setFillColor(NEGRO)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(x + 10, y - 40, str(value))

# ============================================================
# 🎨 Paneles de listas con gutter y subrayado corporativo
# Sustituye tu _list_block por estas dos funciones
# ============================================================

def _panel_list_block(c, x, y_top, width, title, rows, max_items=8, accent=AZUL):
    """
    Dibuja una 'tarjeta' con:
      - Título y subrayado azul
      - Fondo suave y padding interno
      - Lista con bullets
    Devuelve la coordenada Y final (abajo del panel).
    """
    padding = 10                # espacio interno de la tarjeta
    line_height = 12            # alto de cada renglón de lista
    title_gap = 16              # espacio debajo del título
    max_width_title_line = width - (padding * 2)

    # Medimos la altura que usaremos según items visibles
    items_to_draw = rows[:max_items] if rows else []
    inner_list_height = max(1, len(items_to_draw)) * line_height
    inner_height = title_gap + inner_list_height
    panel_height = padding + 14 + 4 + inner_height + padding
    #  14: alto título; 4: margen/subrayado simbólico

    # Fondo del panel
    c.setFillColor(AZUL_SUAVE)
    c.roundRect(x, y_top - panel_height, width, panel_height, 8, stroke=0, fill=1)

    # Título
    c.setFillColor(NEGRO)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(x + padding, y_top - padding - 2, title)

    # Subrayado azul del título (dentro de la tarjeta)
    c.setStrokeColor(accent)
    c.setLineWidth(2)
    title_y = y_top - padding - 4
    c.line(x + padding, title_y - 4, x + padding + max_width_title_line, title_y - 4)

    # Lista
    c.setFont("Helvetica", 9)
    list_y = title_y - 4 - 10  # pequeño espacio tras el subrayado
    if not items_to_draw:
        c.setFillColor(GRIS)
        c.drawString(x + padding, list_y, "Sin información disponible")
        list_y -= line_height
    else:
        c.setFillColor(NEGRO)
        for r in items_to_draw:
            c.drawString(x + padding, list_y, f"• {r[:110]}")
            list_y -= line_height

    # Y final bajo el panel (+ respiro)
    return y_top - panel_height - 4

def _list_block(c, x, y, title, rows, max_items=8):
    """
    Compatibilidad: si algún llamado viejo usa _list_block,
    delegamos al nuevo panel con un ancho estándar de 272 px.
    """
    return _panel_list_block(c, x, y, 272, title, rows, max_items=max_items, accent=AZUL)


def _bar_block(c, x, y, title, data, maxw=240):
    """Barras horizontales compactas."""
    c.setFillColor(NEGRO)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(x, y, title)
    y -= 14
    if not data:
        c.setFont("Helvetica", 9); c.setFillColor(GRIS)
        c.drawString(x, y, "Sin datos"); return y - 12
    mx = max(data.values())
    c.setFont("Helvetica", 9)
    for k, v in sorted(data.items(), key=lambda kv: -kv[1])[:6]:
        w = 0 if mx == 0 else int((v / mx) * maxw)
        c.setFillColor(AZUL)
        c.rect(x, y - 8, w, 8, stroke=0, fill=1)
        c.setFillColor(NEGRO)
        c.drawString(x + w + 6, y - 7, f"{k[:20]} — {v} h")
        y -= 16
    return y

def _root_cause(peor):
    if not peor:
        return ("Semana estable", "Mantén el flujo y prepara backlog granular para Lunes.")
    ds = peor["dias_sin_prog"]; da = peor["dias_abierto"]
    if ds >= 5:
        return ("Falta de foco / bloqueos",
                "Divide en 3 subtareas de 1–2 h, bloquea 90 min diarios y cierra dependencias hoy.")
    if ds >= 3:
        return ("Interrupciones / alcance difuso",
                "Agenda bloque de foco, escribe micro-brief (3 bullets) y define objetivo cierre en 48 h.")
    return ("Complejidad media",
            "Aclara requerimientos, valida supuestos y establece objetivo SMART para próxima ventana.")

def _footer(c):
    c.setFillColor(GRIS)
    c.setFont("Helvetica-Oblique", 8)
    c.drawString(24, 28, "Bias for Action • Dive Deep • Deliver Results")
    c.drawRightString(588, 28, _now().strftime("Generado %Y-%m-%d %H:%M"))

def _build_pdf(app, payload, etiqueta, outdir="static/reports"):
    os.makedirs(outdir, exist_ok=True)
    fname = f"weekly_{_now().strftime('%Y%m%d_%H%M%S')}.pdf"
    path = os.path.join(outdir, fname)

    c = canvas.Canvas(path, pagesize=letter)
    w, h = letter

    # Header
    _title_bar(c, etiqueta)

    # KPIs (grid 2x2)
    k = payload["kpis"]
    _kpi_cell(c, 24, 710, 280, 56, "Total Hours", k["horas_total"], AZUL)
    _kpi_cell(c, 316, 710, 272, 56, "Execution Rate", f"{k['execution_rate']}%", VERDE)
    _kpi_cell(c, 24, 646, 280, 56, "Efficiency vs Target", f"{k['eficiencia_vs_obj']}%", AZUL)
    _kpi_cell(c, 316, 646, 272, 56, "Backlog Exposure (≥7d)", k["backlog_exposure_7d"], ROJO)

    # ================================
    # What went well / needs attention
    # ================================
    wins = [f"{s['nombre']}  ({s['categoria']})" for s in payload["cerrados"]]

    gaps = []
    for s in payload["pendientes"]:
        tag = "🔴" if s["dias_sin_prog"] >= 5 else ("🟠" if s["dias_sin_prog"] >= 3 else "🟡")
        gaps.append(f"{tag} {s['nombre']}  ({s['categoria']}) • {s['dias_sin_prog']}d sin progreso")

    # Dos columnas con gutter real
    col_w = 272
    gutter = 20
    left_x = 24
    right_x = left_x + col_w + gutter
    top_y = 590

    y_left  = _panel_list_block(c, left_x,  top_y, col_w, "✅ What went well", wins, max_items=8, accent=AZUL)
    y_right = _panel_list_block(c, right_x, top_y, col_w, "❌ What needs attention", gaps, max_items=8, accent=AZUL)

    # Punto de arranque para las barras: debajo del panel más largo
    ybars = min(y_left, y_right) - 18


    # Bars por categoría y tecnología
    # DESPUÉS
    ybars = _draw_bars(c, 24, ybars, payload["horas_por_categoria"], "⏱ Hours by Category")
    ybars = _draw_bars(c, 24, ybars - 12, payload["horas_por_tecnologia"], "🧠 Hours by Technology")


    # Root cause & Action
    # Root cause & Action Plan
    causa, accion = _root_cause(payload["peor_obstaculo"])

    # Root Cause
    c.setFillColor(NEGRO)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(316, ybars + 56, "🧩 Root Cause")
    c.setFillColor(AZUL)
    c.setLineWidth(2)
    c.line(316, ybars + 54, 316 + 240, ybars + 54)

    c.setFillColor(NEGRO)
    c.setFont("Helvetica", 9)
    c.drawString(316, ybars + 38, causa[:90])

    # Action Plan
    c.setFillColor(NEGRO)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(316, ybars + 20, "🚀 Action Plan")
    c.setFillColor(AZUL)
    c.line(316, ybars + 18, 316 + 240, ybars + 18)

    c.setFillColor(NEGRO)
    c.setFont("Helvetica", 9)
    c.drawString(316, ybars + 4, accion[:110])


    _footer(c)
    c.showPage()
    c.save()
    return path, fname

# ======================== RUTAS ===========================

@weekly_bp.route("/generate")
@login_required
def generate_weekly():
    """Genera el PDF ejecutivo y lo muestra inline."""
    hint = request.args.get("when")       # prev | this
    iso_str = request.args.get("iso")     # YYYY-Www

    start_dt, end_dt, etiqueta = _compute_window(hint, iso_str)
    payload = _fetch_week_data(current_app, start_dt, end_dt)
    path, fname = _build_pdf(current_app, payload, etiqueta)

    # Notificación en el sistema
    try:
        db = get_db(current_app); cur = db.cursor()
        cur.execute("INSERT INTO notifications (mensaje, fecha) VALUES (?, ?)",
                    (f"📄 Weekly Execution Review generado: {fname}", _now().isoformat()))
        db.commit()
    except Exception:
        pass

    return send_file(path, mimetype="application/pdf", as_attachment=False)

@weekly_bp.route("/ping")
@login_required
def ping():
    """Health check simple."""
    return jsonify({"ok": True, "service": "weekly", "tz": str(_tz())})



# ==========================================
# 🎨 Nuevo: Barras con Título Subrayado Azul
# ==========================================
def _draw_bars(c, x, y, data_dict, title, max_width=240, bar_h=12):
    """
    Dibuja barras horizontales con estilo corporativo.
    Devuelve la nueva coordenada y.
    """
    # Título
    c.setFillColor(NEGRO)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(x, y, title)

    # Subrayado azul corporativo
    c.setStrokeColor(AZUL)
    c.setLineWidth(2)
    c.line(x, y - 2, x + max_width + 120, y - 2)

    # Contenido
    y -= 18
    if not data_dict:
        c.setFillColor(GRIS)
        c.setFont("Helvetica-Oblique", 10)
        c.drawString(x, y, "Sin datos")
        return y - 20

    max_val = max(data_dict.values())
    c.setFont("Helvetica", 9)

    for k, v in sorted(data_dict.items(), key=lambda kv: -kv[1])[:7]:
        w = 0 if max_val == 0 else int((v / max_val) * max_width)
        c.setFillColor(AZUL)
        c.rect(x, y - bar_h + 2, w, bar_h, stroke=0, fill=1)
        c.setFillColor(NEGRO)
        c.drawString(x + w + 6, y - bar_h + 2, f"{k[:20]} — {v}h")
        y -= (bar_h + 6)

    return y
