from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_, or_, desc, func
from typing import List, Dict, Optional
import logging
from datetime import datetime, timedelta
from .models import Product, PriceHistory, Deal, RestockData

class DatabaseQueries:
    def __init__(self, session: AsyncSession):
        if not isinstance(session, AsyncSession):
            raise ValueError("Session must be an AsyncSession instance")
        self.session = session
        self.logger = logging.getLogger("DatabaseQueries")

    async def get_profitable_products(
        self,
        min_profit: float,
        min_monthly_sales: int,
        limit: int = 100
    ) -> List[Dict]:
        """Holt profitable Produkte aus der Datenbank."""
        try:
            self.logger.debug(f"Querying profitable products: profit >= {min_profit}, sales >= {min_monthly_sales}")
            query = (
                select(Product)
                .where(
                    and_(
                        Product.profit_margin >= min_profit,
                        Product.monthly_sales >= min_monthly_sales,
                        Product.is_active == True
                    )
                )
                .order_by(desc(Product.profit_margin))
                .limit(limit)
            )
            result = await self.session.execute(query)
            products = result.scalars().all()
            self.logger.info(f"Found {len(products)} profitable products")
            return [{
                'sku': p.sku,
                'name': p.name,
                'hhv_price': p.hhv_price,
                'alias_price': p.alias_price,
                'profit_margin': p.profit_margin,
                'monthly_sales': p.monthly_sales,
                'last_restock': p.last_restock,
                'restock_probability': p.restock_probability
            } for p in products]
        except Exception as e:
            self.logger.error(f"Error querying profitable products: {e}")
            return []

    async def get_price_history(self, sku: str, days: int = 30) -> List[Dict]:
        """Holt Preishistorie eines Produkts."""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            query = (
                select(PriceHistory)
                .where(
                    and_(
                        PriceHistory.sku == sku,
                        PriceHistory.timestamp >= cutoff_date
                    )
                )
                .order_by(PriceHistory.timestamp.desc())
            )
            result = await self.session.execute(query)
            return [{
                'price': h.price,
                'timestamp': h.timestamp,
                'source': h.source
            } for h in result.scalars().all()]
        except Exception as e:
            self.logger.error(f"Error fetching price history for {sku}: {e}")
            return []

    async def get_training_data(self, limit: int = 10000) -> List[Dict]:
        """Holt ML-Trainingsdaten."""
        try:
            self.logger.debug("Fetching training data")
            query = (
                select(Product, PriceHistory)
                .join(PriceHistory)
                .order_by(PriceHistory.timestamp.desc())
                .limit(limit)
            )
            result = await self.session.execute(query)
            return [{
                'sku': row.Product.sku,
                'price': row.PriceHistory.price,
                'timestamp': row.PriceHistory.timestamp,
                'monthly_sales': row.Product.monthly_sales,
                'restock_frequency': row.Product.restock_frequency,
                'profit_margin': row.Product.profit_margin
            } for row in result.all()]
        except Exception as e:
            self.logger.error(f"Error fetching training data: {e}")
            return []

    async def get_recent_deals(self, hours: int = 24) -> List[Dict]:
        """Holt kürzlich gefundene profitable Deals."""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            query = (
                select(Deal)
                .where(Deal.found_at >= cutoff_time)
                .order_by(desc(Deal.profit_margin))
            )
            result = await self.session.execute(query)
            return [{
                'sku': d.sku,
                'profit_margin': d.profit_margin,
                'found_at': d.found_at,
                'status': d.status
            } for d in result.scalars().all()]
        except Exception as e:
            self.logger.error(f"Error fetching recent deals: {e}")
            return []

    async def get_restock_predictions(self, min_probability: float = 0.5) -> List[Dict]:
        """Holt Restock-Vorhersagen."""
        try:
            query = (
                select(RestockData)
                .where(RestockData.probability >= min_probability)
                .order_by(desc(RestockData.probability))
            )
            result = await self.session.execute(query)
            return [{
                'sku': r.sku,
                'probability': r.probability,
                'predicted_date': r.predicted_date,
                'confidence': r.confidence
            } for r in result.scalars().all()]
        except Exception as e:
            self.logger.error(f"Error fetching restock predictions: {e}")
            return []
