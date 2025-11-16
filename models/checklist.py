# models/checklist.py
import sqlite3
from flask import current_app

def get_db():
    # Conexión a la base de datos SQLite (ya existente)
    db_path = current_app.config.get("DATABASE", "soporte.db")
    return sqlite3.connect(db_path)

def get_all_rules():
    conn = get_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM checklist_rules ORDER BY kr, orden;")

    rules = cur.fetchall()
    conn.close()
    return rules

def add_rule(kr, punto, orden):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO checklist_rules (kr, punto, orden)
        VALUES (?, ?, ?);
    """, (kr, punto, orden))
    conn.commit()
    conn.close()


def update_rule(id, kr, punto, orden):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        UPDATE checklist_rules
        SET kr = ?, punto = ?, orden = ?
        WHERE id = ?;
    """, (kr, punto, orden, id))
    conn.commit()
    conn.close()


def delete_rule(id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM checklist_rules WHERE id=?;", (id,))
    conn.commit()
    conn.close()
