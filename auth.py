# auth.py
# -------------------------------
# Blueprint de autenticación:
# - /login y /logout
# - Decoradores: login_required, role_required
# - Manejo de sesión con Flask (sin Flask-Login)

from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from functools import wraps
from models import verify_user_password

auth_bp = Blueprint('auth', __name__)

# Decorador para exigir login
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash("Debes iniciar sesión.", "warning")
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return wrapper

# Decorador para exigir rol específico (admin/user)
def role_required(role):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if 'user_role' not in session or session['user_role'] != role:
                flash("No tienes permisos para esa acción.", "danger")
                return redirect(url_for('main.index'))
            return f(*args, **kwargs)
        return wrapper
    return decorator

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # GET: muestra formulario; POST: procesa credenciales
    if request.method == 'POST':
        # Toma campos del formulario
        username = request.form.get('username','').strip()
        password = request.form.get('password','').strip()
        # Verifica credenciales
        user = verify_user_password(current_app, username, password)
        if user:
            # Popular sesión
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['user_role'] = user['role']
            flash(f"Bienvenido, {user['username']}", "success")
            return redirect(url_for('dashboard.dashboard'))
        else:
            flash("Usuario o contraseña inválidos.", "danger")
    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    # Limpia sesión
    session.clear()
    flash("Sesión finalizada.", "info")
    return redirect(url_for('auth.login'))
