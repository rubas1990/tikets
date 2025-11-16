import re
import sqlite3
import difflib
from unidecode import unidecode

def limpiar_texto(texto: str) -> str:
    if not texto:
        return ""
    t = unidecode(texto.strip().lower())
    t = re.sub(r"\[.*?\]\s*ruben:.*?(?=\[|$)", "", t)
    t = re.sub(r"\b(ejemplo|test|prueba|probando)\b", "", t)
    t = re.sub(r"[\(\)\[\]\-_/]+", " ", t)
    t = re.sub(r"\s{2,}", " ", t)
    return t.strip()

def normalizar_categoria(cat: str) -> str:
    if not cat: return "Otro"
    cat = cat.lower()
    if "manten" in cat: return "Mantenimiento / falla"
    if "control" in cat or "plc" in cat: return "Control / automatización"
    if "reporte" in cat or "pdf" in cat: return "Reportes / documentos"
    if "comun" in cat or "correo" in cat: return "Comunicación / usuarios"
    if "ajust" in cat or "desarrollo" in cat: return "Desarrollo / ajustes"
    return "Otro"

def normalizar_tecnologia(tec: str) -> str:
    if not tec: return "Otro"
    tec = tec.strip().capitalize()
    mapping = {
        "flask": "Flask",
        "python": "Python",
        "sql server": "SQL Server",
        "php": "PHP",
        "bootstrap": "Bootstrap",
        "plc": "PLC",
    }
    return mapping.get(tec.lower(), tec)

def normalizar_kr(kr: str) -> str:
    if not kr:
        return "Sin definir"

    # 🔹 Normaliza acentos, espacios y minúsculas
    k = unidecode(kr.strip().lower())

    # 🔹 Lista maestra de KR válidos
    base_kr = [
        "ux pro",
        "python analisis",
        "sql avanzado",
        "etl industrial",
        "dashboards",
        "automatizacion",
        "automatizacion industrial",
        "design system",
        "tablet ready",
        "data kr1",
        "data kr4",
        "innov kr1",
        "integracion industrial",
        "alertas inteligentes",
        "integracion maquina y sistema",
    ]

    # 🔹 Busca coincidencias cercanas (tolerancia difusa)
    match = difflib.get_close_matches(k, base_kr, n=1, cutoff=0.6)

    if match:
        # Devuelve capitalizado bonito
        return " ".join(w.capitalize() for w in match[0].split())

    # Si no hay match razonable, deja título simple
    return " ".join(w.capitalize() for w in k.split())

def limpiar_tabla(path_db="soporte.db"):
    conn = sqlite3.connect(path_db)
    cur = conn.cursor()

    cur.execute("SELECT id, nombre_subtarea, categoria, tecnologia, kr, comentarios FROM subtasks")
    filas = cur.fetchall()

    for f in filas:
        id_, subtarea, cat, tec, kr, com = f
        subtarea_limpia = limpiar_texto(subtarea)
        cat_norm = normalizar_categoria(cat)
        tec_norm = normalizar_tecnologia(tec)
        kr_norm = normalizar_kr(kr)
        com_limpio = limpiar_texto(com)

        cur.execute("""
            UPDATE subtasks
            SET nombre_subtarea=?, categoria=?, tecnologia=?, kr=?, comentarios=?
            WHERE id=?;
        """, (subtarea_limpia, cat_norm, tec_norm, kr_norm, com_limpio, id_))

    conn.commit()
    conn.close()
    print("✅ KR ahora normalizados con coincidencia difusa.")

if __name__ == "__main__":
    limpiar_tabla()
