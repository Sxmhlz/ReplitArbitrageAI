from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from database.models import Base
import asyncio
import logging

async def init_database():
    logger = logging.getLogger("DatabaseInit")
    
    try:
        # Datenbank-Engine erstellen
        engine = create_async_engine(
            'sqlite+aiosqlite:///arbitrage.db',
            echo=True
        )
        
        # Tabellen erstellen
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
            
        logger.info("Datenbank erfolgreich initialisiert")
        return True
        
    except Exception as e:
        logger.error(f"Fehler bei Datenbank-Initialisierung: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(init_database())
