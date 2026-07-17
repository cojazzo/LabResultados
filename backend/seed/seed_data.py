"""
Datos semilla para LabResultados.

Crea el usuario admin, químicos de ejemplo, catálogo de pruebas,
pacientes de muestra y lotes de resultados de prueba.

Ejecutar con: python -m backend.seed.seed_data
"""

import asyncio
import sys
import os
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, text


async def get_engine():
    """Crear engine según el entorno (Docker o local)."""
    # Intentar cargar .env
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        from pydantic_settings import BaseSettings
        # Cargar de forma simple
        for line in open(env_path, encoding="utf-8"):
            if line.strip() and not line.startswith("#") and "=" in line:
                key, val = line.strip().split("=", 1)
                os.environ.setdefault(key.strip(), val.strip())
                
    database_url = os.getenv(
        "DATABASE_URL",
        "sqlite+aiosqlite:///./lab_resultados.db",
    )
    return create_async_engine(database_url, echo=False)


# ---------------------------------------------------------------------------
# Datos de catálogo de pruebas
# ---------------------------------------------------------------------------
PRUEBAS_CATALOGO = [
    {
        "codigo": "CRTS",
        "nombre": "Creatinina Sérica",
        "unidad": "mg/dL",
        "valor_min": 0.6,
        "valor_max": 1.2,
        "valor_critico_min": 0.3,
        "valor_critico_max": 4.0,
        "categoria": "Función Renal",
    },
    {
        "codigo": "CRE01",
        "nombre": "Creatinina Urinaria",
        "unidad": "mg/dL",
        "valor_min": 39.0,
        "valor_max": 259.0,
        "valor_critico_min": None,
        "valor_critico_max": None,
        "categoria": "Función Renal",
    },
    {
        "codigo": "ALBOR",
        "nombre": "Albúmina en Orina",
        "unidad": "mg/L",
        "valor_min": 0.0,
        "valor_max": 20.0,
        "valor_critico_min": None,
        "valor_critico_max": None,
        "categoria": "Función Renal",
    },
    {
        "codigo": "ACR",
        "nombre": "Relación Albúmina/Creatinina",
        "unidad": "mg/g",
        "valor_min": 0.0,
        "valor_max": 30.0,
        "valor_critico_min": None,
        "valor_critico_max": None,
        "categoria": "Función Renal",
    },
]

# ---------------------------------------------------------------------------
# Químicos de ejemplo
# ---------------------------------------------------------------------------
QUIMICOS = [
    {
        "cedula": "12345678",
        "nombre_completo": "Q.B. Carlos Alberto López Hernández",
        "activo": True,
    },
    {
        "cedula": "23456789",
        "nombre_completo": "Q.F.B. María Fernanda Gutiérrez Sánchez",
        "activo": True,
    },
    {
        "cedula": "34567890",
        "nombre_completo": "Dr. José Manuel Ramírez Torres",
        "activo": True,
    },
]

# ---------------------------------------------------------------------------
# Pacientes de ejemplo (Aguascalientes)
# ---------------------------------------------------------------------------
PACIENTES = [
    {
        "identificacion": "GARM850315HDFRRL09",
        "nombre": "María Elena",
        "apellido": "García Ramírez",
        "fecha_nacimiento": date(1985, 3, 15),
        "sexo": "F",
        "telefono": "4491234567",
        "email": "maria.garcia@email.com",
        "whatsapp": "4491234567",
        "domicilio": "Av. Gómez Morín 123 Col. Centro",
        "codigo_postal": "20000",
        "estado_residencia": "Aguascalientes",
        "municipio_residencia": "Aguascalientes",
        "peso": 65.2,
        "estatura": 1.62,
        "derechohabiencia": "IMSS",
        "padecimientos": "Ningún padecimiento",
    },
    {
        "identificacion": "LOPC900728HDFPRS05",
        "nombre": "Pedro",
        "apellido": "López Cruz",
        "fecha_nacimiento": date(1990, 7, 28),
        "sexo": "M",
        "telefono": "4492345678",
        "email": "pedro.lopez@email.com",
        "whatsapp": "4492345678",
        "domicilio": "Calle Madero 456 Col. la Estación",
        "codigo_postal": "20180",
        "estado_residencia": "Aguascalientes",
        "municipio_residencia": "Aguascalientes",
        "peso": 80.5,
        "estatura": 1.76,
        "derechohabiencia": "ISSSTE",
        "padecimientos": "Hipertensión(presión alta)",
    },
    {
        "identificacion": "HEMR780512MDFRNR02",
        "nombre": "Rosa María",
        "apellido": "Hernández Moreno",
        "fecha_nacimiento": date(1978, 5, 12),
        "sexo": "F",
        "telefono": "4493456789",
        "email": "rosa.hernandez@email.com",
        "whatsapp": "4493456789",
        "domicilio": "Av. de la Convención 789 Col. Gremial",
        "codigo_postal": "20030",
        "estado_residencia": "Aguascalientes",
        "municipio_residencia": "Aguascalientes",
        "peso": 70.0,
        "estatura": 1.58,
        "derechohabiencia": "Ninguno",
        "padecimientos": "Diabetes",
    },
    {
        "identificacion": "MARS951103HDFRNS08",
        "nombre": "Santiago",
        "apellido": "Martínez Ríos",
        "fecha_nacimiento": date(1995, 11, 3),
        "sexo": "M",
        "telefono": "4494567890",
        "email": "santiago.martinez@email.com",
        "whatsapp": None,
        "domicilio": "Av. Alameda 302 Col. Héroes",
        "codigo_postal": "20190",
        "estado_residencia": "Aguascalientes",
        "municipio_residencia": "Aguascalientes",
        "peso": 75.0,
        "estatura": 1.70,
        "derechohabiencia": "IMSS",
        "padecimientos": "Algún familiar cuenta con enfermedad renal",
    },
    {
        "identificacion": "TOGL880220MDFRRL04",
        "nombre": "Lucía",
        "apellido": "Torres González",
        "fecha_nacimiento": date(1988, 2, 20),
        "sexo": "F",
        "telefono": "4495678901",
        "email": None,
        "whatsapp": "4495678901",
        "domicilio": "Manuel Doblado 15 Col. Centro",
        "codigo_postal": "20000",
        "estado_residencia": "Aguascalientes",
        "municipio_residencia": "Aguascalientes",
        "peso": 58.0,
        "estatura": 1.60,
        "derechohabiencia": "INSABI",
        "padecimientos": "Ningún padecimiento",
    },
]


async def seed_database():
    """Poblar la base de datos con datos de ejemplo."""

    engine = await get_engine()

    try:
        from app.models import Base, User, Prueba, Quimico, Paciente, Lote, Resultado
        from app.core.security import get_password_hash
    except ImportError:
        print("[WARN] Los modelos de la aplicación no están disponibles.")
        print("       Este script requiere que app.models y app.core.security existan.")
        print("       Ejecutando en modo de referencia.\n")
        await _print_seed_summary()
        return

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        async with session.begin():
            # ---------------------------------------------------------------
            # 1. Usuario admin
            # ---------------------------------------------------------------
            existing = await session.execute(
                select(User).where(User.username == "admin")
            )
            if not existing.scalar_one_or_none():
                admin = User(
                    username="admin",
                    email="admin@laboratorio.com",
                    hashed_password=get_password_hash("admin123"),
                    nombre_completo="Administrador del Sistema",
                    is_active=True,
                    is_superuser=True,
                )
                session.add(admin)
                print("[OK] Usuario admin creado")
            else:
                print("[INFO] Usuario admin ya existe")

            # ---------------------------------------------------------------
            # 2. Catálogo de pruebas
            # ---------------------------------------------------------------
            pruebas_creadas = 0
            for p in PRUEBAS_CATALOGO:
                existing = await session.execute(
                    select(Prueba).where(Prueba.codigo == p["codigo"])
                )
                if not existing.scalar_one_or_none():
                    prueba = Prueba(**p)
                    session.add(prueba)
                    pruebas_creadas += 1
            print(f"[OK] {pruebas_creadas} pruebas creadas ({len(PRUEBAS_CATALOGO) - pruebas_creadas} ya existían)")

            # ---------------------------------------------------------------
            # 3. Químicos
            # ---------------------------------------------------------------
            quimicos_creados = 0
            for q in QUIMICOS:
                existing = await session.execute(
                    select(Quimico).where(Quimico.cedula == q["cedula"])
                )
                if not existing.scalar_one_or_none():
                    quimico = Quimico(**q)
                    session.add(quimico)
                    quimicos_creados += 1
            print(f"[OK] {quimicos_creados} químicos creados ({len(QUIMICOS) - quimicos_creados} ya existían)")

            # ---------------------------------------------------------------
            # 4. Pacientes
            # ---------------------------------------------------------------
            pacientes_creados = 0
            for pac in PACIENTES:
                existing = await session.execute(
                    select(Paciente).where(
                        Paciente.identificacion == pac["identificacion"]
                    )
                )
                if not existing.scalar_one_or_none():
                    paciente = Paciente(**pac)
                    session.add(paciente)
                    pacientes_creados += 1
            print(f"[OK] {pacientes_creados} pacientes creados ({len(PACIENTES) - pacientes_creados} ya existían)")

        # Flush para obtener IDs
        await session.commit()

        # ---------------------------------------------------------------
        # 5. Lotes de resultados de ejemplo
        # ---------------------------------------------------------------
        async with session.begin():
            # Obtener IDs de pruebas y pacientes
            pruebas_result = await session.execute(select(Prueba))
            pruebas_db = {p.codigo: p for p in pruebas_result.scalars().all()}

            pacientes_result = await session.execute(select(Paciente))
            pacientes_db = list(pacientes_result.scalars().all())

            # Verificar si ya existen lotes
            lotes_result = await session.execute(select(Lote))
            if lotes_result.scalars().first():
                print("[INFO] Ya existen lotes de resultados, omitiendo creación")
            else:
                import random

                random.seed(42)  # Reproducible

                lotes_info = [
                    {
                        "nombre": "Lote_Renal_20260708",
                        "descripcion": "Perfil Función Renal - 8 de julio 2026",
                        "fecha": datetime(2026, 7, 8, 9, 0, 0),
                        "pruebas": ["CRTS", "CRE01", "ALBOR", "ACR"],
                    },
                    {
                        "nombre": "Lote_Renal_20260709",
                        "descripcion": "Perfil Función Renal - 9 de julio 2026",
                        "fecha": datetime(2026, 7, 9, 10, 30, 0),
                        "pruebas": ["CRTS", "CRE01", "ALBOR", "ACR"],
                    },
                    {
                        "nombre": "Lote_Renal_20260710",
                        "descripcion": "Perfil Función Renal - 10 de julio 2026",
                        "fecha": datetime(2026, 7, 10, 8, 0, 0),
                        "pruebas": ["CRTS", "CRE01", "ALBOR", "ACR"],
                    },
                ]

                for lote_info in lotes_info:
                    lote = Lote(
                        nombre=lote_info["nombre"],
                        descripcion=lote_info["descripcion"],
                        fecha_carga=lote_info["fecha"],
                        estado="completado",
                        total_registros=0,
                        registros_exitosos=0,
                        registros_error=0,
                    )
                    session.add(lote)
                    await session.flush()

                    registros_count = 0
                    # Asignar resultados a pacientes aleatorios
                    pacientes_lote = random.sample(
                        pacientes_db, min(4, len(pacientes_db))
                    )

                    for paciente in pacientes_lote:
                        for codigo_prueba in lote_info["pruebas"]:
                            prueba = pruebas_db.get(codigo_prueba)
                            if not prueba:
                                continue

                            # Generar valor: 70% normal, 15% alto, 10% bajo, 5% crítico
                            val_min = float(prueba.valor_min) if prueba.valor_min is not None else 0.0
                            val_max = float(prueba.valor_max) if prueba.valor_max is not None else 100.0
                            crit_min = float(prueba.valor_critico_min) if prueba.valor_critico_min is not None else None
                            crit_max = float(prueba.valor_critico_max) if prueba.valor_critico_max is not None else None
                            rango = val_max - val_min
                            rand_val = random.random()

                            if rand_val < 0.70:
                                # Normal
                                valor = round(
                                    random.uniform(val_min, val_max),
                                    1,
                                )
                            elif rand_val < 0.85:
                                # Alto
                                valor = round(
                                    val_max + random.uniform(1, max(1.0, rango * 0.3)),
                                    1,
                                )
                            elif rand_val < 0.95:
                                # Bajo
                                valor = round(
                                    max(0.0, val_min - random.uniform(1, max(1.0, rango * 0.3))),
                                    1,
                                )
                            else:
                                # Crítico
                                if crit_max:
                                    valor = round(
                                        crit_max + random.uniform(1, 50),
                                        1,
                                    )
                                elif crit_min:
                                    valor = round(
                                        max(0.0, crit_min - random.uniform(1, 10)),
                                        1,
                                    )
                                else:
                                    valor = round(
                                        val_max + random.uniform(rango * 0.5, max(1.0, rango)),
                                        1,
                                    )

                            # Calcular interpretación
                            if crit_min and valor < crit_min:
                                interpretacion = "critico_bajo"
                            elif crit_max and valor > crit_max:
                                interpretacion = "critico_alto"
                            elif valor < val_min:
                                interpretacion = "bajo"
                            elif valor > val_max:
                                interpretacion = "alto"
                            else:
                                interpretacion = "normal"

                            resultado = Resultado(
                                lote_id=lote.id,
                                paciente_id=paciente.id,
                                prueba_id=prueba.id,
                                valor=valor,
                                interpretacion=interpretacion,
                                fecha_toma=lote_info["fecha"].date(),
                                fecha_resultado=lote_info["fecha"].date(),
                                observaciones=None,
                            )
                            session.add(resultado)
                            registros_count += 1

                    lote.total_registros = registros_count
                    lote.registros_exitosos = registros_count

                print("[OK] 3 lotes de resultados creados con datos de ejemplo")

        await session.commit()

    await engine.dispose()
    print("\n[SUCCESS] Datos semilla cargados exitosamente.")


async def _print_seed_summary():
    """Imprimir resumen de datos cuando los modelos no están disponibles."""
    print("📋 Resumen de datos semilla:")
    print(f"   - 1 usuario admin (admin/admin123)")
    print(f"   - {len(PRUEBAS_CATALOGO)} pruebas de laboratorio")
    print(f"   - {len(QUIMICOS)} químicos")
    print(f"   - {len(PACIENTES)} pacientes")
    print(f"   - 3 lotes de resultados de ejemplo")
    print("\n📝 Catálogo de pruebas:")
    for p in PRUEBAS_CATALOGO:
        criticos = []
        if p["valor_critico_min"]:
            criticos.append(f"crítico bajo: {p['valor_critico_min']}")
        if p["valor_critico_max"]:
            criticos.append(f"crítico alto: {p['valor_critico_max']}")
        critico_str = f" | {', '.join(criticos)}" if criticos else ""
        print(
            f"   {p['codigo']:10s} {p['nombre']:40s} "
            f"{p['valor_min']}-{p['valor_max']} {p['unidad']}{critico_str}"
        )


if __name__ == "__main__":
    asyncio.run(seed_database())
