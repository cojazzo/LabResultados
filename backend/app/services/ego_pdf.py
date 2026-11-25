"""
PDF del Examen General de Orina (EGO). Mismo encabezado, fondo y pie que el reporte renal,
con las tablas del formato INAER: examen físico, químico y microscópico.
Solo muestra lo capturado; no interpreta resultados.

También genera el formato EGO en blanco (`generar_formato_ego_en_blanco`) para llenarlo a mano: el químico lo
escribe y el técnico lo transcribe a la pantalla de captura. Usa los mismos campos, unidades y referencias.
"""

import io
import os
from datetime import date, datetime
from types import SimpleNamespace

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


# ── Piezas compartidas (reporte y formato en blanco) ──────────────────────────

def _estilos() -> SimpleNamespace:
    styles = getSampleStyleSheet()
    title = ParagraphStyle("T", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=12, textColor=AZUL, spaceAfter=1)
    subtitle = ParagraphStyle("S", parent=styles["Normal"], fontName="Helvetica", fontSize=7.5, textColor=GRIS)
    section = ParagraphStyle("Sec", parent=styles["Heading3"], fontName="Helvetica-Bold", fontSize=8.5, textColor=TEAL, spaceBefore=6, spaceAfter=2)
    body = ParagraphStyle("B", parent=styles["Normal"], fontName="Helvetica", fontSize=7.5, textColor=TEXTO)
    return SimpleNamespace(
        title=title, subtitle=subtitle, section=section, body=body,
        cell=ParagraphStyle("C", parent=body),
        cell_b=ParagraphStyle("CB", parent=body, fontName="Helvetica-Bold"),
        titulo_doc=ParagraphStyle("TD", parent=title, fontSize=11, alignment=1, spaceBefore=4, spaceAfter=2),
        derecha=ParagraphStyle("D", parent=body, alignment=TA_RIGHT),
        subtitulo_derecha=ParagraphStyle("SD", parent=subtitle, alignment=TA_RIGHT),
    )


def _encabezado(settings, est: SimpleNamespace, folio_html: str, emision_html: str, titulo: str,
                espacio_superior: int = 120) -> list:
    """Encabezado institucional (nombre, dirección, folio), línea azul y título del documento."""
    address = settings.LAB_ADDRESS.replace(" Fideicomiso", "<br/>Fideicomiso")
    header = Table([
        [Paragraph(f"<b>{settings.LAB_NAME}</b>", est.title),
         Paragraph(f"<b>FOLIO DE REPORTE</b><br/>{folio_html}", est.derecha)],
        [Paragraph(f"{address}<br/>Tel: {settings.LAB_PHONE} | Email: {settings.LAB_EMAIL}", est.subtitle),
         Paragraph(emision_html, est.subtitulo_derecha)],
    ], colWidths=[400, 164])
    header.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOTTOMPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0)]))
    divider = Table([[""]], colWidths=[564], rowHeights=[1])
    divider.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), AZUL)]))
    return [Spacer(1, espacio_superior), header, Spacer(1, 2), divider, Paragraph(titulo, est.titulo_doc)]


def _fondo(canvas, _doc):
    """Fondo institucional de la página (mismo que el reporte renal)."""
    bg = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Picture1.jpg")
    if os.path.exists(bg):
        canvas.saveState()
        try:
            canvas.drawImage(bg, 0, 0, width=612, height=792)
        except Exception:
            pass
        canvas.restoreState()


def _documento(buffer) -> SimpleDocTemplate:
    return SimpleDocTemplate(buffer, pagesize=letter, rightMargin=24, leftMargin=24, topMargin=24, bottomMargin=24)


# ── Reporte del examen capturado ──────────────────────────────────────────────

def generar_pdf_ego(examen: ExamenOrina) -> bytes:
    """`examen` debe traer cargados `paciente` y `quimico`."""
    settings = get_settings()
    buffer = io.BytesIO()
    doc = _documento(buffer)
    est = _estilos()

    paciente = examen.paciente
    folio = folio_ego(examen)
    elements = _encabezado(
        settings, est, f"<font size=10 color='#ef4444'>{folio}</font>",
        f"Fecha Emisión: {datetime.now():%d/%m/%Y %H:%M}", "EXAMEN GENERAL DE ORINA")

    # Paciente
    edad = _edad(paciente.fecha_nacimiento, examen.fecha_toma)
    sexo = "Femenino" if resolve_sex(paciente) else "Masculino"
    info = Table([
        [Paragraph("<b>INFORMACIÓN DEL PACIENTE</b>", est.section), ""],
        [Paragraph(f"<b>Nombre:</b> {escape(nombre_completo_paciente(paciente))}", est.body),
         Paragraph(f"<b>Identificación/CURP:</b> {escape(paciente.identificacion)}", est.body)],
        [Paragraph(f"<b>Edad:</b> {f'{edad} años' if edad is not None else '—'} | <b>Sexo:</b> {sexo}", est.body),
         Paragraph(f"<b>Fecha de Toma:</b> {examen.fecha_toma:%d/%m/%Y}", est.body)],
    ], colWidths=[282, 282])
    info.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOTTOMPADDING", (0, 0), (-1, -1), 0.5), ("TOPPADDING", (0, 0), (-1, -1), 0.5)]))
    elements.append(info)

    # Secciones
    for clave_seccion, nombre_seccion in SECCIONES:
        filas = [[Paragraph("<b>Estudio</b>", est.cell_b), Paragraph("<b>Resultado</b>", est.cell_b),
                  Paragraph("<b>Unidades</b>", est.cell_b), Paragraph("<b>Valores de referencia</b>", est.cell_b)]]
        for clave, estudio, seccion, unidades, referencia, _ in CAMPOS:
            if seccion != clave_seccion:
                continue
            filas.append([Paragraph(estudio, est.cell), Paragraph(f"<b>{_txt(getattr(examen, clave))}</b>", est.cell),
                          Paragraph(unidades or "—", est.cell), Paragraph(referencia or "—", est.cell)])
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
        elements += [Paragraph(f"<b>{nombre_seccion.upper()}</b>{nota}", est.section), tabla]

    if examen.observaciones:
        elements += [Paragraph("<b>OBSERVACIONES</b>", est.section), Paragraph(escape(examen.observaciones), est.body)]

    # Pie
    quimico = examen.quimico
    # Los exámenes guardados siempre traen químico; la guarda cubre registros antiguos sin él
    validado = (f"<b>Validado por:</b> {escape(quimico.nombre_completo)} (Cédula: {escape(quimico.cedula)})"
                if quimico else "")
    pie = Table([[
        Paragraph("<i>Este es un documento confidencial e intransferible emitido para uso médico.</i>", est.subtitle),
        Paragraph(validado, est.derecha),
    ]], colWidths=[364, 200])
    pie.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "BOTTOM")]))
    elements += [Spacer(1, 10), pie]

    doc.build(elements, onFirstPage=_fondo, onLaterPages=_fondo)
    return buffer.getvalue()


# ── Formato en blanco para llenar a mano ──────────────────────────────────────

ALTO_FILA = 15          # alto de cada renglón de resultado (cabe escritura a mano)
ALTO_SEDIMENTO = 34     # el sedimento se describe con más texto
ALTO_LINEA = 15
BANDA = colors.HexColor("#e0f2f1")


def generar_formato_ego_en_blanco() -> bytes:
    """
    Formato del EGO sin datos, con el encabezado y fondo institucionales, para llenarlo a mano. Cabe en una hoja
    carta. Trae los mismos estudios, unidades y valores de referencia que el reporte; el químico lo escribe y el
    técnico lo transcribe en la pantalla de captura. No incluye interpretaciones.
    """
    settings = get_settings()
    buffer = io.BytesIO()
    doc = _documento(buffer)
    est = _estilos()

    elements = _encabezado(
        settings, est, "No. ____________________", "Fecha de emisión: ____ / ____ / ________",
        "EXAMEN GENERAL DE ORINA — FORMATO DE REGISTRO", espacio_superior=104)

    # Datos de la persona (renglones para escribir)
    def etiqueta(texto: str) -> Paragraph:
        return Paragraph(f"<b>{texto}</b>", est.body)

    datos = Table([
        [etiqueta("Nombre completo:"), "", etiqueta("Identificación / CURP:"), ""],
        [etiqueta("Fecha de nacimiento:"), Paragraph("____ / ____ / ________", est.body),
         etiqueta("Edad:"), Paragraph("________ años", est.body)],
        [etiqueta("Sexo:"), Paragraph("(&nbsp;&nbsp;&nbsp;&nbsp;) Femenino&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;(&nbsp;&nbsp;&nbsp;&nbsp;) Masculino", est.body),
         etiqueta("Fecha de toma:"), Paragraph("____ / ____ / ________", est.body)],
        [etiqueta("ID de petición / folio:"), "", etiqueta("Servicio / campaña:"), ""],
    ], colWidths=[96, 186, 106, 176], rowHeights=[ALTO_LINEA] * 4)
    datos.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
        ("LINEBELOW", (1, 0), (1, 0), 0.5, GRIS), ("LINEBELOW", (3, 0), (3, 0), 0.5, GRIS),
        ("LINEBELOW", (1, 3), (1, 3), 0.5, GRIS), ("LINEBELOW", (3, 3), (3, 3), 0.5, GRIS),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ]))
    elements += [Paragraph("<b>INFORMACIÓN DEL PACIENTE</b>", est.section), datos, Spacer(1, 4)]

    # Una sola tabla: encabezado de columnas y una banda por sección (examen físico, químico, microscópico)
    filas = [[Paragraph("<b>Estudio</b>", est.cell_b), Paragraph("<b>Resultado</b>", est.cell_b),
              Paragraph("<b>Unidades</b>", est.cell_b), Paragraph("<b>Valores de referencia</b>", est.cell_b)]]
    alturas = [ALTO_FILA - 1]
    estilo = [
        ("BACKGROUND", (0, 0), (-1, 0), FONDO_ENC),
        ("GRID", (0, 0), (-1, -1), 0.5, BORDE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
    ]
    for clave_seccion, nombre_seccion in SECCIONES:
        banda = len(filas)
        filas.append([Paragraph(f"<b>{nombre_seccion.upper()}</b>",
                                ParagraphStyle("Banda", parent=est.cell_b, textColor=TEAL)), "", "", ""])
        alturas.append(ALTO_FILA - 2)
        estilo += [("SPAN", (0, banda), (-1, banda)), ("BACKGROUND", (0, banda), (-1, banda), BANDA)]
        for clave, estudio, seccion, unidades, referencia, _ in CAMPOS:
            if seccion != clave_seccion:
                continue
            filas.append([Paragraph(estudio, est.cell), "", Paragraph(unidades or "", est.cell),
                          Paragraph(referencia or "", est.cell)])
            alturas.append(ALTO_SEDIMENTO if clave == "sedimento" else ALTO_FILA)
    tabla = Table(filas, colWidths=[200, 150, 70, 144], rowHeights=alturas)
    tabla.setStyle(TableStyle(estilo))
    elements.append(tabla)

    # Observaciones: recuadro para escribir
    caja = Table([[""]], colWidths=[564], rowHeights=[34])
    caja.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.5, BORDE)]))
    elements += [Paragraph("<b>OBSERVACIONES</b>", est.section), caja, Spacer(1, 6)]

    # Pie: quién realizó el examen y quién transcribió
    firmas = Table([
        [Paragraph("<b>Químico que realizó el examen</b>", est.body), "",
         Paragraph("<b>Transcribió (técnico)</b>", est.body), ""],
        [Paragraph("Nombre:", est.body), "", Paragraph("Nombre:", est.body), ""],
        [Paragraph("Cédula:", est.body), "", Paragraph("Fecha:", est.body), ""],
        [Paragraph("Firma:", est.body), "", Paragraph("Firma:", est.body), ""],
    ], colWidths=[48, 234, 48, 234], rowHeights=[ALTO_LINEA - 3, ALTO_LINEA + 1, ALTO_LINEA + 1, ALTO_LINEA + 1])
    firmas.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
        ("SPAN", (0, 0), (1, 0)), ("SPAN", (2, 0), (3, 0)),
        ("LINEBELOW", (1, 1), (1, 3), 0.5, GRIS), ("LINEBELOW", (3, 1), (3, 3), 0.5, GRIS),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ]))
    pie = Paragraph("<i>Este es un documento confidencial e intransferible emitido para uso médico.</i>", est.subtitle)
    elements += [firmas, Spacer(1, 3), pie]

    doc.build(elements, onFirstPage=_fondo, onLaterPages=_fondo)
    return buffer.getvalue()
