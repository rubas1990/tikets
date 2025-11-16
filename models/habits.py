from models.db import get_db
from datetime import date, datetime
from zoneinfo import ZoneInfo

def get_user_habits(app, username):
    """Devuelve los 5 hábitos del usuario. Crea los predeterminados si no existen."""
    db = get_db(app)
    cur = db.cursor()
    cur.execute("SELECT * FROM habits WHERE username = ? ORDER BY posicion ASC", (username,))
    habits = cur.fetchall()

    # Si no existen, crear los 5 hábitos vacíos
    if len(habits) < 5:
        for i in range(1, 6):
            cur.execute("INSERT INTO habits (username, nombre, posicion) VALUES (?, ?, ?)",
                        (username, f'Hábito {i}', i))
        db.commit()
        cur.execute("SELECT * FROM habits WHERE username = ? ORDER BY posicion ASC", (username,))
        habits = cur.fetchall()

    return habits


def get_habit_logs(app, habit_ids, year, month):
    """Devuelve los registros del mes."""
    db = get_db(app)
    cur = db.cursor()
    cur.execute("""
        SELECT * FROM habit_log
        WHERE habit_id IN ({})
        AND strftime('%Y', fecha) = ? AND strftime('%m', fecha) = ?
    """.format(','.join(['?']*len(habit_ids))), (*habit_ids, str(year), f"{month:02d}"))
    return cur.fetchall()


def update_habit_name(app, habit_id, nombre):
    db = get_db(app)
    cur = db.cursor()
    cur.execute("UPDATE habits SET nombre = ? WHERE id = ?", (nombre, habit_id))
    db.commit()


def toggle_habit(app, habit_id, fecha):
    """Alterna el estado completado del hábito."""
    db = get_db(app)
    cur = db.cursor()
    cur.execute("SELECT id, completado FROM habit_log WHERE habit_id = ? AND fecha = ?", (habit_id, fecha))
    row = cur.fetchone()
    if row:
        nuevo = 0 if row['completado'] else 1
        cur.execute("UPDATE habit_log SET completado = ? WHERE id = ?", (nuevo, row['id']))
    else:
        cur.execute("INSERT INTO habit_log (habit_id, fecha, completado) VALUES (?, ?, 1)", (habit_id, fecha))
    db.commit()




