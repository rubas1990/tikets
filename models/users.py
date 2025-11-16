from werkzeug.security import check_password_hash, generate_password_hash
from .db import get_db

def get_user_by_username(app, username):
    db = get_db(app)
    cur = db.cursor()
    cur.execute("SELECT * FROM users WHERE username=?;", (username,))
    return cur.fetchone()

def verify_user_password(app, username, password):
    user = get_user_by_username(app, username)
    if user and check_password_hash(user['password_hash'], password):
        return user
    return None

def create_user(app, username, password, role='user'):
    db = get_db(app)
    cur = db.cursor()
    try:
        cur.execute("""
            INSERT INTO users (username, password_hash, role)
            VALUES (?, ?, ?)
        """, (username.strip(), generate_password_hash(password), role))
        db.commit()
        return True
    except Exception:
        return False
