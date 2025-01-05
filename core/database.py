from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select, update, delete
from typing import AsyncGenerator, List, Dict, Optional
import logging
from datetime import datetime, timedelta
from database.models import Base, Product, Price, Deal, MLData

class DatabaseManager:
    def __init__(self, database_url: str = "sqlite+aiosqlite:///arbitrage.db"):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.engine = create_async_engine(
            database_url,
            echo=False,
            future=True
        )
        
        self.async_session = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        self.logger.info("Database manager initialized")

    async def init_db(self):
        """Initialisiert die Datenbankstruktur."""
        try:
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            self.logger.info("Database tables created successfully")
        except Exception as e:
            self.logger.error(f"Database initialization failed: {e}", exc_info=True)
            raise

    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Erstellt eine neue Datenbankssession."""
        async with self.async_session() as session:
            try:
                yield session
            finally:
                await session.close()

    async def save_product(self, product_data: Dict) -> Optional[Product]:
        """Speichert oder aktualisiert Produktdaten."""
        try:
            async with self.async_session() as session:
                stmt = select(Product).where(Product.sku == product_data['sku'])
                result = await session.execute(stmt)
                product = result.scalar_one_or_none()
                
                if product:
                    for key, value in product_data.items():
                        if hasattr(product, key):
                            setattr(product, key, value)
                else:
                    product = Product(**product_data)
                    session.add(product)
                
                await session.commit()
                await session.refresh(product)
                return product
        except Exception as e:
            self.logger.error(f"Error saving product: {e}")
            await session.rollback()
            return None

    async def save_price(self, sku: str, price_data: Dict) -> Optional[Price]:
        """Speichert einen neuen Preis-Eintrag."""
        try:
            async with self.async_session() as session:
                price = Price(
                    sku=sku,
                    hhv_price=price_data.get('hhv_price'),
                    alias_price=price_data.get('alias_price'),
                    timestamp=datetime.now()
                )
                session.add(price)
                await session.commit()
                await session.refresh(price)
                return price
        except Exception as e:
            self.logger.error(f"Error saving price: {e}")
            await session.rollback()
            return None

    async def save_deal(self, deal_data: Dict) -> Optional[Deal]:
        """Speichert einen profitablen Deal."""
        try:
            async with self.async_session() as session:
                deal = Deal(**deal_data)
                session.add(deal)
                await session.commit()
                await session.refresh(deal)
                return deal
        except Exception as e:
            self.logger.error(f"Error saving deal: {e}")
            await session.rollback()
            return None

    async def get_profitable_products(self, min_profit: float = 15.0, min_sales: int = 5) -> List[Dict]:
        """Holt profitable Produkte für das Restock-Monitoring."""
        try:
            async with self.async_session() as session:
                stmt = select(Product).where(
                    Product.profit_margin >= min_profit,
                    Product.monthly_sales >= min_sales
                )
                result = await session.execute(stmt)
                products = result.scalars().all()
                return [product.__dict__ for product in products]
        except Exception as e:
            self.logger.error(f"Error fetching profitable products: {e}")
            return []

    async def get_training_data(self, limit: int = 1000) -> List[Dict]:
        """Holt Trainingsdaten für das ML-Modell."""
        try:
            async with self.async_session() as session:
                stmt = select(MLData).limit(limit)
                result = await session.execute(stmt)
                data = result.scalars().all()
                return [item.__dict__ for item in data]
        except Exception as e:
            self.logger.error(f"Error fetching training data: {e}")
            return []

    async def update_product(self, sku: str, **kwargs) -> bool:
        """Aktualisiert Produktdaten."""
        try:
            async with self.async_session() as session:
                stmt = update(Product).where(Product.sku == sku).values(**kwargs)
                await session.execute(stmt)
                await session.commit()
                return True
        except Exception as e:
            self.logger.error(f"Error updating product: {e}")
            await session.rollback()
            return False

    async def cleanup_old_data(self, days: int = 30) -> None:
        """Bereinigt alte Datenbankeinträge."""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            async with self.async_session() as session:
                await session.execute(delete(Price).where(Price.timestamp < cutoff_date))
                await session.commit()
                self.logger.info(f"Cleaned up data older than {days} days")
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
            await session.rollback()

    async def close(self):
        """Schließt alle Datenbankverbindungen."""
        try:
            await self.engine.dispose()
            self.logger.info("Database connections closed")
        except Exception as e:
            self.logger.error(f"Error closing database: {e}", exc_info=True)
            raise
