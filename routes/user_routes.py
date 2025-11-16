# routes/user_routes.py

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from auth import login_required, role_required
from models import create_user

user_bp = Blueprint('user', __name__, url_prefix="/users")


@user_bp.route('/new', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def user_new():
    """Formulario para crear un nuevo usuario (solo admin)."""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        role = request.form.get('role', 'user')

        if not username or not password:
            flash("Usuario y contraseña son obligatorios.", "warning")
            return render_template('user_form.html')

        ok = create_user(current_app, username, password, role)
        if ok:
            flash("✅ Usuario creado correctamente.", "success")
            return redirect(url_for('main.index'))
        else:
            flash("❌ El nombre de usuario ya existe.", "danger")

    return render_template('user_form.html')
