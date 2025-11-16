# models/estado_emocional.py
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import pytz

def evaluar_fatiga_operador(db, username):
    """
    Analiza las últimas tareas del operador y devuelve un estado emocional aproximado.
    Si ha trabajado varias subtareas sin descanso o con tiempos largos, sugiere pausa.
    """
    tz = ZoneInfo("America/Monterrey")
    cur = db.cursor()

    # 🔹 Últimas sesiones de tiempo registradas
    cur.execute("""
        SELECT subtask_id, inicio, fin, duracion_min
        FROM subtask_tiempo
        WHERE username = ?
        ORDER BY inicio DESC
        LIMIT 10;
    """, (username,))
    sesiones = cur.fetchall()

    if not sesiones:
        return {"estado": "😴 Sin actividad reciente", "mensaje": "No hay sesiones registradas."}

    # 🔹 Calcular cuántas ha hecho sin descanso (fin muy cercano al inicio siguiente)
    seguidas = 1
    for i in range(len(sesiones) - 1):
        fin_actual = sesiones[i]["fin"]
        inicio_siguiente = sesiones[i + 1]["inicio"]
        if fin_actual and inicio_siguiente:
            fin_dt = datetime.fromisoformat(fin_actual).astimezone(tz)
            ini_dt = datetime.fromisoformat(inicio_siguiente).astimezone(tz)
            diff = abs((fin_dt - ini_dt).total_seconds()) / 60
            if diff < 15:  # menos de 15 minutos entre sesiones
                seguidas += 1
            else:
                break

    total_min = sum(s["duracion_min"] or 0 for s in sesiones[:seguidas])
    total_horas = round(total_min / 60, 1)

    # 🔹 Evaluar estado emocional simple
    if seguidas >= 5 or total_horas > 6:
        estado = "🚨 Fatiga alta"
        mensaje = f"Has trabajado {seguidas} tareas seguidas (~{total_horas}h). Tómate un descanso ☕."
    elif seguidas >= 3 or total_horas > 3:
        estado = "⚠️ Estrés leve"
        mensaje = f"Llevas {seguidas} tareas continuas. Una pausa corta podría ayudarte 🧘."
    else:
        estado = "😊 En equilibrio"
        mensaje = "Buen ritmo de trabajo. Mantén tus pausas regulares 💪."

    return {
        "estado": estado,
        "mensaje": mensaje,
        "tareas_seguidas": seguidas,
        "horas_totales": total_horas
    }


def resumen_emocional_por_categoria(db, dias=7):
    """Promedio de horas trabajadas por categoría (últimos N días)."""
    cur = db.cursor()
    cur.execute("""
        SELECT categoria,
               ROUND(AVG(horas_trabajadas), 2) AS prom_horas,
               COUNT(DISTINCT fecha) AS dias_registrados
        FROM emocional_log
        WHERE date(fecha) >= date('now', ? || ' day')
        GROUP BY categoria
        ORDER BY prom_horas DESC;
    """, (f"-{dias}",))
    return cur.fetchall()


def historial_categoria(db, categoria, dias=7):
    """Devuelve el historial diario de una categoría específica."""
    cur = db.cursor()
    cur.execute("""
        SELECT fecha, ROUND(AVG(horas_trabajadas), 2) AS horas_promedio
        FROM emocional_log
        WHERE categoria = ?
          AND date(fecha) >= date('now', ? || ' day')
        GROUP BY fecha
        ORDER BY fecha ASC;
    """, (categoria, f"-{dias}"))
    return cur.fetchall()


def registrar_estado_emocional_diario(db):
    """
    Calcula y guarda un resumen emocional diario por usuario y categoría
    según las horas trabajadas en subtareas.
    """
    cur = db.cursor()

    # 📆 Fecha local de hoy
    tz = pytz.timezone("America/Monterrey")
    fecha_hoy = datetime.now(tz).strftime("%Y-%m-%d")

    # 🔍 Verificar si ya existen registros del día
    cur.execute("SELECT COUNT(*) AS c FROM emocional_log WHERE date(fecha)=?", (fecha_hoy,))
    if cur.fetchone()["c"] > 0:
        print("[emocional] Ya existen registros de hoy, no se duplican.")
        return

    # 🔹 Obtener trabajo del día agrupado por usuario y categoría
    cur.execute("""
        SELECT 
            t.username,
            s.categoria,
            SUM(t.duracion_min)/60.0 AS horas_trabajadas,
            COUNT(DISTINCT t.subtask_id) AS tareas_seguidas
        FROM subtask_tiempo t
        JOIN subtasks s ON s.id = t.subtask_id
        WHERE date(t.inicio) = date('now', 'localtime')
        GROUP BY t.username, s.categoria;
    """)
    rows = cur.fetchall()
    if not rows:
        print("[emocional] No se encontraron actividades para hoy.")
        return

    total_registros = 0
    for r in rows:
        username = r["username"] or "desconocido"
        categoria = r["categoria"] or "Otro"
        horas = round(r["horas_trabajadas"] or 0, 2)
        tareas = r["tareas_seguidas"] or 0

        # 🔹 Calcular nivel de fatiga
        if horas < 2:
            nivel = "Bajo"
            mensaje = f"Buen ritmo, {username} mantiene energía óptima ✅"
        elif horas < 5:
            nivel = "Moderado"
            mensaje = f"Actividad sostenida ({horas}h) en {categoria}. Considera un descanso 🧘."
        else:
            nivel = "Alto"
            mensaje = f"⚠️ Jornada intensa ({horas}h) en {categoria}. ¡Tómate un respiro!"

        # 💾 Guardar en emocional_log
        cur.execute("""
            INSERT INTO emocional_log (fecha, username, categoria, horas_trabajadas, tareas_seguidas, nivel_fatiga, estado_emocional, mensaje)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """, (fecha_hoy, username, categoria, horas, tareas, nivel, nivel, mensaje))
        total_registros += 1

        print(f"[emocional] {fecha_hoy} | {username} → {categoria}: {horas}h → {nivel}")

    db.commit()
    print(f"[emocional] {total_registros} registros emocionales agregados ✅")





def regenerar_emocional_desde_historial(db, dias=30):
    """
    Genera registros emocionales retroactivos (últimos N días)
    basados en el historial real de trabajo de subtask_tiempo.
    """
    cur = db.cursor()

    # Limpia posibles duplicados previos (opcional)
    cur.execute("DELETE FROM emocional_log WHERE date(fecha) >= date('now', ? || ' day');", (f"-{dias}",))

    # 🔹 Inserta datos completos
    cur.execute("""
        INSERT INTO emocional_log (fecha, username, categoria, horas_trabajadas, tareas_seguidas, nivel_fatiga, estado_emocional, mensaje)
        SELECT 
            date(t.inicio) AS fecha,
            COALESCE(t.username, 'desconocido') AS username,
            COALESCE(s.categoria, 'Sin categoría') AS categoria,
            ROUND(SUM(t.duracion_min) / 60.0, 2) AS horas_trabajadas,
            COUNT(DISTINCT t.subtask_id) AS tareas_seguidas,
            CASE
                WHEN SUM(t.duracion_min) / 60.0 >= 6 THEN 'Alta'
                WHEN SUM(t.duracion_min) / 60.0 >= 3 THEN 'Media'
                ELSE 'Baja'
            END AS nivel_fatiga,
            CASE
                WHEN SUM(t.duracion_min) / 60.0 >= 6 THEN 'Fatiga alta'
                WHEN SUM(t.duracion_min) / 60.0 >= 3 THEN 'Estable'
                ELSE 'Relajado'
            END AS estado_emocional,
            CASE
                WHEN SUM(t.duracion_min) / 60.0 >= 6 THEN '⚠️ Exceso de trabajo. Recomendado descansar.'
                WHEN SUM(t.duracion_min) / 60.0 >= 3 THEN '💡 Actividad moderada. Mantén pausas cortas.'
                ELSE '✅ Ritmo saludable. Buen equilibrio.'
            END AS mensaje
        FROM subtask_tiempo t
        JOIN subtasks s ON s.id = t.subtask_id
        WHERE date(t.inicio) >= date('now', ? || ' day')
        GROUP BY date(t.inicio), t.username, s.categoria;
    """, (f"-{dias}",))

    db.commit()
    print(f"[ok] Datos emocionales regenerados ({dias} días atrás)")
