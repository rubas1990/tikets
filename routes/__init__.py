from flask import Flask

def register_blueprints(app: Flask):
    from .main_routes import main_bp
    from .dashboard_routes import dashboard_bp
    from .project_routes import project_bp
    from .tiket_routes import tiket_bp
    from .personal_routes import personal_bp
    from .agenda_routes import agenda_bp
    from .weekly_report_routes import weekly_bp
    from .agenda_predictiva import para_hoy_bp
    from .paquete_routes import paquete_bp
    from .resumen import resumen_bp
    from .api import api_bp
    from .growth_routes import growth_bp
    from .checklist import checklist_bp
    from .tiket_visual import visual_bp
    from .tiket_edit import edit_bp
    from .naming_ai import naming_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(project_bp)
    app.register_blueprint(tiket_bp)
    app.register_blueprint(personal_bp)
    app.register_blueprint(agenda_bp)
    app.register_blueprint(paquete_bp)
    app.register_blueprint(resumen_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(growth_bp)
    app.register_blueprint(weekly_bp)
    app.register_blueprint(para_hoy_bp)
    app.register_blueprint(checklist_bp)
    app.register_blueprint(visual_bp)
    app.register_blueprint(edit_bp)
    app.register_blueprint(naming_bp)


    # ===== DEBUG FLASK =====
    print("\n===== BLUEPRINTS CARGADOS =====")
    for name in app.blueprints.keys():
        print(" -", name)

    print("\n===== RUTAS REGISTRADAS =====")
    for rule in app.url_map.iter_rules():
        print(f" {rule.endpoint:30}  ->  {rule.rule}")
    print("================================\n")
