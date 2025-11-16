# routes/checklist.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import checklist

checklist_bp = Blueprint("checklist", __name__)

# 🟢 Ver y agregar reglas
@checklist_bp.route("/checklist", methods=["GET", "POST"])
def checklist_view():
    # 🔹 Agregar nueva regla
    if request.method == "POST" and "add" in request.form:
        kr = (request.form.get("kr") or "").strip()
        punto = (request.form.get("punto") or "").strip()
        orden = int(request.form.get("orden") or 0)

        if not kr or not punto:
            flash("⚠️ Debes llenar todos los campos.", "warning")
            return redirect(url_for("checklist.checklist_view"))

        checklist.add_rule(kr, punto, orden)
        flash("✅ Regla agregada correctamente.", "success")
        return redirect(url_for("checklist.checklist_view"))

    reglas = checklist.get_all_rules()
    return render_template("checklist.html", reglas=reglas)


# ✏️ Actualizar regla existente
@checklist_bp.route("/checklist/update/<int:id>", methods=["POST"])
def checklist_update(id):
    kr = (request.form.get("kr") or "").strip()
    punto = (request.form.get("punto") or "").strip()
    orden = int(request.form.get("orden") or 0)

    if not kr or not punto:
        flash("⚠️ Debes llenar todos los campos.", "warning")
        return redirect(url_for("checklist.checklist_view"))

    checklist.update_rule(id, kr, punto, orden)
    flash("✏️ Regla actualizada.", "info")
    return redirect(url_for("checklist.checklist_view"))


# 🗑️ Eliminar regla
@checklist_bp.route("/checklist/delete/<int:id>", methods=["POST"])
def checklist_delete(id):
    checklist.delete_rule(id)
    flash("🗑️ Regla eliminada.", "danger")
    return redirect(url_for("checklist.checklist_view"))
