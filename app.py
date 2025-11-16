# app.py
from flask import Flask, session
from models import init_db, get_db, registrar_fin_trabajo
from models.personal import get_current_activity
from auth import auth_bp
from routes import register_blueprints
import threading
import time
from datetime import datetime
import pytz
from routes.reports_routes import reports_bp
import os
import requests

def create_app():
    app = Flask(__name__)
    app.config["BUILD_ID"] = int(datetime.now().timestamp())
    app.config['SECRET_KEY'] = 'cambia-esta-clave-en-produccion'

    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    app.config['DATABASE'] = os.path.join(BASE_DIR, 'soporte.db')
    print(f"[debug] 🧱 Usando base de datos: {app.config['DATABASE']}")

    init_db(app)

    app.register_blueprint(auth_bp)
    register_blueprints(app)
    app.register_blueprint(reports_bp)

    @app.template_filter('fmt_dt')
    def fmt_dt(value):
        if not value:
            return ''
        return value.replace('T', ' ').split('.')[0]

    @app.context_processor
    def inject_current_activity():
        username = session.get("username")
        if not username:
            return dict(current_activity=None)
        actividad = get_current_activity(app, username)
        return dict(current_activity=actividad)

    return app


def cerrar_proyectos_fuera_de_horario(app):
    ultima_ejecucion = None
    with app.app_context():
        while True:
            try:
                tz = pytz.timezone("America/Monterrey")
                ahora = datetime.now(tz)
                hora_actual = ahora.strftime("%H:%M")
                fecha_actual = ahora.date()

                if hora_actual == "17:06" and ultima_ejecucion != fecha_actual:
                    db = get_db(app)
                    cur = db.cursor()
                    cur.execute("SELECT id, nombre FROM projects WHERE status='Trabajando';")
                    activos = cur.fetchall()

                    if activos:
                        for a in activos:
                            cur.execute("UPDATE projects SET status='Detenido' WHERE id=?;", (a['id'],))
                            registrar_fin_trabajo(app, a['id'])
                        db.commit()

                    ultima_ejecucion = fecha_actual

                time.sleep(60)

            except Exception as e:
                print(f"⚠️ Error en tarea automática: {e}")
                time.sleep(60)


if __name__ == '__main__':
    app = create_app()
    threading.Thread(target=cerrar_proyectos_fuera_de_horario, args=(app,), daemon=True).start()
    app.run(debug=True, port=70, host="0.0.0.0")
