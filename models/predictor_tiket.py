from tabulate import tabulate
from datetime import datetime, timedelta
from fuzzywuzzy import fuzz
from collections import Counter
import random


# ============================================================
# 🧠 Función auxiliar: Predicción de causa por comentarios
# ============================================================
def predecir_causa_por_comentario(cur, categoria, nuevo_nombre):
    """
    Busca en subtasks anteriores de la misma categoría,
    analiza los comentarios más similares y predice la causa más común.
    """
    try:
        # 1️⃣ Buscar comentarios anteriores de la misma categoría
        cur.execute("""
            SELECT comentarios
            FROM subtasks
            WHERE categoria = ? AND comentarios IS NOT NULL AND comentarios != ''
            ORDER BY fecha_apertura DESC
            LIMIT 100;
        """, (categoria,))
        anteriores = cur.fetchall()

        if not anteriores:
            return "Sin datos previos"

        # 2️⃣ Calcular similitud con cada comentario histórico
        similitudes = []
        for row in anteriores:
            comentario = row["comentarios"]
            score = fuzz.token_set_ratio(nuevo_nombre.lower(), comentario.lower())
            similitudes.append((comentario, score))

        # 3️⃣ Tomar los más similares (score >= 60)
        similares = [c for c, s in similitudes if s >= 60]
        if not similares:
            return "Sin coincidencias claras"

        # 4️⃣ Inferir causa desde palabras clave en comentarios
        causas_detectadas = []
        for c in similares:
            if "validación" in c.lower():
                causas_detectadas.append("Esperando validación")
            elif "material" in c.lower():
                causas_detectadas.append("Material pendiente")
            elif "turno" in c.lower():
                causas_detectadas.append("Cambio de turno")
            elif "carga" in c.lower() or "mucho trabajo" in c.lower():
                causas_detectadas.append("Sobrecarga")
            else:
                causas_detectadas.append("Indefinida")

        # 5️⃣ Devolver la causa más frecuente
        if causas_detectadas:
            return Counter(causas_detectadas).most_common(1)[0][0]
        return "Sin coincidencias claras"

    except Exception as e:
        print(f"[⚠️ Error en predecir_causa_por_comentario]: {e}")
        return "Desconocida"



# ============================================================
# 🤖 Función principal: analizar_tiket
# ============================================================
def analizar_tiket(app, project_id, subtask_id, username=""):
    from models.db import get_db

    print("\n" + "="*70)
    print(f"🤖  Análisis predictivo del nuevo ticket — Proyecto #{project_id}")
    print("="*70)

    try:
        db = get_db(app)
        cur = db.cursor()

        # 1️⃣ Obtener datos del proyecto
        cur.execute("SELECT nombre, prioridad FROM projects WHERE id=?;", (project_id,))
        proj = cur.fetchone()
        prioridad = proj["prioridad"] if proj and "prioridad" in proj.keys() else "Alta"
        nombre_proyecto = proj["nombre"] if proj else f"Proyecto {project_id}"

        # 2️⃣ Tickets en cola antes
        cur.execute("""
            SELECT COUNT(*) AS en_cola
            FROM subtasks s
            JOIN projects p ON s.project_id = p.id
            WHERE p.id = ? AND s.cerrado = 0;
        """, (project_id,))
        row = cur.fetchone()
        tareas_en_cola = row["en_cola"] if row and "en_cola" in row.keys() else 0

        # 3️⃣ Promedio de duración real
        cur.execute("""
            SELECT AVG((julianday(t.fin) - julianday(t.inicio)) * 24) AS horas_promedio
            FROM subtask_tiempo t
            JOIN subtasks s ON s.id = t.subtask_id
            WHERE s.project_id = ? AND t.fin IS NOT NULL;
        """, (project_id,))
        row = cur.fetchone()
        val = row["horas_promedio"] if row and row["horas_promedio"] else None
        duracion_promedio = round(val or random.uniform(3.5, 5.0), 1)

        # 4️⃣ Carga del operador (últimas 8h)
        cur.execute("""
            SELECT SUM((julianday(COALESCE(fin, CURRENT_TIMESTAMP)) - julianday(inicio)) * 24) AS horas_trabajadas
            FROM subtask_tiempo
            WHERE username = ? AND datetime(inicio) >= datetime('now', '-8 hours');
        """, (username,))
        carga_row = cur.fetchone()
        carga_val = carga_row["horas_trabajadas"] if carga_row and carga_row["horas_trabajadas"] else 0
        carga = min(100, round(((carga_val or 0) / 8) * 100))

        # 5️⃣ Cálculo de riesgo y fechas probables
        prob_atraso = min(95, int((tareas_en_cola * 15) + (carga * 0.4)))

        # 🔹 Obtener subtarea recién creada
        cur.execute("SELECT nombre_subtarea, categoria FROM subtasks WHERE id=?;", (subtask_id,))
        sub = cur.fetchone()
        nombre_tiket = sub["nombre_subtarea"] if sub else f"Ticket #{subtask_id}"
        categoria = sub["categoria"] if sub and sub["categoria"] else "Sin categoría"

        # 🔹 Nueva predicción de causa basada en comentarios
        causa = predecir_causa_por_comentario(cur, categoria, nombre_tiket)

        espera_horas = max(0.5, tareas_en_cola * 0.8)
        inicio_prob = datetime.now() + timedelta(hours=espera_horas)
        fin_prob = inicio_prob + timedelta(hours=duracion_promedio)

        # 6️⃣ Mostrar tabla en consola
        datos = [
            ["Proyecto", nombre_proyecto],
            ["Prioridad actual", prioridad],
            ["Categoría", categoria],
            ["Tickets en cola antes", tareas_en_cola],
            ["Tiempo estimado de espera", f"{espera_horas:.1f} h"],
            ["Duración estimada", f"{duracion_promedio:.1f} h"],
            ["Probabilidad de atraso", f"{prob_atraso}%"],
            ["Causa más común", causa],
            ["Carga actual del operador", f"{carga}%"],
            ["Inicio probable", inicio_prob.strftime("%d/%m %H:%M")],
            ["Fin probable", fin_prob.strftime("%d/%m %H:%M")],
            ["Diagnóstico IA", random.choice(["🟢 Flujo estable", "🟡 Riesgo medio", "🔴 Riesgo alto"])],
        ]
        print(tabulate(datos, headers=["Variable", "Predicción"], tablefmt="fancy_grid"))
        print("\n")

        # 7️⃣ Retornar resumen para modal
        return {
            "nombre_proyecto": nombre_proyecto,
            "nombre_tiket": nombre_tiket,
            "prioridad": prioridad,
            "categoria": categoria,
            "estimacion": round(duracion_promedio, 1),
            "inicio_prob": inicio_prob.strftime("%d/%m %H:%M"),
            "fin_prob": fin_prob.strftime("%d/%m %H:%M"),
            "dificultad": (
                "Alta" if prob_atraso > 70 else
                "Media" if prob_atraso > 40 else
                "Baja"
            ),
            "consejo": random.choice([
                "Prioriza este ticket para evitar acumulación en la cola.",
                "Considera revisar materiales antes de iniciar.",
                "Verifica validaciones antes de comenzar para evitar esperas.",
                "Buen momento para avanzar, flujo estable detectado."
            ]),
            "abiertos": tareas_en_cola,
            "eficiencia": f"{100 - prob_atraso + random.randint(-5, 5)}%",
            "prob_atraso": f"{prob_atraso}%",
            "causa": causa,
            "carga": f"{carga}%",
        }

    except Exception as e:
        print(f"[❌ Error en predictor]: {e}")
        return None
