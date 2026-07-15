from sqlalchemy import Column, Integer, String, Boolean, Date, DateTime, ForeignKey, Numeric, Text, Table, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class User(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    nombre_completo = Column(String, nullable=False)
    rol = Column(String, default="tecnico")  # admin, tecnico, quimico
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Paciente(Base):
    __tablename__ = "pacientes"

    id = Column(Integer, primary_key=True, index=True)
    identificacion = Column(String, unique=True, index=True, nullable=False)
    nombre = Column(String, nullable=False)
    apellido = Column(String, nullable=False)
    apellido_materno = Column(String, nullable=True)
    fecha_nacimiento = Column(Date, nullable=True)
    sexo = Column(String, nullable=True)  # M, F
    telefono = Column(String, nullable=True)
    email = Column(String, nullable=True)
    whatsapp = Column(String, nullable=True)
    domicilio = Column(String, nullable=True)
    codigo_postal = Column(String, nullable=True)
    estado_residencia = Column(String, nullable=True)
    municipio_residencia = Column(String, nullable=True)
    peso = Column(Numeric(precision=10, scale=2), nullable=True)
    estatura = Column(Numeric(precision=10, scale=2), nullable=True)
    derechohabiencia = Column(String, nullable=True)
    suplemento_detalle = Column(String, nullable=True)
    tipo_agua = Column(String, nullable=True)
    cocina_agua_llave = Column(String, nullable=True)
    padecimientos = Column(Text, nullable=True)
    # --- Nuevos campos de automatización ---
    questionnaire_data = Column(Text, nullable=True) # JSON string
    questionnaire_source_id = Column(String, nullable=True)
    email_consent = Column(Boolean, default=False)
    whatsapp_consent = Column(Boolean, default=False)
    result_delivery_consent = Column(Boolean, default=False)
    # ---------------------------------------
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    resultados = relationship("Resultado", back_populates="paciente")
    reportes = relationship("ReporteGenerado", back_populates="paciente")

class Quimico(Base):
    __tablename__ = "quimicos"

    id = Column(Integer, primary_key=True, index=True)
    nombre_completo = Column(String, nullable=False)
    cedula = Column(String, unique=True, index=True, nullable=False)
    activo = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Prueba(Base):
    __tablename__ = "pruebas"

    id = Column(Integer, primary_key=True, index=True)
    codigo = Column(String, unique=True, index=True, nullable=False)
    nombre = Column(String, nullable=False)
    categoria = Column(String, nullable=False)
    unidad = Column(String, nullable=False)
    valor_min = Column(Numeric(precision=10, scale=2), nullable=True)
    valor_max = Column(Numeric(precision=10, scale=2), nullable=True)
    valor_critico_min = Column(Numeric(precision=10, scale=2), nullable=True)
    valor_critico_max = Column(Numeric(precision=10, scale=2), nullable=True)
    metodo = Column(String, nullable=True)
    activa = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    resultados = relationship("Resultado", back_populates="prueba")

class Lote(Base):
    __tablename__ = "lotes_carga"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, nullable=False)  # matches filename
    descripcion = Column(String, nullable=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    fecha_carga = Column(DateTime(timezone=True), server_default=func.now())
    estado = Column(String, default="procesando")  # procesando, completado, error_parcial, error
    total_registros = Column(Integer, default=0)
    registros_exitosos = Column(Integer, default=0)
    registros_error = Column(Integer, default=0)
    log_errores = Column(Text, nullable=True)  # JSON string
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    resultados = relationship("Resultado", back_populates="lote")
    reportes = relationship("ReporteGenerado", back_populates="lote")

class Resultado(Base):
    __tablename__ = "resultados"

    id = Column(Integer, primary_key=True, index=True)
    paciente_id = Column(Integer, ForeignKey("pacientes.id"), nullable=False, index=True)
    prueba_id = Column(Integer, ForeignKey("pruebas.id"), nullable=False, index=True)
    lote_id = Column(Integer, ForeignKey("lotes_carga.id"), nullable=False, index=True)
    valor = Column(Numeric(precision=10, scale=2), nullable=True)
    valor_texto = Column(String, nullable=True)
    interpretacion = Column(String, nullable=True)  # normal, alto, bajo, critico_alto, critico_bajo
    fecha_toma = Column(Date, nullable=False)
    fecha_resultado = Column(Date, nullable=True)
    observaciones = Column(Text, nullable=True)
    
    # --- Nuevos campos de automatización/importación ---
    source_row_number = Column(Integer, nullable=True)
    validation_status = Column(String, default="pending") # pending, valid, error
    authorization_status = Column(String, default="pending") # pending, authorized
    # ---------------------------------------------------
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    paciente = relationship("Paciente", back_populates="resultados")
    prueba = relationship("Prueba", back_populates="resultados")
    lote = relationship("Lote", back_populates="resultados")
    reporte_resultados = relationship("ReporteResultado", back_populates="resultado")

    __table_args__ = (
        Index("idx_resultados_paciente_fecha", "paciente_id", "fecha_toma"),
        Index("idx_resultados_prueba_fecha", "prueba_id", "fecha_toma"),
    )

class ReporteGenerado(Base):
    __tablename__ = "reportes_generados"

    id = Column(Integer, primary_key=True, index=True)
    paciente_id = Column(Integer, ForeignKey("pacientes.id"), nullable=False)
    lote_id = Column(Integer, ForeignKey("lotes_carga.id"), nullable=True)
    folio = Column(String, unique=True, index=True, nullable=False)
    ruta_archivo = Column(String, nullable=False)
    fecha_generacion = Column(DateTime(timezone=True), server_default=func.now())
    generado_por = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    estado = Column(String, default="generado")  # generado, enviado, error
    
    # --- Campos para automatización de envíos ---
    authorized_at = Column(DateTime(timezone=True), nullable=True)
    authorized_by = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    # --------------------------------------------
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    paciente = relationship("Paciente", back_populates="reportes")
    lote = relationship("Lote", back_populates="reportes")
    reporte_resultados = relationship("ReporteResultado", back_populates="reporte")
    envios = relationship("Envio", back_populates="reporte")

class ReporteResultado(Base):
    __tablename__ = "reportes_resultados"

    id = Column(Integer, primary_key=True, index=True)
    reporte_id = Column(Integer, ForeignKey("reportes_generados.id"), nullable=False)
    resultado_id = Column(Integer, ForeignKey("resultados.id"), nullable=False)

    reporte = relationship("ReporteGenerado", back_populates="reporte_resultados")
    resultado = relationship("Resultado", back_populates="reporte_resultados")

class Envio(Base):
    __tablename__ = "envios"

    id = Column(Integer, primary_key=True, index=True)
    reporte_id = Column(Integer, ForeignKey("reportes_generados.id"), nullable=False)
    canal = Column(String, nullable=False)  # email, whatsapp
    destinatario = Column(String, nullable=False)
    estado = Column(String, default="pendiente")  # pendiente, enviado, fallido
    intentos = Column(Integer, default=0)
    error_detalle = Column(Text, nullable=True)
    fecha_envio = Column(DateTime(timezone=True), nullable=True)
    fecha_proximo_reintento = Column(DateTime(timezone=True), nullable=True)
    enviado_por = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    
    # --- Campos para programación (n8n) ---
    scheduled_at = Column(DateTime(timezone=True), nullable=True)
    # --------------------------------------
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    reporte = relationship("ReporteGenerado", back_populates="envios")

    __table_args__ = (
        Index("idx_envios_estado_reintento", "estado", "fecha_proximo_reintento"),
    )

class AutomationEvent(Base):
    __tablename__ = "automation_events"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String, unique=True, index=True, nullable=False) # UUID para idempotencia
    event_type = Column(String, nullable=False, index=True) # ej. patient.questionnaire.submitted
    entity_id = Column(String, nullable=True)
    status = Column(String, default="pending") # pending, processed, error
    attempt_count = Column(Integer, default=0)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    sanitized_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

