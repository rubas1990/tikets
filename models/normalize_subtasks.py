import re
from unidecode import unidecode
from models.db import get_db

import re
from unidecode import unidecode
from models.db import get_db


def categorizar_subtarea(texto: str, app=None) -> str:
    """
    Clasifica una subtarea según las palabras definidas en la tabla 'categoria_reglas'.
    🔹 Ignora texto entre paréntesis para evitar sesgos contextuales.
    🔹 Mantiene trazas de depuración con coincidencias.
    🔹 Aplica reglas contextuales (ej. 'error en dashboard' → Desarrollo / ajustes).
    🔹 Resuelve conflictos por prioridad predefinida.
    """
    if not texto:
        return "Otro"

    import re
    from unidecode import unidecode
    from models import get_db

    # 🧹 1️⃣ Limpieza y normalización
    t_original = texto
    t_sin_parentesis = re.sub(r"\(.*?\)", "", texto.lower()).strip()

    t = unidecode(t_sin_parentesis)
    t = t.replace("\xa0", " ").replace("\u200b", " ").strip()
    t = re.sub(r"[^a-z0-9\s\-_.,;:]", " ", t)

    db = get_db(app)
    cur = db.cursor()
    cur.execute("SELECT palabra, categoria FROM categoria_reglas;")
    reglas = cur.fetchall()

    print(f"\n🧩 Analizando: '{t_original}'")
    print(f"🔹 Texto limpio: '{t}'")
    print(f"⚙️ {len(reglas)} reglas cargadas desde la base de datos.\n")

    categorias_encontradas = set()

    # 🔍 2️⃣ Buscar coincidencias reales
    for r in reglas:
        palabra = r["palabra"].strip().lower()
        categoria = r["categoria"].strip()

        # 🔹 Coincidencia flexible (acepta plural "s")
        patron = rf"(^|[\s\-_.,;:]){palabra}s?([\s\-_.,;:]|$)"
        if re.search(patron, t):
            print(f"✅ Coincidencia: '{palabra}' → {categoria}")
            categorias_encontradas.add(categoria)


    # 🧠 3️⃣ Sin coincidencias
    if not categorias_encontradas:
        print("⚠️ No se encontró ninguna coincidencia → devolverá 'Otro'\n")
        return "Otro"

    # 🧩 4️⃣ Si hay una sola coincidencia
    if len(categorias_encontradas) == 1:
        cat = next(iter(categorias_encontradas))
        print(f"✅ Categoría final: {cat}\n")
        return cat

    # 🧠 5️⃣ Reglas contextuales inteligentes
    if "error" in t and "dashboard" in t:
        print("🎯 Regla contextual: error + dashboard → Desarrollo / ajustes\n")
        return "Desarrollo / ajustes"
    if "error" in t and "sensor" in t:
        print("🎯 Regla contextual: error + sensor → Mantenimiento / falla\n")
        return "Mantenimiento / falla"
    if "error" in t and "plc" in t:
        print("🎯 Regla contextual: error + plc → Control / automatización\n")
        return "Control / automatización"
    if "correo" in t and "error" in t:
        print("🎯 Regla contextual: error + correo → Comunicación / usuarios\n")
        return "Comunicación / usuarios"

    # ⚖️ 6️⃣ Resolver conflictos por prioridad general
    prioridad = [
        "Visión / imágenes",           # 👁️
        "Comunicación / usuarios",     # 💬
        "Reportes / documentos",       # 📄
        "Control / automatización",    # ⚙️
        "Mantenimiento / falla",       # 🔧
        "Desarrollo / ajustes"         # 💻
    ]



    for cat in prioridad:
        if cat in categorias_encontradas:
            print(f"⚠️ Conflicto entre {categorias_encontradas} → se prioriza {cat}\n")
            return cat

    # ⚪ 7️⃣ Si no entra en ninguna prioridad conocida
    conflicto = f"⚠️ Conflicto: {' + '.join(sorted(categorias_encontradas))}"
    print(conflicto)
    return conflicto





def asignar_categorias(app):
    """
    Reasigna categorías a todas las subtareas según las reglas actuales.
    """
    db = get_db(app)
    cur = db.cursor()

    # 🔍 Asegurar columna 'categoria'
    cur.execute("PRAGMA table_info(subtasks);")
    columnas = [c['name'] for c in cur.fetchall()]
    if 'categoria' not in columnas:
        cur.execute("ALTER TABLE subtasks ADD COLUMN categoria TEXT;")
        print("🆕 Columna 'categoria' agregada.")

    # 🔄 Procesar subtareas
    cur.execute("SELECT id, nombre_subtarea FROM subtasks;")
    rows = cur.fetchall()
    total = 0

    for r in rows:
        categoria = categorizar_subtarea(r["nombre_subtarea"], app)
        cur.execute("UPDATE subtasks SET categoria=? WHERE id=?;", (categoria, r["id"]))
        total += 1

    db.commit()
    print(f"\n✅ {total} subtareas categorizadas según la tabla de reglas.\n")
