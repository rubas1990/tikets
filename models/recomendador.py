# models/recomendador.py
from collections import Counter
import math
import re

def limpiar_texto(texto):
    """Limpieza básica de texto: minúsculas y sin caracteres raros."""
    if not texto:
        return ""
    texto = texto.lower()
    texto = re.sub(r'[^a-záéíóúñ0-9\s]', '', texto)
    return texto.strip()

def similitud_coseno(vec1, vec2):
    """Calcula similitud coseno entre dos vectores (TF)."""
    interseccion = set(vec1.keys()) & set(vec2.keys())
    num = sum(vec1[x] * vec2[x] for x in interseccion)
    den1 = math.sqrt(sum(v**2 for v in vec1.values()))
    den2 = math.sqrt(sum(v**2 for v in vec2.values()))
    return num / (den1 * den2) if den1 and den2 else 0

def vectorizar(texto):
    """Convierte texto en un vector TF simple."""
    palabras = limpiar_texto(texto).split()
    return Counter(palabras)

# models/recomendador.py
from datetime import datetime
from collections import Counter

def recomendar_similares(db, subtask_id: int):
    """
    Analiza la subtarea actual y devuelve sugerencias automáticas basadas en IA ligera.
    Incluye tiempo promedio por categoría, proyectos relacionados y palabras clave frecuentes.
    """
    cur = db.cursor()

    # 🔹 Obtener categoría del ticket actual
    cur.execute("SELECT categoria, project_id FROM subtasks WHERE id = ?;", (subtask_id,))
    row = cur.fetchone()
    if not row or not row["categoria"]:
        return {
            "tiempo_estimado": "—",
            "mejor_operador": "—",
            "tags": ["Sin categoría"],
            "categoria": "Otro",
            "proyectos_relacionados": []
        }

    categoria = row["categoria"]
    project_id = row["project_id"]

    # 🔹 Calcular tiempo promedio de cierre por categoría (en horas)
    cur.execute("""
        SELECT AVG((julianday(fecha_cierre) - julianday(fecha_apertura)) * 24) AS prom_horas
        FROM subtasks
        WHERE categoria = ? AND fecha_cierre IS NOT NULL;
    """, (categoria,))
    prom = cur.fetchone()["prom_horas"] or 0

    # 🔹 Buscar proyectos donde esta categoría aparece más
    cur.execute("""
        SELECT p.nombre, COUNT(*) AS cantidad
        FROM subtasks s
        JOIN projects p ON p.id = s.project_id
        WHERE s.categoria = ?
        GROUP BY p.id
        ORDER BY cantidad DESC
        LIMIT 3;
    """, (categoria,))
    proyectos_relacionados = [r["nombre"] for r in cur.fetchall()]

    # 🔹 Analizar palabras más comunes dentro de esta categoría
    cur.execute("""
        SELECT LOWER(nombre_subtarea) AS texto
        FROM subtasks
        WHERE categoria = ?;
    """, (categoria,))
    textos = [r["texto"] for r in cur.fetchall()]
    palabras = []
    for t in textos:
        palabras.extend([w for w in t.split() if len(w) > 4])
    comunes = [p for p, _ in Counter(palabras).most_common(5)]

    # 🔹 Mejor operador (el que más tickets cerró en esta categoría)
    cur.execute("""
        SELECT st.username, COUNT(*) AS total
        FROM subtask_tiempo st
        JOIN subtasks s ON s.id = st.subtask_id
        WHERE s.categoria = ?
        GROUP BY st.username
        ORDER BY total DESC
        LIMIT 1;
    """, (categoria,))
    operador = cur.fetchone()
    mejor_operador = operador["username"] if operador else "—"

    # 🔹 Redondear estimado
    tiempo_estimado = round(prom, 2) if prom else "—"

    return {
        "tiempo_estimado": tiempo_estimado,
        "mejor_operador": mejor_operador,
        "tags": comunes or ["Sin datos"],
        "categoria": categoria,
        "proyectos_relacionados": proyectos_relacionados
    }
