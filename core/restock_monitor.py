import asyncio
from typing import Dict, List, Optional
import logging
from datetime import datetime, timedelta
import numpy as np
from dataclasses import dataclass

@dataclass
class RestockPrediction:
    sku: str
    probability: float
    next_check: datetime
    priority: int
    last_check: datetime = datetime.now()
    success_rate: float = 0.0
    profit_margin: float = 0.0
    sales_velocity: float = 0.0

class RestockMonitor:
    def __init__(self, ml_model, cache_manager, queue_manager=None, discord_notifier=None, alias_client=None):
        self.ml_model = ml_model
        self.cache_manager = cache_manager
        self.queue_manager = queue_manager
        self.discord_notifier = discord_notifier
        self.alias_client = alias_client
        self.logger = logging.getLogger("RestockMonitor")
        self.monitoring_queue = asyncio.PriorityQueue()
        self.check_interval = 300
        self.active_monitors = set()
        self.last_predictions = {}
        self.prediction_ttl = timedelta(minutes=30)
        self.analyzed_products = 0
        self.profitable_products = 0
    async def monitor_products(self, products: List[Dict]):
        """Hauptmonitoring-Loop für Restocks."""
        total_products = len(products)
        analyzed_products = 0
        profitable_products = 0
        
        while True:
            try:
                for product in products:
                    analyzed_products += 1
                    if product['sku'] not in self.active_monitors:
                        prediction = await self.predict_restock(product)
                        if prediction:
                            if prediction.profit_margin > 15:  # Mindestgewinnmarge
                                profitable_products += 1
                                self.logger.info(
                                    f"Profitables Produkt gefunden!\n"
                                    f"Name: {product.get('name')}\n"
                                    f"SKU: {product.get('sku')}\n"
                                    f"Gewinnmarge: {prediction.profit_margin:.1f}%\n"
                                    f"Restock-Wahrscheinlichkeit: {prediction.probability*100:.1f}%"
                                )
                            await self.monitoring_queue.put(
                                (prediction.priority, prediction)
                            )
                            self.active_monitors.add(product['sku'])
                    
                    if analyzed_products % 10 == 0:
                        self.logger.info(
                            f"Fortschritt: {analyzed_products}/{total_products} Produkte analysiert\n"
                            f"Profitable Produkte gefunden: {profitable_products}"
                        )
                
                await self.process_monitoring_queue()
                await self._cleanup_old_monitors()
                await asyncio.sleep(self.check_interval)
                
            except Exception as e:
                self.logger.error(f"Monitoring error: {e}")
                await asyncio.sleep(60)

    async def monitor_restocks(self) -> List[Dict]:
        try:
            restocks = []
            while not self.monitoring_queue.empty():
                _, prediction = await self.monitoring_queue.get()
                if datetime.now() >= prediction.next_check:
                    restock_found = await self.check_restock(prediction.sku)
                    if restock_found:
                        restock_data = await self._prepare_restock_data(prediction)
                        restocks.append(restock_data)
                        await self._notify_restock(restock_data)
                        await self.handle_restock(prediction.sku)
                    else:
                        new_prediction = await self.update_prediction(prediction)
                        if new_prediction:
                            await self.monitoring_queue.put(
                                (new_prediction.priority, new_prediction)
                            )
            return restocks
        except Exception as e:
            self.logger.error(f"Restock monitoring error: {e}")
            return []
    async def _prepare_restock_data(self, prediction: RestockPrediction) -> Dict:
        """Bereitet Restock-Daten für Benachrichtigungen vor."""
        try:
            market_data = await self.alias_client.get_market_data(prediction.sku) if self.alias_client else {}
            return {
                'sku': prediction.sku,
                'detected_at': datetime.now(),
                'probability': prediction.probability,
                'profit_margin': prediction.profit_margin,
                'sales_velocity': prediction.sales_velocity,
                'market_data': market_data
            }
        except Exception as e:
            self.logger.error(f"Error preparing restock data: {e}")
            return {
                'sku': prediction.sku,
                'detected_at': datetime.now(),
                'probability': prediction.probability
            }

    async def get_cached_prediction(self, sku: str) -> Optional[RestockPrediction]:
        """Holt gecachte Vorhersagen."""
        try:
            if self.cache_manager:
                cached = await self.cache_manager.get(f"prediction_{sku}")
                if cached:
                    return RestockPrediction(**cached)
            return None
        except Exception as e:
            self.logger.error(f"Cache retrieval error: {e}")
            return None

    async def cache_prediction(self, prediction: RestockPrediction) -> None:
        """Cached Vorhersagen für spätere Verwendung."""
        try:
            if self.cache_manager:
                await self.cache_manager.set(
                    f"prediction_{prediction.sku}",
                    {
                        'sku': prediction.sku,
                        'probability': prediction.probability,
                        'next_check': prediction.next_check,
                        'priority': prediction.priority,
                        'profit_margin': prediction.profit_margin,
                        'sales_velocity': prediction.sales_velocity
                    },
                    ttl=int(self.prediction_ttl.total_seconds())
                )
        except Exception as e:
            self.logger.error(f"Cache storage error: {e}")

    def _is_prediction_expired(self, prediction: RestockPrediction) -> bool:
        """Prüft ob eine Vorhersage abgelaufen ist."""
        try:
            return (datetime.now() - prediction.last_check) > self.prediction_ttl
        except Exception as e:
            self.logger.error(f"Prediction expiration check error: {e}")
            return True
    async def handle_restock(self, sku: str) -> None:
        """Behandelt einen gefundenen Restock."""
        try:
            if sku in self.active_monitors:
                self.active_monitors.remove(sku)
                
            if self.discord_notifier:
                restock_data = await self._prepare_restock_data(self.last_predictions[sku])
                await self.discord_notifier.send_restock_notification(restock_data)
                
            await self.cache_manager.delete(f"prediction_{sku}")
            self.last_predictions.pop(sku, None)
            
        except Exception as e:
            self.logger.error(f"Restock handling error: {e}")

    async def process_monitoring_queue(self):
        """Verarbeitet die Monitoring-Queue."""
        try:
            temp_queue = asyncio.PriorityQueue()
            while not self.monitoring_queue.empty():
                priority, prediction = await self.monitoring_queue.get()
                if datetime.now() >= prediction.next_check:
                    restock_found = await self.check_restock(prediction.sku)
                    if restock_found:
                        await self.handle_restock(prediction.sku)
                    else:
                        new_prediction = await self.update_prediction(prediction)
                        if new_prediction:
                            await temp_queue.put((new_prediction.priority, new_prediction))
                else:
                    await temp_queue.put((priority, prediction))
            self.monitoring_queue = temp_queue
        except Exception as e:
            self.logger.error(f"Queue processing error: {e}")

    async def _cleanup_old_monitors(self):
        """Bereinigt alte Monitore."""
        current_time = datetime.now()
        to_remove = set()
        for sku in self.active_monitors:
            last_prediction = self.last_predictions.get(sku)
            if last_prediction and (current_time - last_prediction.last_check) > self.prediction_ttl:
                to_remove.add(sku)
        self.active_monitors -= to_remove
        for sku in to_remove:
            self.last_predictions.pop(sku, None)
            await self.cache_manager.delete(f"prediction_{sku}")
    async def update_prediction(self, prediction: RestockPrediction) -> Optional[RestockPrediction]:
        """Aktualisiert eine bestehende Vorhersage."""
        try:
            features = self.extract_features({
                'sku': prediction.sku,
                'profit_margin': prediction.profit_margin,
                'sales_velocity': prediction.sales_velocity
            })
            
            new_probability = await self.get_restock_probability(features)
            new_priority = self.calculate_priority(
                new_probability,
                prediction.profit_margin,
                prediction.sales_velocity
            )
            
            next_check = self.calculate_next_check(new_probability, new_priority)
            new_prediction = RestockPrediction(
                sku=prediction.sku,
                probability=new_probability,
                next_check=next_check,
                priority=new_priority,
                profit_margin=prediction.profit_margin,
                sales_velocity=prediction.sales_velocity
            )
            
            await self.cache_prediction(new_prediction)
            return new_prediction
            
        except Exception as e:
            self.logger.error(f"Prediction update error: {e}")
            return None

    async def get_cached_prediction(self, sku: str) -> Optional[RestockPrediction]:
        """Holt gecachte Vorhersagen."""
        try:
            if self.cache_manager:
                cached = await self.cache_manager.get(f"prediction_{sku}")
                if cached:
                    return RestockPrediction(**cached)
            return None
        except Exception as e:
            self.logger.error(f"Cache retrieval error: {e}")
            return None

    async def cache_prediction(self, prediction: RestockPrediction) -> None:
        """Cached Vorhersagen für spätere Verwendung."""
        try:
            if self.cache_manager:
                await self.cache_manager.set(
                    f"prediction_{prediction.sku}",
                    {
                        'sku': prediction.sku,
                        'probability': prediction.probability,
                        'next_check': prediction.next_check,
                        'priority': prediction.priority,
                        'profit_margin': prediction.profit_margin,
                        'sales_velocity': prediction.sales_velocity
                    },
                    ttl=int(self.prediction_ttl.total_seconds())
                )
        except Exception as e:
            self.logger.error(f"Cache storage error: {e}")
