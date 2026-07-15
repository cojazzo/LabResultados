import os
from datetime import datetime
from decimal import Decimal
from jinja2 import Environment, FileSystemLoader
try:
    from weasyprint import HTML
    WEASYPRINT_AVAILABLE = True
except Exception as e:
    import logging
    logging.warning(f"WeasyPrint no está disponible: {e}. Se usará ReportLab como generador PDF.")
    WEASYPRINT_AVAILABLE = False

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from app.config import get_settings
from app.models import ReporteGenerado, ReporteResultado, Resultado, Paciente, User

# Importar ReportLab para generación local sin dependencias de sistema C
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

import math

settings = get_settings()

def resolve_sex(paciente) -> bool:
    """Retorna True si es Femenino, False si es Masculino."""
    s = str(paciente.sexo).strip().upper() if paciente.sexo else ""
    if s in ["F", "FEMENINO", "MUJER"]:
        return True
    if s in ["M", "MASCULINO", "HOMBRE"]:
        return False
    # Si es nulo, intentar extraer de la identificación (CURP)
    ident = str(paciente.identificacion).strip().upper()
    if len(ident) >= 11:
        sex_char = ident[10] # El 11vo carácter
        if sex_char == "M":
            return True
        if sex_char == "H":
            return False
    return False

def calculate_egfr(scr: float, age: float, is_female: bool) -> tuple[float, str]:
    """
    Calcula la TFG (eGFR) utilizando la fórmula adecuada según la edad.
    Retorna (egfr, formula_name).
    """
    if age < 25:
        calc_age = max(age, 2.0)
        if is_female:
            ln_q = 3.080 + 0.177 * calc_age - 0.223 * math.log(calc_age) - 0.00596 * (calc_age ** 2) + 0.0000686 * (calc_age ** 3)
        else:
            ln_q = 3.200 + 0.259 * calc_age - 0.543 * math.log(calc_age) - 0.00763 * (calc_age ** 2) + 0.0000790 * (calc_age ** 3)
        
        q_umol = math.exp(ln_q)
        q_mgdl = q_umol / 88.42
        
        ratio = scr / q_mgdl
        if ratio < 1.0:
            egfr = 107.3 * (ratio ** -0.322)
        else:
            egfr = 107.3 * (ratio ** -1.132)
            
        return egfr, "CKD-EPI U25 (EKFC)"
    else:
        kappa = 0.7 if is_female else 0.9
        alpha = -0.241 if is_female else -0.302
        gender_mult = 1.012 if is_female else 1.0
        
        term1 = min(scr / kappa, 1.0) ** alpha
        term2 = max(scr / kappa, 1.0) ** (-1.200)
        term3 = 0.9938 ** age
        
        egfr = 142 * term1 * term2 * term3 * gender_mult
        return egfr, "CKD-EPI 2021"

def get_kdigo_classification(egfr: float | None, acr: float | None) -> dict:
    """
    Determina la clasificación KDIGO basada en TFG (eGFR) y ACR.
    Retorna un diccionario con detalles de riesgo y recomendaciones.
    """
    g_cat = None
    g_desc = ""
    if egfr is not None:
        if egfr >= 90:
            g_cat = "G1"
            g_desc = "Normal o elevado"
        elif egfr >= 60:
            g_cat = "G2"
            g_desc = "Ligeramente disminuido"
        elif egfr >= 45:
            g_cat = "G3a"
            g_desc = "Disminuido leve a moderado"
        elif egfr >= 30:
            g_cat = "G3b"
            g_desc = "Disminuido moderado a grave"
        elif egfr >= 15:
            g_cat = "G4"
            g_desc = "Disminuido gravemente"
        else:
            g_cat = "G5"
            g_desc = "Fallo renal"

    a_cat = None
    a_desc = ""
    if acr is not None:
        if acr < 30:
            a_cat = "A1"
            a_desc = "Normal a ligeramente aumentado"
        elif acr <= 300:
            a_cat = "A2"
            a_desc = "Moderadamente aumentado"
        else:
            a_cat = "A3"
            a_desc = "Gravemente aumentado"

    color = "gray"
    riesgo = "Datos insuficientes"
    recomendacion = "Complete los estudios de TFG y ACR para evaluar el riesgo KDIGO."
    
    if g_cat and a_cat:
        if g_cat in ["G1", "G2"]:
            if a_cat == "A1":
                color = "green"
                riesgo = "Riesgo Bajo"
                recomendacion = "Función renal normal. Mantenga hábitos de vida saludables (buena hidratación, dieta balanceada y control de peso)."
            elif a_cat == "A2":
                color = "yellow"
                riesgo = "Riesgo Moderado"
                recomendacion = "Albuminuria moderada. Se recomienda repetir la prueba en 3 meses para confirmar persistencia y monitorear hábitos de salud."
            elif a_cat == "A3":
                color = "orange"
                riesgo = "Riesgo Alto"
                recomendacion = "Albuminuria severa. Se recomienda valoración médica para iniciar tratamiento protector de la función renal y repetir estudios de control."
        elif g_cat == "G3a":
            if a_cat == "A1":
                color = "yellow"
                riesgo = "Riesgo Moderado"
                recomendacion = "TFG disminuida levemente. Se sugiere repetir estudios de control y consultar con su médico para evaluar factores de riesgo."
            elif a_cat == "A2":
                color = "orange"
                riesgo = "Riesgo Alto"
                recomendacion = "TFG disminuida y albuminuria moderada. Requiere valoración médica formal para control de factores (presión arterial, glucemia)."
            elif a_cat == "A3":
                color = "red"
                riesgo = "Riesgo Muy Alto"
                recomendacion = "Función renal alterada de forma importante. Busque atención médica/nefrología a la brevedad para tratamiento especializado."
        elif g_cat == "G3b":
            if a_cat == "A1":
                color = "orange"
                riesgo = "Riesgo Alto"
                recomendacion = "TFG disminuida de forma moderada a grave. Requiere consulta médica regular para monitoreo de la función renal."
            else:
                color = "red"
                riesgo = "Riesgo Muy Alto"
                recomendacion = "Función renal comprometida. Busque atención médica especializada de inmediato para evitar la progresión de la enfermedad."
        elif g_cat in ["G4", "G5"]:
            color = "red"
            riesgo = "Riesgo Muy Alto"
            recomendacion = "TFG muy baja (insuficiencia renal avanzada). Requiere atención médica/nefrológica especializada con urgencia para manejo de complicaciones."

    return {
        "g_cat": g_cat,
        "g_desc": g_desc,
        "a_cat": a_cat,
        "a_desc": a_desc,
        "color": color,
        "riesgo": riesgo,
        "recomendacion": recomendacion
    }

def get_jinja_env():
    """Obtiene el entorno Jinja2 para cargar plantillas."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    templates_dir = os.path.join(base_dir, "templates")
    os.makedirs(templates_dir, exist_ok=True)
    return Environment(loader=FileSystemLoader(templates_dir))

def generate_reportlab_pdf(pdf_path, context):
    """Genera un reporte de función renal profesional utilizando ReportLab en una sola hoja."""
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=letter,
        rightMargin=24,
        leftMargin=24,
        topMargin=24,
        bottomMargin=24
    )
    
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'LabTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=12,
        textColor=colors.HexColor('#1e3a5f'),
        spaceAfter=1
    )
    
    subtitle_style = ParagraphStyle(
        'LabSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        textColor=colors.HexColor('#64748b'),
        spaceAfter=1
    )
    
    section_title = ParagraphStyle(
        'SectionTitle',
        parent=styles['Heading3'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        textColor=colors.HexColor('#0d9488'),
        spaceBefore=4,
        spaceAfter=1
    )
    
    body_style = ParagraphStyle(
        'BodyText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        textColor=colors.HexColor('#334155')
    )
    
    cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        textColor=colors.HexColor('#334155')
    )
    
    cell_bold = ParagraphStyle(
        'TableCellBold',
        parent=cell_style,
        fontName='Helvetica-Bold'
    )
    
    elements = [Spacer(1, 120)]
    
    # Encabezado
    address_str = context['lab_address'].replace(" Fideicomiso", "<br/>Fideicomiso")
    header_data = [
        [
            Paragraph(f"<b>{context['lab_name']}</b>", title_style),
            Paragraph(f"<b>FOLIO DE REPORTE</b><br/><font size=10 color='#ef4444'>{context['folio']}</font>", ParagraphStyle('Folio', parent=body_style, alignment=TA_RIGHT))
        ],
        [
            Paragraph(f"{address_str}<br/>Tel: {context['lab_phone']} | Email: {context['lab_email']}", subtitle_style),
            Paragraph(f"Fecha Emisión: {context['fecha_emision']}", ParagraphStyle('Emit', parent=subtitle_style, alignment=TA_RIGHT))
        ]
    ]
    header_table = Table(header_data, colWidths=[400, 164])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 2))
    
    divider = Table([[""]], colWidths=[564], rowHeights=[1])
    divider.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#1e3a5f')),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
    ]))
    elements.append(divider)
    elements.append(Spacer(1, 2))
    
    # Paciente y médico
    paciente = context['paciente']
    medico = context['medico']
    
    dob = paciente.fecha_nacimiento
    ft_date = datetime.strptime(context['fecha_toma'], "%d/%m/%Y").date() if isinstance(context['fecha_toma'], str) else context['fecha_toma']
    if dob:
        if hasattr(dob, "date"):
            dob = dob.date()
        age = ft_date.year - dob.year - ((ft_date.month, ft_date.day) < (dob.month, dob.day))
    else:
        age = 45
        
    is_female = resolve_sex(paciente)
    sex_desc = "Femenino" if is_female else "Masculino"
    
    info_data = [
        [
            Paragraph("<b>INFORMACIÓN DEL PACIENTE</b>", section_title),
            ""
        ],
        [
            Paragraph(f"<b>Nombre:</b> {paciente.nombre} {paciente.apellido}", body_style),
            Paragraph(f"<b>Identificación/CURP:</b> {paciente.identificacion}", body_style)
        ],
        [
            Paragraph(f"<b>Edad:</b> {age} años | <b>Sexo:</b> {sex_desc}", body_style),
            Paragraph(f"<b>Fecha de Toma:</b> {ft_date.strftime('%d/%m/%Y')}", body_style)
        ]
    ]
    info_table = Table(info_data, colWidths=[282, 282])
    info_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0.5),
        ('TOPPADDING', (0,0), (-1,-1), 0.5),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 2))
    
    # Extraer valores de resultados
    crts = None
    cre01 = None
    albor = None
    acr = None
    
    for r in context['resultados']:
        code = r.prueba.codigo.upper()
        val = float(r.valor) if r.valor is not None else None
        if code == "CRTS":
            crts = val
        elif code == "CRE01":
            cre01 = val
        elif code == "ALBOR":
            albor = val
        elif code == "ACR":
            acr = val
            
    if acr is None and albor is not None and cre01 is not None and cre01 > 0:
        acr = (albor / cre01) * 100
        
    egfr = None
    formula_name = "N/A"
    if crts is not None:
        egfr, formula_name = calculate_egfr(crts, age, is_female)
        
    # SECCIÓN 1: EVALUACIÓN DE FUNCIÓN GLOMERULAR (TFG)
    elements.append(Paragraph("<b>1. EVALUACIÓN DE FUNCIÓN GLOMERULAR (TFG)</b>", section_title))
    tfg_rows = [
        [
            Paragraph("<b>Prueba / Parámetro</b>", cell_bold),
            Paragraph("<b>Resultado</b>", cell_bold),
            Paragraph("<b>Unidades</b>", cell_bold),
            Paragraph("<b>Límites de Referencia</b>", cell_bold),
            Paragraph("<b>Método/Fórmula</b>", cell_bold)
        ]
    ]
    
    if crts is not None:
        ref_crts = "0.6 - 1.2" if not is_female else "0.5 - 1.1"
        tfg_rows.append([
            Paragraph("Creatinina Sérica (CRTS)", cell_style),
            Paragraph(f"<b>{crts:.2f}</b>", cell_bold),
            Paragraph("mg/dL", cell_style),
            Paragraph(ref_crts, cell_style),
            Paragraph("Jaffé cinético / Enzimático", cell_style)
        ])
        
    if egfr is not None:
        egfr_val_str = f"{egfr:.1f}"
        int_color = "#16a34a" if egfr >= 60 else "#dc2626"
        tfg_rows.append([
            Paragraph("Tasa de Filtración Glomerular Estimada (eGFR)", cell_bold),
            Paragraph(f"<font color='{int_color}'><b>{egfr_val_str}</b></font>", cell_bold),
            Paragraph("mL/min/1.73m²", cell_style),
            Paragraph("&gt;= 90.0", cell_style),
            Paragraph(formula_name, cell_bold)
        ])
    else:
        tfg_rows.append([
            Paragraph("Tasa de Filtración Glomerular Estimada (eGFR)", cell_bold),
            Paragraph("<font color='gray'>Falta CRTS</font>", cell_style),
            Paragraph("mL/min/1.73m²", cell_style),
            Paragraph("&gt;= 90.0", cell_style),
            Paragraph("N/A", cell_style)
        ])
        
    tfg_table = Table(tfg_rows, colWidths=[190, 80, 84, 100, 110])
    tfg_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f1f5f9')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ('TOPPADDING', (0,0), (-1,-1), 2),
    ]))
    elements.append(tfg_table)
    elements.append(Spacer(1, 2))
    
    # SECCIÓN 2: PERFIL DE ALBUMINURIA (ACR)
    elements.append(Paragraph("<b>2. PERFIL DE ALBUMINURIA</b>", section_title))
    acr_rows = [
        [
            Paragraph("<b>Prueba / Parámetro</b>", cell_bold),
            Paragraph("<b>Resultado</b>", cell_bold),
            Paragraph("<b>Unidades</b>", cell_bold),
            Paragraph("<b>Rango de Referencia</b>", cell_bold),
            Paragraph("<b>Descripción</b>", cell_bold)
        ]
    ]
    
    albor_str = f"{albor:.1f}" if albor is not None else "No solicitado"
    acr_rows.append([
        Paragraph("Albúmina en Orina (ALBOR)", cell_style),
        Paragraph(albor_str, cell_bold if albor is not None else cell_style),
        Paragraph("mg/L", cell_style),
        Paragraph("&lt; 20.0", cell_style),
        Paragraph("Inmunoturbidimetría", cell_style)
    ])
    
    cre01_str = f"{cre01:.1f}" if cre01 is not None else "No solicitado"
    acr_rows.append([
        Paragraph("Creatinina Urinaria (CRE01)", cell_style),
        Paragraph(cre01_str, cell_bold if cre01 is not None else cell_style),
        Paragraph("mg/dL", cell_style),
        Paragraph("39.0 - 259.0", cell_style),
        Paragraph("Jaffé / Enzimático", cell_style)
    ])
    
    if acr is not None:
        acr_val_str = f"{acr:.1f}"
        if acr < 30:
            int_color = "#16a34a"
            acr_desc = "Normal a leve (<30)"
        elif acr <= 300:
            int_color = "#ca8a04"
            acr_desc = "Moderado (30-300)"
        else:
            int_color = "#dc2626"
            acr_desc = "Severo (>300)"
            
        acr_rows.append([
            Paragraph("Relación Albúmina/Creatinina (ACR)", cell_bold),
            Paragraph(f"<font color='{int_color}'><b>{acr_val_str}</b></font>", cell_bold),
            Paragraph("mg/g", cell_style),
            Paragraph("&lt; 30.0", cell_style),
            Paragraph(acr_desc, cell_bold)
        ])
    else:
        acr_rows.append([
            Paragraph("Relación Albúmina/Creatinina (ACR)", cell_bold),
            Paragraph("<font color='gray'>Faltan datos</font>", cell_style),
            Paragraph("mg/g", cell_style),
            Paragraph("&lt; 30.0", cell_style),
            Paragraph("Requiere ALBOR + CRE01", cell_style)
        ])
        
    acr_table = Table(acr_rows, colWidths=[190, 80, 84, 100, 110])
    acr_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f1f5f9')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ('TOPPADDING', (0,0), (-1,-1), 2),
    ]))
    elements.append(acr_table)
    elements.append(Spacer(1, 2))
    
    # SECCIÓN 3: CLASIFICACIÓN DE RIESGO KDIGO (SEMÁFORO)
    kdigo = get_kdigo_classification(egfr, acr)
    g_cat = kdigo["g_cat"]
    a_cat = kdigo["a_cat"]
    
    elements.append(Paragraph("<b>3. MATRIZ DE RIESGO RENAL KDIGO (ESTADIFICACIÓN)</b>", section_title))
    
    if egfr is None:
        kdigo_matrix = [
            ["Solo ACR", "green", "yellow", "orange"]
        ]
    else:
        kdigo_matrix = [
            ["G1 (>= 90)", "green", "yellow", "orange"],
            ["G2 (60-89)", "green", "yellow", "orange"],
            ["G3a (45-59)", "yellow", "orange", "red"],
            ["G3b (30-44)", "orange", "red", "red"],
            ["G4 (15-29)", "red", "red", "red"],
            ["G5 (< 15)", "red", "red", "red"]
        ]
    
    colors_hex = {
        "green": "#dcfce7",
        "yellow": "#fef9c3",
        "orange": "#ffedd5",
        "red": "#fee2e2"
    }
    
    colors_text = {
        "green": "#16a34a",
        "yellow": "#ca8a04",
        "orange": "#ea580c",
        "red": "#dc2626"
    }
    
    riesgo_names = {
        "green": "Bajo Riesgo",
        "yellow": "Moderado",
        "orange": "Alto Riesgo",
        "red": "Muy Alto"
    }
    
    kdigo_data = [
        [
            Paragraph("<b>TFG / ACR</b>", cell_bold),
            Paragraph("<b>A1</b><br/>&lt;30 mg/g", ParagraphStyle('TH1', parent=cell_bold, alignment=TA_CENTER)),
            Paragraph("<b>A2</b><br/>30-300 mg/g", ParagraphStyle('TH2', parent=cell_bold, alignment=TA_CENTER)),
            Paragraph("<b>A3</b><br/>&gt;300 mg/g", ParagraphStyle('TH3', parent=cell_bold, alignment=TA_CENTER))
        ]
    ]
    
    kdigo_styles = [
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 1, colors.HexColor('#cbd5e1')),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f8fafc')),
        ('BACKGROUND', (0,1), (0,-1), colors.HexColor('#f8fafc')),
        ('BOTTOMPADDING', (0,0), (-1,-1), 1.5),
        ('TOPPADDING', (0,0), (-1,-1), 1.5),
    ]
    
    for row_idx, row_info in enumerate(kdigo_matrix, 1):
        g_stage = row_info[0]
        label = g_stage if egfr is not None else "Nivel de Albuminuria"
        row_cells = [Paragraph(f"<b>{label}</b>", cell_style)]
        
        for col_idx, color_name in enumerate(row_info[1:], 1):
            a_stage = f"A{col_idx}"
            if egfr is not None:
                is_patient_cell = (g_cat == g_stage.split()[0] and a_cat == a_stage)
            else:
                is_patient_cell = (a_cat == a_stage)
            
            cell_bg = colors_hex[color_name]
            cell_text_color = colors_text[color_name]
            
            p_text = f"<font color='{cell_text_color}'><b>{riesgo_names[color_name]}</b></font>"
            
            if is_patient_cell:
                kdigo_styles.append(('LINEBELOW', (col_idx, row_idx), (col_idx, row_idx), 2, colors.HexColor('#1e3a5f')))
                kdigo_styles.append(('LINEABOVE', (col_idx, row_idx), (col_idx, row_idx), 2, colors.HexColor('#1e3a5f')))
                kdigo_styles.append(('LINEBEFORE', (col_idx, row_idx), (col_idx, row_idx), 2, colors.HexColor('#1e3a5f')))
                kdigo_styles.append(('LINEAFTER', (col_idx, row_idx), (col_idx, row_idx), 2, colors.HexColor('#1e3a5f')))
                
            row_cells.append(Paragraph(p_text, ParagraphStyle('TC', parent=cell_style, alignment=TA_CENTER)))
            kdigo_styles.append(('BACKGROUND', (col_idx, row_idx), (col_idx, row_idx), colors.HexColor(cell_bg)))
            
        kdigo_data.append(row_cells)
        
    kdigo_table = Table(kdigo_data, colWidths=[130, 144, 145, 145])
    kdigo_table.setStyle(TableStyle(kdigo_styles))
    elements.append(kdigo_table)
    elements.append(Spacer(1, 2))
    
    # SECCIÓN 4: RECOMENDACIÓN CLÍNICA
    elements.append(Paragraph("<b>4. EVALUACIÓN Y RECOMENDACIÓN CLÍNICA</b>", section_title))
    
    rec_bg = "#f8fafc"
    rec_border = "#cbd5e1"
    if kdigo["color"] == "green":
        rec_bg = "#f0fdf4"
        rec_border = "#bbf7d0"
    elif kdigo["color"] == "yellow":
        rec_bg = "#fefce8"
        rec_border = "#fef08a"
    elif kdigo["color"] == "orange":
        rec_bg = "#fff7ed"
        rec_border = "#fed7aa"
    elif kdigo["color"] == "red":
        rec_bg = "#fef2f2"
        rec_border = "#fecaca"
        
    rec_text = f"<b>Nivel de Riesgo KDIGO:</b> <font color='{colors_text.get(kdigo['color'], '#000000')}'><b>{kdigo['riesgo'].upper()}</b></font><br/>"
    if g_cat and a_cat:
        rec_text += f"Estadificación: <b>TFG {g_cat} ({kdigo['g_desc']})</b> y <b>ACR {a_cat} ({kdigo['a_desc']})</b>.<br/>"
    rec_text += f"<b>Recomendación:</b> {kdigo['recomendacion']}"
    
    rec_table = Table([[Paragraph(rec_text, body_style)]], colWidths=[564])
    rec_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor(rec_bg)),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor(rec_border)),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    elements.append(rec_table)
    elements.append(Spacer(1, 4))
    
    # Pie de página
    footer_data = [
        [
            Paragraph("<i>Este es un documento confidencial e intransferible emitido para uso médico.</i>", subtitle_style),
            Paragraph(f"<b>Validado por:</b> {context['usuario_nombre']}", ParagraphStyle('Val', parent=body_style, alignment=TA_RIGHT))
        ]
    ]
    footer_table = Table(footer_data, colWidths=[364, 200])
    footer_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'BOTTOM'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
    ]))
    elements.append(footer_table)
    
    def draw_background(canvas, doc):
        canvas.saveState()
        # Ruta de la imagen de fondo copiada dentro del contenedor
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        bg_image = os.path.join(base_dir, "Picture1.jpg")
        if os.path.exists(bg_image):
            try:
                canvas.drawImage(bg_image, 0, 0, width=612, height=792)
            except Exception as e:
                import logging
                logging.error(f"Error cargando imagen de fondo: {e}")
        canvas.restoreState()
    
    doc.build(elements, onFirstPage=draw_background, onLaterPages=draw_background)

async def generate_report_pdf(db: AsyncSession, paciente_id: int, resultado_ids: list[int], generado_por: int, lote_id: int = None, quimico_id: int = None) -> ReporteGenerado:
    """
    Genera un archivo PDF para los resultados seleccionados de un paciente.
    Crea el registro de ReporteGenerado y de las relaciones en ReporteResultado.
    """
    # 1. Cargar paciente y usuario generador
    paciente_res = await db.execute(select(Paciente).where(Paciente.id == paciente_id))
    paciente = paciente_res.scalar_one_or_none()
    if not paciente:
        raise ValueError(f"Paciente con ID {paciente_id} no encontrado")

    usuario_res = await db.execute(select(User).where(User.id == generado_por))
    usuario = usuario_res.scalar_one_or_none()
    usuario_nombre = usuario.nombre_completo if usuario else "Sistema"
    
    from app.models import Quimico
    if quimico_id:
        quimico_res = await db.execute(select(Quimico).where(Quimico.id == quimico_id))
        quimico = quimico_res.scalar_one_or_none()
        if quimico:
            usuario_nombre = f"{quimico.nombre_completo} (Cédula: {quimico.cedula})"
    else:
        # Fallback a un químico activo si no se especificó uno
        quimico_res = await db.execute(select(Quimico).where(Quimico.activo == True).limit(1))
        quimico = quimico_res.scalar_one_or_none()
        if quimico:
            usuario_nombre = f"{quimico.nombre_completo} (Cédula: {quimico.cedula})"

    # 2. Cargar los resultados seleccionados
    resultados_res = await db.execute(
        select(Resultado)
        .where(Resultado.id.in_(resultado_ids))
        .options(selectinload(Resultado.prueba), selectinload(Resultado.medico))
    )
    resultados = resultados_res.scalars().all()
    if not resultados:
        raise ValueError("No se encontraron resultados para incluir en el reporte")

    # Tomar la fecha de toma más representativa y el médico
    fecha_toma = resultados[0].fecha_toma
    medico = resultados[0].medico

    # 3. Extraer folio de observaciones
    folio_extraido = None
    for res in resultados:
        if res.observaciones and "Petición No." in res.observaciones:
            parts = res.observaciones.split("Petición No.")
            if len(parts) > 1:
                folio_raw = parts[1].strip()
                folio_extraido = folio_raw.replace("/", "-").replace("\\", "-")
                break

    # 4. Buscar si ya existe un reporte no autorizado
    stmt_exist = select(ReporteGenerado).where(
        ReporteGenerado.paciente_id == paciente.id,
        ReporteGenerado.lote_id == lote_id,
        ReporteGenerado.authorized_at.is_(None)
    )
    reporte = (await db.execute(stmt_exist)).scalar_one_or_none()

    if reporte:
        folio = folio_extraido if folio_extraido else reporte.folio
        reporte.folio = folio
        # Borrar relaciones anteriores
        await db.execute(
            ReporteResultado.__table__.delete().where(
                ReporteResultado.reporte_id == reporte.id
            )
        )
    else:
        folio = folio_extraido
        if not folio:
            year = datetime.now().year
            stmt = select(func.count(ReporteGenerado.id))
            count_res = await db.execute(stmt)
            count = count_res.scalar() or 0
            folio = f"LAB-{year}-{count + 1:06d}"

    # 4. Preparar directorio de guardado
    os.makedirs(settings.PDF_STORAGE_PATH, exist_ok=True)
    pdf_filename = f"{folio}.pdf"
    pdf_path = os.path.join(settings.PDF_STORAGE_PATH, pdf_filename)

    # 5. Preparar contexto para la generación del PDF
    context = {
        "lab_name": settings.LAB_NAME,
        "lab_address": settings.LAB_ADDRESS,
        "lab_phone": settings.LAB_PHONE,
        "lab_email": settings.LAB_EMAIL,
        "folio": folio,
        "fecha_emision": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "paciente": paciente,
        "medico": medico,
        "fecha_toma": fecha_toma.strftime("%d/%m/%Y"),
        "resultados": resultados,
        "usuario_nombre": usuario_nombre
    }

    # Siempre usar ReportLab para generar el reporte completo con matriz KDIGO
    generate_reportlab_pdf(pdf_path, context)

    # 7. Registrar en Base de Datos (o actualizar)
    if not reporte:
        reporte = ReporteGenerado(
            paciente_id=paciente.id,
            lote_id=lote_id,
            folio=folio,
            ruta_archivo=pdf_path,
            generado_por=generado_por,
            estado="generado"
        )
        db.add(reporte)
        await db.flush()
    else:
        # Actualizar metadata si es necesario
        reporte.ruta_archivo = pdf_path
        reporte.generado_por = generado_por
        reporte.fecha_generacion = datetime.now()
        await db.flush()

    # Agregar relaciones ReporteResultado
    for res in resultados:
        rep_res = ReporteResultado(
            reporte_id=reporte.id,
            resultado_id=res.id
        )
        db.add(rep_res)

    await db.commit()
    await db.refresh(reporte)
    return reporte

async def generate_batch_reports(db: AsyncSession, lote_id: int, generado_por: int, quimico_id: int = None) -> list[ReporteGenerado]:
    """
    Genera reportes PDF para todos los pacientes que tienen resultados en un lote.
    Agrupa los resultados por paciente y genera un PDF por cada uno.
    """
    # Buscar todos los resultados de este lote
    stmt = select(Resultado).where(Resultado.lote_id == lote_id)
    res_result = await db.execute(stmt)
    resultados = res_result.scalars().all()

    if not resultados:
        return []

    # Agrupar por paciente_id
    pacientes_resultados = {}
    for res in resultados:
        if res.paciente_id not in pacientes_resultados:
            pacientes_resultados[res.paciente_id] = []
        pacientes_resultados[res.paciente_id].append(res.id)

    reportes_creados = []
    for pac_id, res_ids in pacientes_resultados.items():
        try:
            reporte = await generate_report_pdf(db, pac_id, res_ids, generado_por, lote_id=lote_id, quimico_id=quimico_id)
            reportes_creados.append(reporte)
        except Exception as e:
            print(f"Error generando reporte para paciente {pac_id}: {str(e)}")
            continue

    return reportes_creados
