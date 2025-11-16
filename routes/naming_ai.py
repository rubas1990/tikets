# ============================================================
# 🚀 NAMING INTELIGENTE — Versión PRO 2.0 para tu ecosistema CVG
# ------------------------------------------------------------
# Este módulo genera para cada idea de ticket:
#   - Nombre claro: [Acción + Objeto — Propósito]
#   - Categoría
#   - KR
#   - Tecnología (solo del catálogo permitido)
#
# Usa:
#   - Reglas semánticas industriales (alto peso)
#   - Datos reales de subtasks (ligero ajuste)
#   - Feedback en tabla naming_ai_feedback (opcional)
# ============================================================

from flask import Blueprint, render_template, request, current_app
from datetime import datetime
from models.db import get_db

# Blueprint registrado en /naming_ai
naming_bp = Blueprint('naming_ai', __name__, url_prefix='/naming_ai')


# ------------------------------------------------------------
# 🧠 UTILIDAD: Generador de nombres ejecutivos
# ------------------------------------------------------------
def generar_nombre(descripcion: str, categoria: str | None = None) -> str:
    """
    Genera nombres elegantes con la estructura:
        [Acción + Objeto] — [Propósito]

    - Acción: verbo canonizado (Crear, Verificar, Sincronizar, Optimizar, Automatizar…)
    - Objeto: concepto clave (conexión PLC, base de datos, formulario SQL…)
    - Propósito: se ajusta según categoría y contenido
    """
    # Normalizamos texto
    texto = descripcion.lower()

    # -------------------------
    # 1) Detectar ACCIÓN
    # -------------------------
    if any(p in texto for p in ["checar", "revisar", "validar", "verificar", "probar"]):
        accion = "Verificar"
    elif any(p in texto for p in ["crear", "generar", "hacer", "levantar", "construir"]):
        accion = "Crear"
    elif any(p in texto for p in ["optimizar", "mejorar", "ajustar", "afinar"]):
        accion = "Optimizar"
    elif any(p in texto for p in ["sincronizar", "conectar", "integrar", "linkear"]):
        accion = "Sincronizar"
    elif any(p in texto for p in ["automatizar", "programar", "agendar"]):
        accion = "Automatizar"
    else:
        # Acción neutra por defecto
        accion = "Mejorar"

    # -------------------------
    # 2) Detectar OBJETO
    # -------------------------
    objeto = "proceso"  # fallback genérico

    # PLC / señales
    if "plc" in texto:
        if any(p in texto for p in ["entrada", "salida", "entradas", "salidas", "io"]):
            objeto = "conexión PLC"
        else:
            objeto = "señales PLC"

    # Base de datos
    elif "base de datos" in texto or "bd" in texto:
        objeto = "base de datos"

    # Formulario / UI
    elif "formulario" in texto or "forma" in texto:
        if "sql" in texto:
            objeto = "formulario SQL"
        else:
            objeto = "formulario"

    # Python / scripts
    elif "python" in texto or "script" in texto:
        objeto = "ejecución Python"

    # Query Oracle / AMOS
    elif "oracle" in texto:
        objeto = "query Oracle"
    elif "amos" in texto:
        objeto = "query AMOS"
    elif "query" in texto or "consulta" in texto:
        objeto = "consulta de datos"

    # Cámara / Keyence
    elif "keyence" in texto or "camara" in texto or "cámara" in texto:
        objeto = "cámara Keyence"

    else:
        # Fallback: tomamos la primera palabra "larga" como objeto
        palabras = [p for p in texto.replace(",", " ").split() if len(p) > 3]
        if palabras:
            objeto = palabras[0]

    # -------------------------
    # 3) Detectar PROPÓSITO
    # -------------------------
    proposito = "Mejorar el proceso"  # valor por defecto

    # Ajustamos propósito en función de categoría + texto
    cat = (categoria or "").lower()

    # Integración máquina–sistema
    if "integración máquina" in cat or "integracion maquina" in cat:
        if any(p in texto for p in ["plc", "entradas", "salidas", "io", "señales", "senales"]):
            proposito = "Asegurar integridad de señales"
        elif any(p in texto for p in ["camara", "cámara", "keyence", "vision", "defecto", "pieza"]):
            proposito = "Mejorar inspección visual"
        else:
            proposito = "Incrementar confiabilidad del sistema"

    # Data Analyst / SQL / BD
    elif "data analyst" in cat or "industrial data" in cat:
        if any(p in texto for p in ["optimizar", "rapido", "rápido", "performance", "tiempo", "lento"]):
            proposito = "Optimizar rendimiento de consultas"
        else:
            proposito = "Asegurar integridad de datos"

    # UX Pro (frontend / formularios)
    elif "ux pro" in cat:
        proposito = "Mejorar experiencia del usuario"

    # Automatización
    elif "automatización" in cat or "automatizacion" in cat:
        proposito = "Automatizar procesos críticos"

    # Migraciones / PHP
    elif "migraciones" in cat:
        proposito = "Modernizar el sistema"

    # ----------------------------------------------------------------
    # Armamos nombre final con formato:
    #   Acción + Objeto — Propósito
    # ----------------------------------------------------------------
    return f"{accion} {objeto} — {proposito}"


# ------------------------------------------------------------
# 🧠 UTILIDAD: Clasificación semántica industrial
# ------------------------------------------------------------
def clasificar_semantico(descripcion: str) -> dict:
    """
    Clasificador basado en reglas industriales y tu catálogo oficial
    de tecnologías. Este es el “cerebro de reglas” que se ajusta
    periódicamente en base a cómo realmente trabajas.
    """
    texto = descripcion.lower()

    # --------------------------------------------------
    # 1) PLC / Integración máquina–sistema
    # --------------------------------------------------
    if any(x in texto for x in [
        "plc", "modbus", "allen bradley", "compactlogix", "contrologix",
        "ethernet/ip", "ladder", "tag", "hmi", "scada", "i/o", "entradas", "salidas"
    ]):
        return {
            "categoria": "Integración máquina–sistema",
            "kr": "Comunicación PLC–Servidor",
            "tecnologia": "Integracion industrial"
        }

    # Caso cámara / Keyence (inspección en línea)
    if any(x in texto for x in ["keyence", "camara", "cámara", "vision"]) and \
       any(x in texto for x in ["defecto", "pieza", "inspeccion", "inspección", "linea", "línea"]):
        return {
            "categoria": "Integración máquina–sistema",
            "kr": "Automatización industrial",
            "tecnologia": "Integracion industrial"
        }

    # --------------------------------------------------
    # 2) SQL / Base de datos / ETL / Queries
    # --------------------------------------------------
    if any(x in texto for x in [
        "sql", "consulta", "query", "base de datos", "bd", "tabla", "view", "join",
        "insert", "update", "delete", "select", "sp", "stored procedure", "sincronizar"
    ]):
        return {
            "categoria": "Data Analyst",
            "kr": "Base de Datos Industrial (SQL/AMOS/Oracle)",
            "tecnologia": "SQL Server"
        }

    # --------------------------------------------------
    # 3) Python / Scripts / Automatización general
    # --------------------------------------------------
    if any(x in texto for x in [
        "python", "script", "automatizar", "proceso automatico", "proceso automático",
        "batch", "cron", "scheduler", "ejecutar script"
    ]):
        return {
            "categoria": "Automatización",
            "kr": "Automatización de procesos",
            "tecnologia": "Python"
        }

    # --------------------------------------------------
    # 4) Flask / API / Rutas backend
    # --------------------------------------------------
    if any(x in texto for x in ["api", "endpoint", "flask", "ruta", "backend"]):
        return {
            "categoria": "Desarrollo / ajustes",
            "kr": "Integraciones externas",
            "tecnologia": "Flask"
        }

    # --------------------------------------------------
    # 5) UX / Frontend / Formularios / Tablet
    # --------------------------------------------------
    if any(x in texto for x in [
        "formulario", "frontend", "pantalla", "boton", "botón", "color",
        "vista", "interfaz", "responsive", "tablet", "ui", "ux"
    ]):
        return {
            "categoria": "UX Pro",
            "kr": "Design System",
            "tecnologia": "Bootstrap"
        }

    # --------------------------------------------------
    # 6) Industrial Data / AMOS / Oracle / Datos planta
    # --------------------------------------------------
    if any(x in texto for x in ["amos", "oracle", "industrial data", "datos industriales", "produccion", "producción"]):
        return {
            "categoria": "Industrial Data",
            "kr": "ETL Industrial",
            "tecnologia": "Industrial Data"
        }

    # --------------------------------------------------
    # 7) PHP / Migraciones legacy
    # --------------------------------------------------
    if "php" in texto or "migrar" in texto or "legacy" in texto:
        return {
            "categoria": "Migraciones",
            "kr": "Modernización del sistema",
            "tecnologia": "PHP"
        }

    # --------------------------------------------------
    # 8) Fallback genérico
    # --------------------------------------------------
    return {
        "categoria": "Otro",
        "kr": "Sin definir",
        "tecnologia": "Otro"
    }


# ------------------------------------------------------------
# 🔥 INTELIGENCIA HÍBRIDA (Reglas + Datos Internos)
# ------------------------------------------------------------
def generar_sugerencia(descripcion: str, db) -> dict:
    """
    Combina:
    - Reglas semánticas industriales (alto peso)
    - Datos reales de subtasks (bajo peso, estilo “afinador”)
    """
    # 1) Clasificación semántica (cerebro de reglas)
    reglas = clasificar_semantico(descripcion)
    categoria = reglas["categoria"]
    kr = reglas["kr"]
    tecnologia = reglas["tecnologia"]

    # 2) Nombre se genera en función de categoría
    nombre = generar_nombre(descripcion, categoria)

    # 3) Ajuste fino con datos reales (si hay coincidencias)
    try:
        cur = db.cursor()

        # Buscar tecnologías reales relacionadas
        cur.execute("""
            SELECT tecnologia
            FROM subtasks
            WHERE LOWER(nombre_subtarea) LIKE ?
            LIMIT 1;
        """, (f"%{descripcion.lower()}%",))

        row = cur.fetchone()
        if row and row["tecnologia"]:
            tecnologia = row["tecnologia"]

        # Buscar KR reales similares
        cur.execute("""
            SELECT kr
            FROM subtasks
            WHERE LOWER(nombre_subtarea) LIKE ?
              AND kr IS NOT NULL AND kr != ''
            LIMIT 1;
        """, (f"%{descripcion.lower()}%",))

        row = cur.fetchone()
        if row and row["kr"]:
            kr = row["kr"]

    except Exception:
        # Si falla la BD, no rompemos la lógica de naming
        pass

    # Resultado final unificado
    return {
        "nombre": nombre,
        "categoria": categoria,
        "kr": kr,
        "tecnologia": tecnologia
    }


# ------------------------------------------------------------
# 🟦 RUTA PRINCIPAL /naming_ai
# ------------------------------------------------------------
@naming_bp.route('/', methods=['GET', 'POST'])
def naming_ai():
    """
    Vista de la herramienta de Naming Inteligente.

    - GET: muestra formulario vacío
    - POST: recibe descripción, llama a la IA interna y muestra resultado
    """
    sugerencia = None
    descripcion = ""

    if request.method == 'POST':
        # Tomamos la descripción cruda del formulario
        descripcion = request.form.get('descripcion', '').strip()

        if descripcion:
            # Conexión a la BD SQLite principal
            db = get_db(current_app)

            # Generamos sugerencia híbrida (reglas + datos internos)
            sugerencia = generar_sugerencia(descripcion, db)

            # Registramos feedback inicial en naming_ai_feedback (si existe)
            try:
                cur = db.cursor()
                cur.execute("""
                    INSERT INTO naming_ai_feedback (
                        descripcion_original,
                        nombre_sugerido,
                        categoria_sugerida,
                        kr_sugerido,
                        tecnologia_sugerida,
                        aceptado,
                        fecha
                    ) VALUES (?, ?, ?, ?, ?, 0, ?);
                """, (
                    descripcion,
                    sugerencia["nombre"],
                    sugerencia["categoria"],
                    sugerencia["kr"],
                    sugerencia["tecnologia"],
                    datetime.now().isoformat(timespec="seconds"),
                ))
                db.commit()
            except Exception:
                # Si la tabla no existe o algo falla, no bloqueamos la herramienta
                pass

    # Renderizamos plantilla con la descripción y sugerencia (si existe)
    return render_template(
        'naming_ai.html',
        sugerencia=sugerencia,
        descripcion=descripcion
    )
