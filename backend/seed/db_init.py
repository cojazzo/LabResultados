import asyncio
import sys
from pathlib import Path

# Add root directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import engine
from app.models import Base

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Tablas de la base de datos creadas exitosamente.")

if __name__ == "__main__":
    asyncio.run(init_db())
