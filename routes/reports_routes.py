# routes/reports_routes.py
from flask import Blueprint, request, send_file, current_app, render_template
from io import BytesIO
from datetime import date
from models import get_db
from models.analytics import get_exec_metrics
from services.pdf_report import build_exec_pdf

reports_bp = Blueprint("reports", __name__)

@reports_bp.route("/reports/exec")
def exec_monthly_view():
    """Vista HTML del panel ejecutivo."""
    today = date.today()
    year = int(request.args.get("year", today.year))
    month = int(request.args.get("month", today.month))

    metrics = get_exec_metrics(get_db(current_app), year, month)
    return render_template("reports_exec.html", metrics=metrics)

@reports_bp.route("/reports/exec.pdf")
def exec_monthly_pdf():
    """Genera y descarga el PDF ejecutivo mensual."""
    today = date.today()
    year = int(request.args.get("year", today.year))
    month = int(request.args.get("month", today.month))

    metrics = get_exec_metrics(get_db(current_app), year, month)
    pdf_bytes = build_exec_pdf(metrics)
    return send_file(
        BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"Panel_Ejecutivo_{year}-{month:02d}.pdf",
    )
