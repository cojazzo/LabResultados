"""
PDF del Examen General de Orina (EGO). Mismo encabezado, fondo y pie que el reporte renal,
con las tablas del formato INAER: examen físico, químico y microscópico.
Solo muestra lo capturado; no interpreta resultados.
"""

import io
import os
from datetime import date, datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from xml.sax.saxutils import escape

from app.config import get_settings
from app.models import ExamenOrina
from app.services.pdf_generator import resolve_sex
from app.utils.ego import CAMPOS, SECCIONES
from app.utils.validators import nombre_completo_paciente

AZUL = colors.HexColor("#1e3a5f")
TEAL = colors.HexColor("#0d9488")
GRIS = colors.HexColor("#64748b")
TEXTO = colors.HexColor("#334155")
BORDE = colors.HexColor("#cbd5e1")
FONDO_ENC = colors.HexColor("#f1f5f9")


def folio_ego(examen: ExamenOrina) -> str:
    return f"EGO-{examen.fecha_toma:%Y}-{examen.id:06d}"


def _edad(dob, ref: date):
    if not dob:
        return None
    if dob.year > datetime.now().year:  # mismo ajuste que el reporte renal (2090 -> 1990)
        dob = dob.replace(year=dob.year - 100)
    return ref.year - dob.year - ((ref.month, ref.day) < (dob.month, dob.day))


def _txt(valor) -> str:
    return escape(str(valor)) if valor not in (None, "") else "—"


def generar_pdf_ego(examen: ExamenOrina) -> bytes:
    """`examen` debe traer cargados `paciente` y `quimico`."""
    settings = get_settings()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=24, leftMargin=24, topMargin=24, bottomMargin=24)

    styles = getSampleStyleSheet()
    title = ParagraphStyle("T", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=12, textColor=AZUL, spaceAfter=1)
    subtitle = ParagraphStyle("S", parent=styles["Normal"], fontName="Helvetica", fontSize=7.5, textColor=GRIS)
    section = ParagraphStyle("Sec", parent=styles["Heading3"], fontName="Helvetica-Bold", fontSize=8.5, textColor=TEAL, spaceBefore=6, spaceAfter=2)
    body = ParagraphStyle("B", parent=styles["Normal"], fontName="Helvetica", fontSize=7.5, textColor=TEXTO)
    cell = ParagraphStyle("C", parent=body)
    cell_b = ParagraphStyle("CB", parent=body, fontName="Helvetica-Bold")
    titulo_doc = ParagraphStyle("TD", parent=title, fontSize=11, alignment=1, spaceBefore=4, spaceAfter=2)

    paciente = examen.paciente
    folio = folio_ego(examen)
    elements = [Spacer(1, 120)]

    # Encabezado
    address = settings.LAB_ADDRESS.replace(" Fideicomiso", "<br/>Fideicomiso")
    header = Table([
        [Paragraph(f"<b>{settings.LAB_NAME}</b>", title),
         Paragraph(f"<b>FOLIO DE REPORTE</b><br/><font size=10 color='#ef4444'>{folio}</font>",
                   ParagraphStyle("F", parent=body, alignment=TA_RIGHT))],
        [Paragraph(f"{address}<br/>Tel: {settings.LAB_PHONE} | Email: {settings.LAB_EMAIL}", subtitle),
         Paragraph(f"Fecha Emisión: {datetime.now():%d/%m/%Y %H:%M}", ParagraphStyle("E", parent=subtitle, alignment=TA_RIGHT))],
    ], colWidths=[400, 164])
    header.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOTTOMPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0)]))
    elements += [header, Spacer(1, 2)]
    divider = Table([[""]], colWidths=[564], rowHeights=[1])
    divider.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), AZUL)]))
    elements += [divider, Paragraph("EXAMEN GENERAL DE ORINA", titulo_doc)]

    # Paciente
    edad = _edad(paciente.fecha_nacimiento, examen.fecha_toma)
    sexo = "Femenino" if resolve_sex(paciente) else "Masculino"
    info = Table([
        [Paragraph("<b>INFORMACIÓN DEL PACIENTE</b>", section), ""],
        [Paragraph(f"<b>Nombre:</b> {escape(nombre_completo_paciente(paciente))}", body),
         Paragraph(f"<b>Identificación/CURP:</b> {escape(paciente.identificacion)}", body)],
        [Paragraph(f"<b>Edad:</b> {f'{edad} años' if edad is not None else '—'} | <b>Sexo:</b> {sexo}", body),
         Paragraph(f"<b>Fecha de Toma:</b> {examen.fecha_toma:%d/%m/%Y}", body)],
    ], colWidths=[282, 282])
    info.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOTTOMPADDING", (0, 0), (-1, -1), 0.5), ("TOPPADDING", (0, 0), (-1, -1), 0.5)]))
    elements.append(info)

    # Secciones
    for clave_seccion, nombre_seccion in SECCIONES:
        filas = [[Paragraph("<b>Estudio</b>", cell_b), Paragraph("<b>Resultado</b>", cell_b),
                  Paragraph("<b>Unidades</b>", cell_b), Paragraph("<b>Valores de referencia</b>", cell_b)]]
        for clave, estudio, seccion, unidades, referencia, _ in CAMPOS:
            if seccion != clave_seccion:
                continue
            filas.append([Paragraph(estudio, cell), Paragraph(f"<b>{_txt(getattr(examen, clave))}</b>", cell),
                          Paragraph(unidades or "—", cell), Paragraph(referencia or "—", cell)])
        tabla = Table(filas, colWidths=[200, 150, 70, 144])
        tabla.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), FONDO_ENC),
            ("GRID", (0, 0), (-1, -1), 0.5, BORDE),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        nota = ""
        if clave_seccion == "quimico":
            nota = " (tira reactiva)" if examen.quimico_fuente == "tira_uc1000" else ""
        elements += [Paragraph(f"<b>{nombre_seccion.upper()}</b>{nota}", section), tabla]

    if examen.observaciones:
        elements += [Paragraph("<b>OBSERVACIONES</b>", section), Paragraph(escape(examen.observaciones), body)]

    # Pie
    quimico = examen.quimico
    # Los exámenes guardados siempre traen químico; la guarda cubre registros antiguos sin él
    validado = (f"<b>Validado por:</b> {escape(quimico.nombre_completo)} (Cédula: {escape(quimico.cedula)})"
                if quimico else "")
    pie = Table([[
        Paragraph("<i>Este es un documento confidencial e intransferible emitido para uso médico.</i>", subtitle),
        Paragraph(validado, ParagraphStyle("V", parent=body, alignment=TA_RIGHT)),
    ]], colWidths=[364, 200])
    pie.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "BOTTOM")]))
    elements += [Spacer(1, 10), pie]

    def fondo(canvas, _doc):
        bg = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Picture1.jpg")
        if os.path.exists(bg):
            canvas.saveState()
            try:
                canvas.drawImage(bg, 0, 0, width=612, height=792)
            except Exception:
                pass
            canvas.restoreState()

    doc.build(elements, onFirstPage=fondo, onLaterPages=fondo)
    return buffer.getvalue()
