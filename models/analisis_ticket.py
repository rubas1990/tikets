# models/analisis_ticket.py
from datetime import datetime, timedelta

def analizar_nueva_subtarea(db, username, nombre_subtarea, prioridad):
    """
    Genera un análisis automático al crear una subtarea.
    Retorna un dict con los campos del 'coach industrial'.
    """
    cur = db.cursor()

    # 1️⃣ Categoría detectada (según palabra clave)
    cur.execute("SELECT palabra, categoria FROM categoria_reglas;")
    reglas = cur.fetchall()
    categoria = "Sin categoría"
    texto = nombre_subtarea.lower()
    for r in reglas:
        if r["palabra"] in texto:
            categoria = r["categoria"]
            break

    # 2️⃣ Carga actual del usuario (tickets abiertos)
    cur.execute("""
        SELECT COUNT(*) AS abiertos
        FROM subtasks
        WHERE username = ? AND status != 'Cerrado';
    """, (username,))
    abiertos = cur.fetchone()["abiertos"]

    # 3️⃣ Desempeño semanal
    semana_inicio = (datetime.now() - timedelta(days=datetime.now().weekday())).date()
    cur.execute("""
        SELECT AVG(tiempo_trabajado / NULLIF(tiempo_objetivo, 0)) AS eficiencia
        FROM subtasks
        WHERE username = ? AND date(fecha_creacion) >= date(?);
    """, (username, semana_inicio))
    eficiencia = cur.fetchone()["eficiencia"] or 1.0

    # 4️⃣ Predicción heurística de duración
    prioridad = prioridad.upper()
    if prioridad in ["1", "ALTA"]:
        base_horas = 2
    elif prioridad in ["2", "3"]:
        base_horas = 4
    elif prioridad in ["4", "5"]:
        base_horas = 8
    else:
        base_horas = 16  # N/A → 2 días aprox

    # Ajustar según carga y desempeño
    factor_carga = 1 + (abiertos * 0.05)
    factor_eficiencia = 1 / max(eficiencia, 0.5)
    estimacion = base_horas * factor_carga * factor_eficiencia

    # 5️⃣ Generar texto de advertencia y consejo
    if estimacion < 3:
        dificultad = "Baja"
        consejo = "Trabajo ligero, podrás completarlo sin contratiempos."
    elif estimacion < 7:
        dificultad = "Media"
        consejo = "Organiza bien tu tiempo y mantén foco en la ejecución."
    else:
        dificultad = "Alta"
        consejo = "Planea pausas y revisa los recursos antes de iniciar."

    return {
        "categoria": categoria,
        "estimacion": round(estimacion, 1),
        "dificultad": dificultad,
        "consejo": consejo,
        "abiertos": abiertos,
        "eficiencia": round(eficiencia, 2)
    }
