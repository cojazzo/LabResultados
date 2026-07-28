import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from app.config import get_settings

async def reset_data():
    settings = get_settings()
    connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
    engine = create_async_engine(settings.DATABASE_URL, connect_args=connect_args)
    
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        print("Iniciando borrado de datos de laboratorio...")
        try:
            # Borrar en orden para respetar las claves foráneas
            await session.execute(text("DELETE FROM reportes_resultados"))
            await session.execute(text("DELETE FROM envios"))
            await session.execute(text("DELETE FROM reportes_generados"))
            await session.execute(text("DELETE FROM resultados"))
            await session.execute(text("DELETE FROM lotes_carga"))
            await session.execute(text("DELETE FROM pacientes"))
            
            await session.commit()
            print("✅ ¡Los datos (pacientes, resultados, reportes y lotes) han sido borrados con éxito!")
            print("ℹ️  (Los usuarios y el catálogo de pruebas se mantuvieron intactos).")
        except Exception as e:
            await session.rollback()
            print(f"❌ Error al borrar datos: {e}")
        finally:
            await session.close()
            
if __name__ == "__main__":
    asyncio.run(reset_data())
