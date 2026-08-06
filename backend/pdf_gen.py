import io
import os
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ReportLab-ის ჩაშენებული Helvetica ფონტი მხოლოდ ლათინურ დამწერლობას
# უჭერს მხარს — ქართული ტექსტი (პაციენტის/ექიმის სახელები, დიაგნოზი) მასზე
# საერთოდ არ გამოისახებოდა. ამიტომ რეცეპტის PDF-ში გამოიყენება Noto Sans
# Georgian (Google Fonts, OFL ლიცენზია) — ჩართულია პროექტში `fonts/`
# საქაღალდეში, რომ დამოუკიდებელი იყოს ოპერაციული სისტემისგან/დეპლოის
# გარემოსგან. თუ ფონტის ფაილი რაიმე მიზეზით ვერ მოიძებნა, გრაცილურად
# ვბრუნდებით ჩაშენებულ Helvetica-ზე (მაშინ ქართული ტექსტი არ გამოისახება,
# მაგრამ PDF მაინც გენერირდება).
_FONT_NAME = "Helvetica"
_FONT_BOLD = "Helvetica-Bold"
_FONT_ITALIC = "Helvetica-Oblique"
_font_path = os.path.join(os.path.dirname(__file__), "fonts", "NotoSansGeorgian.ttf")
if os.path.exists(_font_path):
    try:
        pdfmetrics.registerFont(TTFont("NotoGeorgian", _font_path))
        _FONT_NAME = _FONT_BOLD = _FONT_ITALIC = "NotoGeorgian"
    except Exception:
        pass


def generate_prescription_pdf(
    patient_name: str,
    doctor_name: str,
    specialty: str,
    appointment_date: datetime,
    diagnosis: str,
    medication: str,
    dosage: str,
    instructions: str,
) -> bytes:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    left_margin = 2.5 * cm
    right_margin = width - 2 * cm
    y = height - 2 * cm

    # Header
    c.setFillColor(colors.HexColor("#0F766E"))
    c.rect(0, height - 2.2 * cm, width, 2.2 * cm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont(_FONT_BOLD, 18)
    c.drawString(left_margin, height - 1.4 * cm, "MediCare Clinic")
    c.setFont(_FONT_NAME, 10)
    c.drawString(left_margin, height - 1.9 * cm, "რეცეპტი / სამედიცინო ცნობა")

    y = height - 3.2 * cm
    c.setFillColor(colors.black)

    def field(label, value, y_pos):
        c.setFont(_FONT_BOLD, 11)
        c.drawString(left_margin, y_pos, f"{label}:")
        c.setFont(_FONT_NAME, 11)
        c.drawString(left_margin + 4.5 * cm, y_pos, str(value))

    field("პაციენტი", patient_name, y)
    y -= 0.8 * cm
    field("ექიმი", f"{doctor_name} ({specialty})", y)
    y -= 0.8 * cm
    field("თარიღი", appointment_date.strftime("%Y-%m-%d %H:%M"), y)
    y -= 1.2 * cm

    c.setStrokeColor(colors.HexColor("#CBD5E1"))
    c.line(left_margin, y, right_margin, y)
    y -= 1 * cm

    def block(title, text, y_pos):
        c.setFont(_FONT_BOLD, 12)
        c.setFillColor(colors.HexColor("#0F766E"))
        c.drawString(left_margin, y_pos, title)
        c.setFillColor(colors.black)
        c.setFont(_FONT_NAME, 10)
        y_pos -= 0.6 * cm
        text = text or "-"
        max_chars = 95
        lines = []
        for paragraph in text.split("\n"):
            while len(paragraph) > max_chars:
                split_at = paragraph.rfind(" ", 0, max_chars)
                if split_at == -1:
                    split_at = max_chars
                lines.append(paragraph[:split_at])
                paragraph = paragraph[split_at:].strip()
            lines.append(paragraph)
        for line in lines:
            c.drawString(left_margin, y_pos, line)
            y_pos -= 0.5 * cm
        return y_pos - 0.4 * cm

    y = block("დიაგნოზი", diagnosis, y)
    y = block("მედიკამენტი", medication, y)
    y = block("დოზირება", dosage, y)
    y = block("ინსტრუქცია", instructions, y)

    c.setFont(_FONT_ITALIC, 8)
    c.setFillColor(colors.grey)
    c.drawString(
        left_margin,
        2 * cm,
        "დოკუმენტი ავტომატურად გენერირებულია Clinic Appointment System-ის მიერ (საბაკალავრო პროექტი).",
    )

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer.getvalue()
