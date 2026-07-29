import io
import os
from datetime import datetime, date
from typing import List, Optional

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import get_current_user
from app.database import get_db
from app.models import Paciente, Prueba, Resultado, ReporteGenerado, User
from app.services.pdf_generator import generate_report_pdf, generate_batch_reports

router = APIRouter(prefix="/reportes", tags=["Reportes PDF"])


# Mapa: nombre de columna visible → (atributo del modelo | "imc" para calculado)
TAMIZAJE_FIELD_MAP: dict[str, str | None] = {
    "CURP":                     "identificacion",
    "Nombre":                   "nombre",
    "Apellido Paterno":         "apellido",
    "Apellido Materno":         "apellido_materno",
    "Sexo":                     "sexo",
    "Fecha Nacimiento":         "fecha_nacimiento",
    "Peso (kg)":                "peso",
    "Estatura (cm)":            "estatura",
    "IMC":                      None,          # calculado
    "Derechohabiencia":         "derechohabiencia",
    "Padecimientos":            "padecimientos",
    "Tipo de Agua":             "tipo_agua",
    "Cocina con Agua de Llave": "cocina_agua_llave",
}

ALL_TAMIZAJE_COLS = list(TAMIZAJE_FIELD_MAP.keys())


@router.get("/exportar-excel")
async def exportar_excel(
    fecha_inicio: Optional[date] = Query(None, description="Fecha de inicio (YYYY-MM-DD)"),
    fecha_fin: Optional[date] = Query(None, description="Fecha de fin (YYYY-MM-DD)"),
    campos: Optional[str] = Query(
        None,
        description="Columnas de tamizaje a incluir, separadas por coma. Si se omite, se incluyen todas.",
    ),
    prueba_ids: Optional[str] = Query(
        None,
        description="IDs de pruebas de laboratorio a incluir, separados por coma. Si se omite, se incluyen todas.",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Genera y descarga un Excel con una fila por paciente.
    Columnas fijas: datos de tamizaje (filtrables con 'campos').
    Columnas dinámicas: valores de laboratorio agrupados por Toma 1, Toma 2, ...
    Filtrable por rango de fecha de toma de muestra y por pruebas seleccionadas.
    """

    # Resolver columnas de tamizaje seleccionadas
    if campos:
        selected_tamizaje = [c.strip() for c in campos.split(",") if c.strip() in TAMIZAJE_FIELD_MAP]
    else:
        selected_tamizaje = ALL_TAMIZAJE_COLS

    # Resolver IDs de pruebas seleccionadas
    selected_prueba_ids: set[int] | None = None
    if prueba_ids:
        try:
            selected_prueba_ids = {int(pid.strip()) for pid in prueba_ids.split(",") if pid.strip()}
        except ValueError:
            raise HTTPException(status_code=400, detail="prueba_ids debe ser una lista de enteros separados por coma")

    # 1. Obtener resultados en el rango de fechas, cargando relaciones
    stmt = (
        select(Resultado)
        .options(
            selectinload(Resultado.paciente),
            selectinload(Resultado.prueba),
        )
        .order_by(Resultado.paciente_id, Resultado.fecha_toma)
    )
    if fecha_inicio:
        stmt = stmt.where(Resultado.fecha_toma >= fecha_inicio)
    if fecha_fin:
        stmt = stmt.where(Resultado.fecha_toma <= fecha_fin)

    res = await db.execute(stmt)
    resultados = res.scalars().all()

    if not resultados:
        # Devolver Excel vacío con encabezados de tamizaje solamente
        df_empty = pd.DataFrame(columns=[
            "CURP", "Nombre", "Apellido Paterno", "Apellido Materno",
            "Sexo", "Fecha Nacimiento", "Peso (kg)", "Estatura (cm)", "IMC",
            "Derechohabiencia", "Padecimientos", "Tipo de Agua",
            "Cocina con Agua de Llave",
        ])
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df_empty.to_excel(writer, index=False, sheet_name="Reporte")
        output.seek(0)
        filename = _build_filename(fecha_inicio, fecha_fin)
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    # 2. Recopilar todos los IDs de pacientes involucrados para traer datos de tamizaje
    paciente_ids = list({r.paciente_id for r in resultados})
    stmt_pac = select(Paciente).where(Paciente.id.in_(paciente_ids))
    res_pac = await db.execute(stmt_pac)
    pacientes_map: dict[int, Paciente] = {p.id: p for p in res_pac.scalars().all()}

    # 3. Recopilar todas las pruebas en orden para columnas consistentes
    prueba_cols: list[str] = []
    seen_pruebas: set[str] = set()
    for r in sorted(resultados, key=lambda x: (x.paciente_id, x.fecha_toma, x.prueba.nombre)):
        key = f"{r.prueba.nombre} ({r.prueba.unidad})"
        if key not in seen_pruebas:
            seen_pruebas.add(key)
            prueba_cols.append(key)

    # 4. Agrupar resultados por paciente y asignar número de toma
    from collections import defaultdict
    pac_resultados: dict[int, list[Resultado]] = defaultdict(list)
    for r in resultados:
        pac_resultados[r.paciente_id].append(r)

    max_tomas = 0
    # Estructura: { paciente_id: { toma_num: { prueba_col: valor, 'fecha': fecha } } }
    pac_tomas: dict[int, dict[int, dict]] = {}
    for pac_id, res_list in pac_resultados.items():
        # Fechas únicas ordenadas → cada fecha es una toma
        fechas_unicas = sorted({r.fecha_toma for r in res_list})
        tomas: dict[int, dict] = {}
        for idx, fecha in enumerate(fechas_unicas, start=1):
            toma_data: dict = {"fecha": fecha}
            for r in res_list:
                if r.fecha_toma == fecha:
                    col = f"{r.prueba.nombre} ({r.prueba.unidad})"
                    toma_data[col] = float(r.valor) if r.valor is not None else (r.valor_texto or "")
            tomas[idx] = toma_data
        pac_tomas[pac_id] = tomas
        if len(fechas_unicas) > max_tomas:
            max_tomas = len(fechas_unicas)

    # 5. Construir filas del DataFrame
    rows = []
    for pac_id in paciente_ids:
        paciente = pacientes_map.get(pac_id)
        if not paciente:
            continue

        # Calcular IMC
        try:
            peso = float(paciente.peso) if paciente.peso else None
            estatura_m = float(paciente.estatura) / 100 if paciente.estatura else None
            imc = round(peso / (estatura_m ** 2), 2) if peso and estatura_m else None
        except Exception:
            imc = None

        row: dict = {
            "CURP": paciente.identificacion,
            "Nombre": paciente.nombre,
            "Apellido Paterno": paciente.apellido,
            "Apellido Materno": paciente.apellido_materno or "",
            "Sexo": paciente.sexo or "",
            "Fecha Nacimiento": str(paciente.fecha_nacimiento) if paciente.fecha_nacimiento else "",
            "Peso (kg)": float(paciente.peso) if paciente.peso else "",
            "Estatura (cm)": float(paciente.estatura) if paciente.estatura else "",
            "IMC": imc if imc is not None else "",
            "Derechohabiencia": paciente.derechohabiencia or "",
            "Padecimientos": paciente.padecimientos or "",
            "Tipo de Agua": paciente.tipo_agua or "",
            "Cocina con Agua de Llave": paciente.cocina_agua_llave or "",
        }

        # Agregar columnas de cada toma
        tomas = pac_tomas.get(pac_id, {})
        for toma_num in range(1, max_tomas + 1):
            toma_data = tomas.get(toma_num, {})
            row[f"Toma {toma_num} — Fecha"] = str(toma_data.get("fecha", "")) if toma_data.get("fecha") else ""
            for col in prueba_cols:
                row[f"Toma {toma_num} — {col}"] = toma_data.get(col, "")

        rows.append(row)

    # 6. Crear DataFrame y generar Excel
    df = pd.DataFrame(rows)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Reporte")
        # Ajustar ancho de columnas automáticamente
        ws = writer.sheets["Reporte"]
        for col_cells in ws.columns:
            max_len = max(
                (len(str(cell.value)) if cell.value is not None else 0)
                for cell in col_cells
            )
            ws.column_dimensions[col_cells[0].column_letter].width = min(max_len + 4, 50)

    output.seek(0)
    filename = _build_filename(fecha_inicio, fecha_fin)
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _build_filename(fecha_inicio: Optional[date], fecha_fin: Optional[date]) -> str:
    """Construye el nombre del archivo Excel con el rango de fechas."""
    if fecha_inicio and fecha_fin:
        return f"Reporte_{fecha_inicio}_{fecha_fin}.xlsx"
    elif fecha_inicio:
        return f"Reporte_desde_{fecha_inicio}.xlsx"
    elif fecha_fin:
        return f"Reporte_hasta_{fecha_fin}.xlsx"
    return "Reporte_Completo.xlsx"


# ─────────────────────────────────────────────────────────────────────────────

class GenerarReporteRequest(BaseModel):
    paciente_id: int
    resultado_ids: List[int]
    lote_id: Optional[int] = None
    quimico_id: Optional[int] = None

class GenerarMasivoRequest(BaseModel):
    lote_id: int
    quimico_id: Optional[int] = None

class ReporteResponse(BaseModel):
    id: int
    folio: str
    paciente_nombre: str
    paciente_id: int
    fecha_generacion: datetime
    estado: str
    ruta_archivo: str

    class Config:
        from_attributes = True

@router.post("/generar", response_model=ReporteResponse)
async def generar_reporte(
    req: GenerarReporteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Genera un reporte PDF para un paciente con un conjunto específico de resultados.
    """
    try:
        reporte = await generate_report_pdf(
            db=db,
            paciente_id=req.paciente_id,
            resultado_ids=req.resultado_ids,
            generado_por=current_user.id,
            lote_id=req.lote_id,
            quimico_id=req.quimico_id
        )
        
        # Recargar para traer datos del paciente
        stmt = select(ReporteGenerado).where(ReporteGenerado.id == reporte.id).options(selectinload(ReporteGenerado.paciente))
        res = await db.execute(stmt)
        rep_full = res.scalar_one_or_none()
        
        pac_nombre = f"{rep_full.paciente.nombre} {rep_full.paciente.apellido}" if rep_full.paciente else "Desconocido"
        
        return ReporteResponse(
            id=rep_full.id,
            folio=rep_full.folio,
            paciente_nombre=pac_nombre,
            paciente_id=rep_full.paciente_id,
            fecha_generacion=rep_full.fecha_generacion,
            estado=rep_full.estado,
            ruta_archivo=rep_full.ruta_archivo
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(error_details)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generando PDF: {str(e)}. TRACEBACK: {error_details}"
        )

@router.post("/generar-masivo", response_model=List[ReporteResponse])
async def generar_reporte_masivo(
    req: GenerarMasivoRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Genera reportes PDF para todo un lote de resultados agrupado por paciente.
    """
    try:
        reportes = await generate_batch_reports(
            db=db,
            lote_id=req.lote_id,
            generado_por=current_user.id,
            quimico_id=req.quimico_id
        )
        
        response_list = []
        for r in reportes:
            # Traer datos del paciente
            stmt = select(ReporteGenerado).where(ReporteGenerado.id == r.id).options(selectinload(ReporteGenerado.paciente))
            res = await db.execute(stmt)
            rep_full = res.scalar_one_or_none()
            
            pac_nombre = f"{rep_full.paciente.nombre} {rep_full.paciente.apellido}" if rep_full.paciente else "Desconocido"
            
            response_list.append(
                ReporteResponse(
                    id=rep_full.id,
                    folio=rep_full.folio,
                    paciente_nombre=pac_nombre,
                    paciente_id=rep_full.paciente_id,
                    fecha_generacion=rep_full.fecha_generacion,
                    estado=rep_full.estado,
                    ruta_archivo=rep_full.ruta_archivo
                )
            )
        return response_list
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error en generación masiva: {str(e)}"
        )

@router.get("", response_model=List[ReporteResponse])
async def get_reportes(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Lista todos los reportes PDF generados con paginación.
    """
    offset = (page - 1) * limit
    stmt = (
        select(ReporteGenerado)
        .options(selectinload(ReporteGenerado.paciente))
        .order_by(desc(ReporteGenerado.fecha_generacion))
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)
    reportes = result.scalars().all()
    
    response_list = []
    for r in reportes:
        pac_nombre = f"{r.paciente.nombre} {r.paciente.apellido}" if r.paciente else "Desconocido"
        response_list.append(
            ReporteResponse(
                id=r.id,
                folio=r.folio,
                paciente_nombre=pac_nombre,
                paciente_id=r.paciente_id,
                fecha_generacion=r.fecha_generacion,
                estado=r.estado,
                ruta_archivo=r.ruta_archivo
            )
        )
    return response_list

@router.get("/{id}/descargar")
async def descargar_reporte(
    id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Descarga el archivo PDF de un reporte específico.
    """
    stmt = select(ReporteGenerado).where(ReporteGenerado.id == id)
    result = await db.execute(stmt)
    reporte = result.scalar_one_or_none()
    
    if not reporte:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reporte con ID {id} no encontrado"
        )
        
    if not os.path.exists(reporte.ruta_archivo):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El archivo PDF físico no se encuentra en el servidor"
        )
        
    return FileResponse(
        path=reporte.ruta_archivo,
        media_type="application/pdf",
        filename=f"{reporte.folio}.pdf"
    )

class ReporteBusquedaResponse(BaseModel):
    folio: str
    paciente_nombre: str
    pdf_url: str

@router.get("/buscar-por-telefono", response_model=ReporteBusquedaResponse)
async def buscar_por_telefono(
    telefono: str = Query(..., description="Número de teléfono del paciente"),
    db: AsyncSession = Depends(get_db)
):
    """
    Busca el reporte más reciente de un paciente dado su número de teléfono.
    Este endpoint es de uso interno/webhook para automatizaciones (ej. n8n).
    """
    from app.config import get_settings
    settings = get_settings()

    # Limpiar el teléfono para dejar solo los últimos 10 dígitos (local)
    clean_phone = "".join(c for c in telefono if c.isdigit())
    if len(clean_phone) > 10:
        clean_phone = clean_phone[-10:]

    # Buscar al paciente por teléfono (que contenga los últimos 10 dígitos)
    stmt_pac = select(Paciente).where(Paciente.telefono.like(f"%{clean_phone}%"))
    res_pac = await db.execute(stmt_pac)
    paciente = res_pac.scalar_one_or_none()

    if not paciente:
        raise HTTPException(status_code=404, detail="Paciente no encontrado con ese teléfono")

    # Buscar el reporte más reciente del paciente (y que esté autorizado)
    stmt_rep = (
        select(ReporteGenerado)
        .where(ReporteGenerado.paciente_id == paciente.id)
        # .where(ReporteGenerado.authorized_at.isnot(None)) # Opcional: solo reportes autorizados
        .order_by(desc(ReporteGenerado.fecha_generacion))
        .limit(1)
    )
    res_rep = await db.execute(stmt_rep)
    reporte = res_rep.scalar_one_or_none()

    if not reporte:
        raise HTTPException(status_code=404, detail="El paciente no tiene reportes generados")

    pac_nombre = f"{paciente.nombre} {paciente.apellido}"
    pdf_url = f"{settings.BASE_URL}/storage/pdfs/{reporte.folio}.pdf"

    return ReporteBusquedaResponse(
        folio=reporte.folio,
        paciente_nombre=pac_nombre,
        pdf_url=pdf_url
    )
