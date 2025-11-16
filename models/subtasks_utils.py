# models/subtasks_utils.py
from models import get_db
from models.subtasks import create_subtask  # 🔹 Reusamos la función original
from models.predictor_tiket import analizar_tiket

def create_subtask_with_metadata(app, project_id, nombre, tiempo_objetivo_horas, tecnologia, dificultad, kr, username):
    """
    Crea una subtarea completa reutilizando la función base y agregando campos extendidos.
    """
    db = get_db(app)
    cur = db.cursor()

    # 1️⃣ Crear subtarea base (genera número incremental y categoría)
    subtask_id = create_subtask(app, project_id, nombre, tiempo_objetivo_horas)
    if not subtask_id:
        return None, None

    # 2️⃣ Guardar campos adicionales
    cur.execute("""
        UPDATE subtasks
        SET tecnologia=?, dificultad=?, kr=?
        WHERE id=?;
    """, (tecnologia, dificultad, kr, subtask_id))
    db.commit()

    # 3️⃣ Ejecutar IA predictiva
    analisis = None
    try:
        analisis = analizar_tiket(app, project_id, subtask_id, username)
    except Exception as e:
        print(f"[IA] Error en análisis predictivo: {e}")

    return subtask_id, analisis
