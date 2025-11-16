# services/pdf_report.py
from io import BytesIO
from datetime import datetime
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
import os

# =====================================================
# 🔹 HEADER / FOOTER
# =====================================================
def draw_header(c, title, periodo_text, logo_path=None):
    """Corporate header with logo and gradient bar."""
    width, height = LETTER

    # Blue banner background
    c.setFillColor(colors.HexColor("#0d6efd"))
    c.rect(0, height - 100, width, 100, fill=1, stroke=0)

    # Logo (optional)
    if logo_path and os.path.exists(logo_path):
        try:
            logo = ImageReader(logo_path)
            c.drawImage(logo, 40, height - 90, width=80, preserveAspectRatio=True, mask='auto')
        except Exception as e:
            print("[warning] Could not load logo:", e)

    # Title text
    c.setFont("Helvetica-Bold", 20)
    c.setFillColor(colors.white)
    c.drawString(140, height - 60, title)

    # Subtitle (period)
    c.setFont("Helvetica", 10)
    c.setFillColor(colors.whitesmoke)
    c.drawString(140, height - 78, f"Period: {periodo_text}")
    c.setFillColor(colors.black)


def draw_footer(c):
    """Footer with company signature."""
    c.setFont("Helvetica-Oblique", 9)
    c.setFillColor(colors.grey)
    c.drawCentredString(LETTER[0] / 2, 30,
                        "Quality • Control Area — CVG Corporate ©2025")


# =====================================================
# 🔹 TABLES AND CONTENT
# =====================================================
def draw_table(c, data, x, y, col_titles):
    """Draws Hours vs Target table with status."""
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(colors.HexColor("#f8f9fa"))
    c.rect(x, y - 14, 500, 16, fill=1, stroke=0)
    c.setFillColor(colors.black)

    # Column headers
    col_x = [x + 6, x + 220, x + 320, x + 420, x + 500]
    for i, t in enumerate(col_titles):
        c.drawString(col_x[i], y - 12, t)
    y -= 20

    c.setFont("Helvetica", 10)
    alt = False
    for row in data:
        if y < 100:
            c.showPage()
            draw_footer(c)
            draw_header(c, "📊 Executive Monthly Report", "", None)
            y = 750

        # alternate row shading
        if alt:
            c.setFillColor(colors.HexColor("#f1f3f5"))
            c.rect(x, y - 12, 500, 14, fill=1, stroke=0)
        c.setFillColor(colors.black)

        c.drawString(x + 6, y - 2, str(row.get("project", ""))[:32])
        c.drawRightString(x + 320, y - 2, f"{row.get('actual_hours', 0):.2f}")
        c.drawRightString(x + 420, y - 2, f"{row.get('target_hours', 0):.2f}")
        c.drawString(x + 450, y - 2, row.get("status", ""))

        alt = not alt
        y -= 14

    return y


# =====================================================
# 🔹 MAIN PDF BUILDER
# =====================================================
def build_exec_pdf(metrics):
    """
    Generates an updated English executive PDF report
    consistent with the HTML dashboard.
    """
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=LETTER)
    width, height = LETTER

    # Logo path
    logo_path = os.path.join("static", "images", "logo.png")

    # Header
    periodo = metrics["period"]
    periodo_text = f"{periodo['year']}-{periodo['month']:02d} ({periodo['start']} → {periodo['end']})"
    draw_header(c, "📊 Executive Monthly Report", periodo_text, logo_path)

    y = height - 130
    c.setFont("Helvetica", 11)
    c.drawString(72, y, f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    y -= 25

    # =====================================================
    # KPI Summary
    # =====================================================
    c.setFont("Helvetica-Bold", 12)
    c.drawString(72, y, "Key Performance Indicators (KPIs)")
    y -= 15
    c.setFont("Helvetica", 11)
    c.drawString(72, y, f"💰 Total Savings: ${metrics['ahorro_total']:,.2f}")
    y -= 15
    c.drawString(72, y, f"📈 Projected Closures: {metrics['proj_cierre_mes']} tickets")
    y -= 15
    c.drawString(72, y, f"✅ Completion Rate: {metrics['projects_closed_pct']}%")
    y -= 25

    # =====================================================
    # Project Status Overview
    # =====================================================
    c.setFont("Helvetica-Bold", 12)
    c.drawString(72, y, "Project Status Overview")
    y -= 15
    c.setFont("Helvetica", 11)
    c.drawString(72, y,
        f"🟢 Closed: {metrics['projects_closed']}   "
        f"🟡 In Progress: {metrics['projects_working']}   "
        f"🔴 On Hold: {metrics['projects_stopped']}"
    )
    y -= 30

    # =====================================================
    # Hours vs Target Table
    # =====================================================
    c.setFont("Helvetica-Bold", 12)
    c.drawString(72, y, "⏱ Hours vs Target per Project")
    y -= 10
    y = draw_table(
        c,
        metrics["hours_by_project"],
        72,
        y,
        ["Project", "Actual (h)", "Target (h)", "Status"]
    )

    y -= 25
    c.setFont("Helvetica-Bold", 12)
    c.drawString(72, y, "🏅 Top 3 Most Efficient Operators")
    y -= 18
    c.setFont("Helvetica", 10)
    for op in metrics["top_operators"]:
        c.drawString(80, y, f"{op['username']}: {op['efficiency_pct']}% "
                            f"(Real: {op['actual_hours']}h / Target: {op['target_hours']}h)")
        y -= 14

    y -= 20
    c.setFont("Helvetica-Bold", 12)
    c.drawString(72, y, "📅 Weekly Closure Performance")
    y -= 18
    c.setFont("Helvetica", 10)
    for week in metrics["closed_by_week"]:
        c.drawString(80, y, f"{week['week_label']}: {week['cerrados']} closed")
        y -= 14

    y -= 25
    c.setFont("Helvetica-Bold", 12)
    c.drawString(72, y, "🧠 Data Insights")
    y -= 16
    c.setFont("Helvetica", 10)
    for insight in metrics["data_insights"]:
        c.drawString(80, y, f"- {insight}")
        y -= 12

    # Footer
    draw_footer(c)
    c.showPage()
    c.save()

    buffer.seek(0)
    return buffer.getvalue()
