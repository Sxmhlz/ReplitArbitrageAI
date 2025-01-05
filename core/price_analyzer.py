import asyncio
from typing import Dict, List, Optional
import logging
from datetime import datetime, timedelta
import numpy as np
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor

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

class PriceAnalyzer:
    def __init__(self, ml_model, cache_manager=None, discord_notifier=None, alias_client=None):
        self.ml_model = ml_model
        self.cache_manager = cache_manager
        self.discord_notifier = discord_notifier
        self.alias_client = alias_client

        self.logger = logging.getLogger("PriceAnalyzer")
        self.prediction_ttl = timedelta(minutes=30)
        self.min_profit_margin = 15.0  # Mindest-Gewinnmarge in Prozent
        self.analyzed_products = 0
        self.profitable_products = 0

        # Konfiguration für parallele Verarbeitung und Caching
        self.chunk_size = 50
        self.thread_pool = ThreadPoolExecutor(max_workers=20)
        self.semaphore = asyncio.Semaphore(100)
        self.cache_ttl = 300  # Cache-Zeit in Sekunden
        self.price_cache = {}
        self.analysis_queue = asyncio.Queue()
        self.retry_delay = 1
        self.max_retries = 3

        # Aktive Analysen und Zeitstempel der letzten Analyse
        self.active_analyses = set()
        self.last_analysis_time = None

    async def start_analysis_worker(self):
        """Startet einen Hintergrund-Worker für kontinuierliche Analyse."""
        while True:
            try:
                if not self.analysis_queue.empty():
                    product = await self.analysis_queue.get()
                    if not isinstance(product, dict):
                        self.logger.error(f"Ungültiges Produktformat in der Warteschlange: {product}")
                        continue

                    analysis_task = asyncio.create_task(self.analyze_price(product))
                    self.active_analyses.add(analysis_task)
                    analysis_task.add_done_callback(self.active_analyses.discard)

                await asyncio.sleep(0.1)
            except Exception as e:
                self.logger.error(f"Fehler im Analysis-Worker: {e}")
                await asyncio.sleep(1)
import asyncio
from typing import Dict, List, Optional
import logging
from datetime import datetime, timedelta
import numpy as np
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor

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

class PriceAnalyzer:
    def __init__(self, ml_model, cache_manager=None, discord_notifier=None, alias_client=None):
        self.ml_model = ml_model
        self.cache_manager = cache_manager
        self.discord_notifier = discord_notifier
        self.alias_client = alias_client

        self.logger = logging.getLogger("PriceAnalyzer")
        self.prediction_ttl = timedelta(minutes=30)
        self.min_profit_margin = 15.0  # Mindest-Gewinnmarge in Prozent
        self.analyzed_products = 0
        self.profitable_products = 0

        # Konfiguration für parallele Verarbeitung und Caching
        self.chunk_size = 50
        self.thread_pool = ThreadPoolExecutor(max_workers=20)
        self.semaphore = asyncio.Semaphore(100)
        self.cache_ttl = 300  # Cache-Zeit in Sekunden
        self.price_cache = {}
        self.analysis_queue = asyncio.Queue()
        self.retry_delay = 1
        self.max_retries = 3

        # Aktive Analysen und Zeitstempel der letzten Analyse
        self.active_analyses = set()
        self.last_analysis_time = None

    async def start_analysis_worker(self):
        """Startet einen Hintergrund-Worker für kontinuierliche Analyse."""
        while True:
            try:
                if not self.analysis_queue.empty():
                    product = await self.analysis_queue.get()
                    if not isinstance(product, dict):
                        self.logger.error(f"Ungültiges Produktformat in der Warteschlange: {product}")
                        continue

                    analysis_task = asyncio.create_task(self.analyze_price(product))
                    self.active_analyses.add(analysis_task)
                    analysis_task.add_done_callback(self.active_analyses.discard)

                await asyncio.sleep(0.1)
            except Exception as e:
                self.logger.error(f"Fehler im Analysis-Worker: {e}")
                await asyncio.sleep(1)
    async def _get_cached_analysis(self, sku: str) -> Optional[Dict]:
        """Holt die Analyse aus dem Cache, falls verfügbar."""
        try:
            if self.cache_manager:
                cached_data = await self.cache_manager.get(sku)
                if cached_data:
                    return cached_data
            return None
        except Exception as e:
            self.logger.error(f"Fehler beim Abrufen der Cache-Daten für SKU {sku}: {e}")
            return None

    async def _cache_analysis(self, sku: str, analysis: Dict) -> None:
        """Speichert die Analyse im Cache."""
        try:
            if self.cache_manager:
                await self.cache_manager.set(sku, analysis, ttl=self.cache_ttl)
                self.logger.info(f"Analyse für SKU {sku} im Cache gespeichert.")
        except Exception as e:
            self.logger.error(f"Fehler beim Speichern der Analyse im Cache für SKU {sku}: {e}")

    def _extract_features(self, product: Dict) -> List[float]:
        """Extrahiert relevante Features für die Preisanalyse."""
        try:
            return [
                float(product.get('hhv_price', 0)),
                float(product.get('alias_price', 0)),
                float(product.get('sales_velocity', 0)),
                float(product.get('profit_margin', 0))
            ]
        except Exception as e:
            self.logger.error(f"Fehler beim Extrahieren von Features: {e}")
            return []

    def _calculate_margin(self, product: Dict) -> float:
        """Berechnet die Gewinnmarge basierend auf Preisen."""
        try:
            alias_price = float(product.get('alias_price', 0))
            hhv_price = float(product.get('hhv_price', 0))
            if alias_price > 0 and hhv_price > 0:
                return ((alias_price - hhv_price) / hhv_price) * 100
            return 0.0
        except Exception as e:
            self.logger.error(f"Fehler bei der Berechnung der Gewinnmarge: {e}")
            return 0.0

    def _calculate_roi(self, product: Dict) -> float:
        """Berechnet den Return on Investment (ROI)."""
        try:
            alias_price = float(product.get('alias_price', 0))
            hhv_price = float(product.get('hhv_price', 0))
            if alias_price > 0 and hhv_price > 0:
                return ((alias_price - hhv_price) / alias_price) * 100
            return 0.0
        except Exception as e:
            self.logger.error(f"Fehler bei der Berechnung des ROI: {e}")
            return 0.0

    async def cleanup(self):
        """Räumt Ressourcen auf."""
        try:
            # Beende aktive Analysen
            for task in self.active_analyses:
                task.cancel()
            await asyncio.gather(*self.active_analyses, return_exceptions=True)

            # Schließe den Thread-Pool
            self.thread_pool.shutdown(wait=True)

            self.logger.info("PriceAnalyzer erfolgreich gestoppt und Ressourcen bereinigt.")
        except Exception as e:
            self.logger.error(f"Fehler beim Bereinigen von Ressourcen: {e}")
