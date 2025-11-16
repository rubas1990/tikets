# routes/para_hoy.py
# -------------------------------------------
# Vista y API para la Agenda Predictiva "Para hoy"
# - GET /para_hoy           : render de la página
# - GET /api/para_hoy       : JSON con recomendaciones
#
# Dependencias:
# - auth.login_required
# - models.db.get_db
# - usa tz America/Monterrey
# -------------------------------------------

from flask import Blueprint, render_template, request, jsonify, current_app, session
from auth import login_required
from models.db import get_db
from datetime import datetime
import pytz

para_hoy_bp = Blueprint('para_hoy', __name__)

def _safe_div(a, b):
    """Evita división por cero devolviendo 0 si b==0."""
    return (a / b) if b else 0.0

def _normalizar_prioridad(p):
    """
    Normaliza prioridad de proyecto a [0,1].
    Asume 1..3 (baja..alta). Ajusta si usas 1..5.
    """
    try:
        p = int(p or 1)
    except:
        p = 1
    minimo, maximo = 1, 3  # Cambia a (1,5) si tu escala es 1..5
    return (p - minimo) / (maximo - minimo) if maximo > minimo else 0.0

def _dias_sin_tocar(ultimo_iso, tz):
    """
    Recibe ISO string de última actividad; si None, considera 'olvidada' (10 días).
    """
    if not ultimo_iso:
        return 10
    try:
        dt = datetime.fromisoformat(ultimo_iso)
        if dt.tzinfo is None:
            dt = tz.localize(dt)
    except:
        return 10
    hoy = datetime.now(tz)
    return max(0, (hoy - dt).days)






def _tiempo_sugerido_horas(score):
    """
    Tiempo sugerido en horas.
    - Por defecto 8 h si no hay score.
    - A mayor score, sugiere bloques más enfocados pero realistas (entre 1 y 3 h).
    """
    if score is None:
        return 8
    # Mapear score a rango [1, 3] horas, con piso 1h, techo 3h.
    # Puedes afinar esta curva sin tocar el front.
    s = max(0.0, min(10.0, score))  # acotar score
    return max(1, min(3, round(1 + (s / 10) * 2)))  # 1..3 horas

@para_hoy_bp.route('/para_hoy')
@login_required
def para_hoy_view():
    """
    Renderiza la página principal. No calcula; el JS llama a /api/para_hoy.
    """
    # Lee 'n' desde query o usa 8 por defecto
    try:
        n = int(request.args.get('n', 8))
    except:
        n = 8
    # Última actualización se muestra en cliente, pero lo mandamos inicial
    return render_template('para_hoy.html', default_n=n)




@para_hoy_bp.route('/api/para_hoy')
@login_required
def para_hoy_api():
    """
    Devuelve lista priorizada para la agenda predictiva.
    Orden inteligente (Opción 2): Prioridad + Atraso + Olvido + Antigüedad.
    """
    tz = pytz.timezone("America/Monterrey")
    username = session.get('username') or session.get('user') or 'anon'

    try:
        limit = int(request.args.get('n', 8))
    except:
        limit = 8

    db = get_db(current_app)
    cur = db.cursor()

    # =======================================
    # 1) Subtareas abiertas del usuario (por actividad en subtask_tiempo)
    #    Incluimos fecha_apertura en el SELECT para evitar N consultas.
    # =======================================
    cur.execute("""
SELECT
    s.id AS subtask_id,
    s.nombre_subtarea,
    s.cerrado,
    s.tiempo_objetivo_horas,
    s.prioridad AS subtask_prioridad,
    s.fecha_apertura AS subtask_fecha_apertura,
    p.id AS project_id,
    p.nombre AS project_nombre,
    p.prioridad AS project_prioridad,
    p.numero_de_queja,
    p.status AS project_status
FROM subtasks s
JOIN projects p ON p.id = s.project_id
WHERE
    p.status != 'Cerrado'
    AND s.cerrado = 0



    """)


    subtareas = cur.fetchall()

    # =======================================
    # 2) Minutos trabajados por subtarea
    # =======================================
    cur.execute("""
        SELECT subtask_id, SUM(duracion_min) AS total_min
        FROM subtask_tiempo
        GROUP BY subtask_id
    """)
    tiempos_map = {r['subtask_id']: (r['total_min'] or 0) for r in cur.fetchall()}

    # =======================================
    # 3) Última actividad por subtarea
    # =======================================
    cur.execute("""
        SELECT subtask_id, MAX(COALESCE(fin, inicio)) AS last_activity
        FROM subtask_tiempo
        GROUP BY subtask_id
    """)
    ultimo_map = {r['subtask_id']: r['last_activity'] for r in cur.fetchall()}

    recomendaciones = []

    for r in subtareas:
        sub_id = r['subtask_id']

        

        # 🔥 Avance real (0..1)
        mins = tiempos_map.get(sub_id, 0)
        horas_trab = mins / 60
        horas_obj = float(r['tiempo_objetivo_horas'] or 0)
        avance = (horas_trab / horas_obj) if horas_obj > 0 else 0
        avance = max(0.0, min(1.0, round(avance, 2)))

        # 🧊 Días sin tocar
        last_iso = ultimo_map.get(sub_id)
        if last_iso:
            try:
                dt = datetime.fromisoformat(last_iso)
                if dt.tzinfo is None:
                    dt = tz.localize(dt)
                dias_sin_tocar = max(0, (datetime.now(tz) - dt).days)
            except:
                dias_sin_tocar = 10
        else:
            dias_sin_tocar = 10

        # ⌛ Antigüedad (días desde apertura)
        fa = r['subtask_fecha_apertura']
        try:
            apertura_dt = datetime.fromisoformat(fa) if isinstance(fa, str) else fa
            if apertura_dt and apertura_dt.tzinfo is None:
                apertura_dt = tz.localize(apertura_dt)
            antiguedad_dias = max(0, (datetime.now(tz) - apertura_dt).days) if apertura_dt else 0
        except:
            antiguedad_dias = 0

        # 🔺 Normalizar prioridad del proyecto (manejo especial N/A)
        raw_prio = (r['project_prioridad'] or '').strip().lower()

        if raw_prio in ("", "na", "n/a", "ninguna"):
            # 🔽 Sin prioridad → al fondo de la lista
            prioridad_norm = -1  
        else:
            # ✅ Normalizar prioridad del proyecto realmente corporativa
            raw_prio = (r['project_prioridad'] or '').strip().lower()

            map_prio = {
                'alta': 3, 'high': 3, '3': 3,
                'media': 2, 'medio': 2, 'medium': 2, '2': 2,
                'baja': 1, 'low': 1, '1': 1
            }

            pprio = map_prio.get(raw_prio, None)

            if pprio is None:
                # ❌ Sin prioridad → empujar abajo
                prioridad_norm = -1
            else:
                prioridad_norm = (pprio - 1) / (3 - 1)



        # 🎯 Pesos del modelo balanceado (Opción 2)
        peso_prioridad = 10
        peso_atraso = 7
        peso_olvido = 4
        peso_antiguedad = 2

        # ✅ Score final
        score = (
            (peso_prioridad * prioridad_norm) +
            (peso_atraso * (1 - avance)) +
            (peso_olvido * dias_sin_tocar) +
            (peso_antiguedad * antiguedad_dias)
        )
        # ❌ Penalizar fuerte tareas sin prioridad
        if prioridad_norm < 0:
            score -= 100
        # ✅ Agregar recomendación
        recomendaciones.append({
    "subtask_id": sub_id,
    "project_id": r['project_id'],
    "proyecto": r['project_nombre'],
    "subtarea": r['nombre_subtarea'],
    "dias_sin_tocar": dias_sin_tocar,
    "avance": avance,
    "project_status": r['project_status'],
    "score": round(score, 2),
    "tiempo_sugerido_horas": max(1, min(3, round(1 + (score/10)*2))),
    "prioridad": prioridad_norm  # ✅ Para el frontend (0..1 o -1)
})


    # =======================================
    # 📈 Cálculo de impacto semanal estimado
    # =======================================
    total_obj = 0.0
    total_trab = 0.0
    for rr in subtareas:
        sid = rr['subtask_id']
        mins = tiempos_map.get(sid, 0)
        htrab = mins / 60
        hobj = float(rr['tiempo_objetivo_horas'] or 0)
        total_trab += htrab
        total_obj += hobj

    impacto_actual = (total_trab / total_obj) if total_obj > 0 else 0.0
    aporte_potencial = sum(1 - rec['avance'] for rec in recomendaciones if rec['avance'] < 1)
    impacto_potencial = impacto_actual + (aporte_potencial / total_obj if total_obj > 0 else 0)

    # 📌 Ordenar y limitar resultados ✅ AHORA SÍ FUERA DEL FOR
    recomendaciones.sort(key=lambda x: x['score'], reverse=True)
    recomendaciones = recomendaciones[:limit]

    # ✅ Nuevo formato esperado por el JS
    impacto = {
        "antes_pct": round(impacto_actual * 100),
        "despues_pct": round(impacto_potencial * 100)
    }

    return jsonify({
        "ok": True,
        "items": recomendaciones,
        "impacto": impacto,
        "generated_at": datetime.now(tz).isoformat()
    })
