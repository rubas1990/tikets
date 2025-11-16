# models/db.py
import sqlite3
import os
from flask import g
from werkzeug.security import generate_password_hash

# ---------------------------------------------------------
# 📌 DEFINIR PATH SEGURO PARA Render + Local
# ---------------------------------------------------------
def resolve_database_path(app):
    """
    Determina el path correcto de la base de datos.

    PRIORIDAD:
    1. Si Flask define app.config['DATABASE'] → se respeta (local)
    2. Si existe /data (Render) → usar /data/soporte.db
    3. Fallback → soporte.db local junto a app.py
    """

    # 1) Config explícita desde app.py (local)
    if app and app.config.get("DATABASE"):
        return app.config["DATABASE"]

    # 2) Ruta oficial de Render
    if os.path.isdir("/data"):
        return "/data/soporte.db"

    # 3) Modo fallback local
    base_local = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "soporte.db")
    )
    return base_local


# ---------------------------------------------------------
# 1️⃣ Conexión a la base de datos
# ---------------------------------------------------------
def get_db(app):
    """Abre conexión SQLite asegurando path correcto."""
    if "db" not in g:
        db_path = resolve_database_path(app)

        # Auto-crea carpeta /data si Render no la tiene
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        g.db = sqlite3.connect(db_path, check_same_thread=False)
        g.db.row_factory = sqlite3.Row

    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


# ---------------------------------------------------------
# 2️⃣ Inicialización y creación de tablas
# ---------------------------------------------------------
def init_db(app):
    """Inicializa la base de datos y crea tablas si no existen."""

    app.teardown_appcontext(close_db)

    with app.app_context():
        db = get_db(app)
        cur = db.cursor()

        # ==========================
        # USERS
        # ==========================
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('admin','user'))
            );
        """)

        # ==========================
        # PROJECTS
        # ==========================
        cur.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                numero_de_queja TEXT UNIQUE NOT NULL,
                sitio TEXT NOT NULL,
                prioridad TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('Planeado','Detenido','Trabajando','Cerrado')),
                fecha_apertura TEXT NOT NULL,
                fecha_cierre TEXT,
                comentarios TEXT,
                ahorro REAL DEFAULT 0,
                gasto REAL DEFAULT 0
            );
        """)

        # ==========================
        # SUBTASKS
        # ==========================
        cur.execute("""
            CREATE TABLE IF NOT EXISTS subtasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                numero_de_queja TEXT NOT NULL,
                nombre_subtarea TEXT NOT NULL,
                cerrado INTEGER NOT NULL DEFAULT 0,
                fecha_apertura TEXT NOT NULL,
                fecha_cierre TEXT,
                comentarios TEXT DEFAULT '',
                tiempo_objetivo_horas REAL,
                prioridad TEXT,
                tiempo_objetivo REAL DEFAULT 0,
                categoria TEXT,
                tecnologia TEXT,
                dificultad INTEGER,
                kr TEXT,
                aprendizaje TEXT,
                FOREIGN KEY (project_id) REFERENCES projects(id)
            );
        """)

        # ==========================
        # HISTORIAL
        # ==========================
        cur.execute("""
            CREATE TABLE IF NOT EXISTS historial (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo TEXT NOT NULL,
                ref_id INTEGER NOT NULL,
                fecha TEXT NOT NULL,
                accion TEXT NOT NULL,
                detalle TEXT NOT NULL,
                usuario TEXT NOT NULL
            );
        """)

        # ==========================
        # TIEMPOS DE PROYECTOS
        # ==========================
        cur.execute("""
            CREATE TABLE IF NOT EXISTS project_tiempo (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                inicio TEXT NOT NULL,
                fin TEXT,
                duracion_horas REAL,
                FOREIGN KEY(project_id) REFERENCES projects(id)
            );
        """)

        # ==========================
        # PERSONAL TASKS
        # ==========================
        cur.execute("""
            CREATE TABLE IF NOT EXISTS personal_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TEXT NOT NULL,
                tipo TEXT NOT NULL CHECK(tipo IN ('Proyecto','Personal')),
                numero_tarea TEXT NOT NULL,
                descripcion TEXT,
                project_id INTEGER,
                username TEXT NOT NULL,
                FOREIGN KEY(project_id) REFERENCES projects(id)
            );
        """)

        # ==========================
        # HABITS
        # ==========================
        cur.execute("""
            CREATE TABLE IF NOT EXISTS habits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                nombre TEXT NOT NULL,
                posicion INTEGER NOT NULL CHECK(posicion BETWEEN 1 AND 5)
            );
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS habit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                habit_id INTEGER NOT NULL,
                fecha TEXT NOT NULL,
                completado INTEGER DEFAULT 0,
                FOREIGN KEY (habit_id) REFERENCES habits(id)
            );
        """)

        # ==========================
        # EMOCIONAL LOG
        # ==========================
        cur.execute("""
            CREATE TABLE IF NOT EXISTS emocional_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TEXT NOT NULL,
                username TEXT NOT NULL,
                categoria TEXT,
                horas_trabajadas REAL DEFAULT 0,
                tareas_seguidas INTEGER DEFAULT 0,
                nivel_fatiga TEXT,
                estado_emocional TEXT,
                mensaje TEXT
            );
        """)

        # ==========================
        # SUBTASK TIME
        # ==========================
        cur.execute("""
            CREATE TABLE IF NOT EXISTS subtask_tiempo (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subtask_id INTEGER NOT NULL,
                username TEXT NOT NULL,
                inicio TEXT NOT NULL,
                fin TEXT,
                duracion_min REAL,
                FOREIGN KEY(subtask_id) REFERENCES subtasks(id)
            );
        """)

        # ==========================
        # OKR / KR
        # ==========================
        cur.execute("""
            CREATE TABLE IF NOT EXISTS okr_kr (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                categoria TEXT NOT NULL,
                kr TEXT NOT NULL,
                comentarios TEXT,
                kr_resultado TEXT,
                peso INTEGER DEFAULT 1,
                activo INTEGER DEFAULT 1
            );
        """)

        db.commit()

        # ==========================
        # USUARIOS DEFAULT
        # ==========================
        cur.execute("SELECT COUNT(*) AS c FROM users;")
        if cur.fetchone()['c'] == 0:
            cur.execute("INSERT INTO users VALUES (NULL, ?, ?, 'admin')",
                        ("admin", generate_password_hash("admin123")))
            cur.execute("INSERT INTO users VALUES (NULL, ?, ?, 'user')",
                        ("usuario", generate_password_hash("usuario123")))
            db.commit()
