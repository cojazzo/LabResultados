"""
Datos semilla para LabResultados.

Crea el usuario admin, médicos de ejemplo, catálogo de pruebas,
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
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://lab_user:lab_password_2026@localhost:5432/lab_resultados",
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
# Médicos de ejemplo
# ---------------------------------------------------------------------------
MEDICOS = [
    {
        "cedula": "12345678",
        "nombre": "Dr. Carlos Alberto López Hernández",
        "especialidad": "Medicina General",
    },
    {
        "cedula": "23456789",
        "nombre": "Dra. María Fernanda Gutiérrez Sánchez",
        "especialidad": "Medicina Interna",
    },
    {
        "cedula": "34567890",
        "nombre": "Dr. José Manuel Ramírez Torres",
        "especialidad": "Endocrinología",
    },
    {
        "cedula": "45678901",
        "nombre": "Dra. Ana Lucía Martínez Flores",
        "especialidad": "Cardiología",
    },
    {
        "cedula": "56789012",
        "nombre": "Dr. Roberto Alejandro Díaz Castillo",
        "especialidad": "Nefrología",
    },
]

# ---------------------------------------------------------------------------
# Pacientes de ejemplo
# ---------------------------------------------------------------------------
PACIENTES = [
    {
        "identificacion": "GARM850315HDFRRL09",
        "nombre": "María Elena",
        "apellido": "García Ramírez",
        "fecha_nacimiento": date(1985, 3, 15),
        "sexo": "F",
        "telefono": "+52 55 1234 5678",
        "email": "maria.garcia@email.com",
        "whatsapp": "+52 55 1234 5678",
    },
    {
        "identificacion": "LOPC900728HDFPRS05",
        "nombre": "Pedro",
        "apellido": "López Cruz",
        "fecha_nacimiento": date(1990, 7, 28),
        "sexo": "M",
        "telefono": "+52 55 2345 6789",
        "email": "pedro.lopez@email.com",
        "whatsapp": "+52 55 2345 6789",
    },
    {
        "identificacion": "HEMR780512MDFRNR02",
        "nombre": "Rosa María",
        "apellido": "Hernández Moreno",
        "fecha_nacimiento": date(1978, 5, 12),
        "sexo": "F",
        "telefono": "+52 55 3456 7890",
        "email": "rosa.hernandez@email.com",
        "whatsapp": "+52 55 3456 7890",
    },
    {
        "identificacion": "MARS951103HDFRNS08",
        "nombre": "Santiago",
        "apellido": "Martínez Ríos",
        "fecha_nacimiento": date(1995, 11, 3),
        "sexo": "M",
        "telefono": "+52 55 4567 8901",
        "email": "santiago.martinez@email.com",
        "whatsapp": None,
    },
    {
        "identificacion": "TOGL880220MDFRRL04",
        "nombre": "Lucía",
        "apellido": "Torres González",
        "fecha_nacimiento": date(1988, 2, 20),
        "sexo": "F",
        "telefono": "+52 55 5678 9012",
        "email": None,
        "whatsapp": "+52 55 5678 9012",
    },
    {
        "identificacion": "SAVJ720814HDFLZS07",
        "nombre": "Javier",
        "apellido": "Salazar Vázquez",
        "fecha_nacimiento": date(1972, 8, 14),
        "sexo": "M",
        "telefono": "+52 55 6789 0123",
        "email": "javier.salazar@email.com",
        "whatsapp": "+52 55 6789 0123",
    },
    {
        "identificacion": "ROCA000419MDFSMR01",
        "nombre": "Andrea",
        "apellido": "Rojas Castro",
        "fecha_nacimiento": date(2000, 4, 19),
        "sexo": "F",
        "telefono": "+52 55 7890 1234",
        "email": "andrea.rojas@email.com",
        "whatsapp": "+52 55 7890 1234",
    },
    {
        "identificacion": "NUGF650930HDFRRS06",
        "nombre": "Fernando",
        "apellido": "Núñez Guerrero",
        "fecha_nacimiento": date(1965, 9, 30),
        "sexo": "M",
        "telefono": "+52 55 8901 2345",
        "email": "fernando.nunez@email.com",
        "whatsapp": None,
    },
    {
        "identificacion": "DIME930607MDFRXL03",
        "nombre": "Elena",
        "apellido": "Díaz Mendoza",
        "fecha_nacimiento": date(1993, 6, 7),
        "sexo": "F",
        "telefono": "+52 55 9012 3456",
        "email": "elena.diaz@email.com",
        "whatsapp": "+52 55 9012 3456",
    },
    {
        "identificacion": "FLRM871225HDFLPS09",
        "nombre": "Miguel Ángel",
        "apellido": "Flores Reyes",
        "fecha_nacimiento": date(1987, 12, 25),
        "sexo": "M",
        "telefono": "+52 55 0123 4567",
        "email": "miguel.flores@email.com",
        "whatsapp": "+52 55 0123 4567",
    },
    {
        "identificacion": "CACG010815MDFSTR02",
        "nombre": "Gabriela",
        "apellido": "Castañeda Cisneros",
        "fecha_nacimiento": date(2001, 8, 15),
        "sexo": "F",
        "telefono": "+52 55 1357 2468",
        "email": "gabriela.castaneda@email.com",
        "whatsapp": "+52 55 1357 2468",
    },
    {
        "identificacion": "ORAH760503HDFRRL05",
        "nombre": "Alejandro",
        "apellido": "Ortega Huerta",
        "fecha_nacimiento": date(1976, 5, 3),
        "sexo": "M",
        "telefono": "+52 55 2468 1357",
        "email": None,
        "whatsapp": None,
    },
    {
        "identificacion": "VELI991117MDFRPS08",
        "nombre": "Isabel",
        "apellido": "Velasco Lima",
        "fecha_nacimiento": date(1999, 11, 17),
        "sexo": "F",
        "telefono": "+52 55 3691 4725",
        "email": "isabel.velasco@email.com",
        "whatsapp": "+52 55 3691 4725",
    },
    {
        "identificacion": "RAMR830421HDFRNS04",
        "nombre": "Ricardo",
        "apellido": "Ramos Montes",
        "fecha_nacimiento": date(1983, 4, 21),
        "sexo": "M",
        "telefono": "+52 55 4725 3691",
        "email": "ricardo.ramos@email.com",
        "whatsapp": "+52 55 4725 3691",
    },
    {
        "identificacion": "PESC970209MDFRRL06",
        "nombre": "Carolina",
        "apellido": "Peña Soto",
        "fecha_nacimiento": date(1997, 2, 9),
        "sexo": "F",
        "telefono": "+52 55 5813 9264",
        "email": "carolina.pena@email.com",
        "whatsapp": "+52 55 5813 9264",
    },
]


async def seed_database():
    """Poblar la base de datos con datos de ejemplo."""

    engine = await get_engine()

    # Importar modelos después de configurar el engine
    # Esto asume que los modelos siguen la estructura estándar de la app.
    # Si los modelos aún no existen, este script servirá como referencia.
    try:
        from app.models import Base, User, Prueba, Medico, Paciente, Lote, Resultado
        from app.core.security import get_password_hash
    except ImportError:
        print("⚠️  Los modelos de la aplicación aún no están disponibles.")
        print("   Este script requiere que app.models y app.core.security existan.")
        print("   Ejecutando en modo de referencia: mostrando los datos que se insertarían.\n")
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
                    email="admin@labsanrafael.com",
                    hashed_password=get_password_hash("admin123"),
                    nombre_completo="Administrador del Sistema",
                    is_active=True,
                    is_superuser=True,
                )
                session.add(admin)
                print("✅ Usuario admin creado")
            else:
                print("ℹ️  Usuario admin ya existe")

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
            print(f"✅ {pruebas_creadas} pruebas creadas ({len(PRUEBAS_CATALOGO) - pruebas_creadas} ya existían)")

            # ---------------------------------------------------------------
            # 3. Médicos
            # ---------------------------------------------------------------
            medicos_creados = 0
            for m in MEDICOS:
                existing = await session.execute(
                    select(Medico).where(Medico.cedula == m["cedula"])
                )
                if not existing.scalar_one_or_none():
                    medico = Medico(**m)
                    session.add(medico)
                    medicos_creados += 1
            print(f"✅ {medicos_creados} médicos creados ({len(MEDICOS) - medicos_creados} ya existían)")

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
            print(f"✅ {pacientes_creados} pacientes creados ({len(PACIENTES) - pacientes_creados} ya existían)")

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

            medicos_result = await session.execute(select(Medico))
            medicos_db = list(medicos_result.scalars().all())

            # Verificar si ya existen lotes
            lotes_result = await session.execute(select(Lote))
            if lotes_result.scalars().first():
                print("ℹ️  Ya existen lotes de resultados, omitiendo creación")
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
                        pacientes_db, min(8, len(pacientes_db))
                    )

                    for paciente in pacientes_lote:
                        medico = random.choice(medicos_db)
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
                                medico_id=medico.id,
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

                print(f"✅ 3 lotes de resultados creados con datos de ejemplo")

        await session.commit()

    await engine.dispose()
    print("\n🎉 Datos semilla cargados exitosamente.")


async def _print_seed_summary():
    """Imprimir resumen de datos cuando los modelos no están disponibles."""
    print("📋 Resumen de datos semilla:")
    print(f"   - 1 usuario admin (admin/admin123)")
    print(f"   - {len(PRUEBAS_CATALOGO)} pruebas de laboratorio")
    print(f"   - {len(MEDICOS)} médicos")
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
