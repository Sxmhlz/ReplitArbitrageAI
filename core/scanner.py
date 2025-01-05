import asyncio
import logging
from typing import List, Dict, Optional, Set
from datetime import datetime
import aiohttp

from config.scanner_config import ScannerConfig
from utils.proxy_manager import ProxyManager
from utils.queue_manager import QueueManager
from api.hhv_client import HHVClient

class Scanner:
    def __init__(
        self,
        config: ScannerConfig,
        proxy_manager: ProxyManager,
        queue_manager: QueueManager,
        hhv_client: HHVClient
    ):
        self.config = config
        self.proxy_manager = proxy_manager
        self.queue_manager = queue_manager
        self.hhv_client = hhv_client
        self.logger = logging.getLogger("Scanner")
        self.active_tasks: Set[asyncio.Task] = set()
        self.running = False

        # Statistiken und Einstellungen
        self.stats = {
            'products_scanned': 0,
            'successful_scans': 0,
            'failed_scans': 0,
            'last_scan_time': None,
            'scan_duration': None,
            'average_scan_time': 0,
            'total_products_found': 0,
            'total_products_processed': 0
        }
        self.product_urls = self._load_product_urls()
        self.scan_history = []
        self.max_concurrent_scans = 50
        self.semaphore = asyncio.Semaphore(self.max_concurrent_scans)
        self.retry_delay = 1
        self.max_retries = 3

    def _load_product_urls(self) -> List[str]:
        """Lädt Produkt-URLs aus der Konfiguration."""
        try:
            return self.config.product_urls
        except Exception as e:
            self.logger.error(f"Fehler beim Laden der Produkt-URLs: {e}")
            return []

    async def start(self) -> None:
        """Startet den Scanner."""
        self.running = True
        self.logger.info("Scanner gestartet")
        await self.queue_manager.initialize()
        self._start_background_tasks()

    def _start_background_tasks(self):
        """Startet Hintergrundaufgaben für Monitoring."""
        task = asyncio.create_task(self._monitor_scan_performance())
        self.active_tasks.add(task)
        task.add_done_callback(self.active_tasks.discard)

    async def _monitor_scan_performance(self):
        """Überwacht die Scan-Performance."""
        while self.running:
            try:
                await asyncio.sleep(60)
                if self.scan_history:
                    avg_time = sum(h['duration'] for h in self.scan_history) / len(self.scan_history)
                    self.stats['average_scan_time'] = avg_time
                    self.logger.info(f"Durchschnittliche Scan-Zeit: {avg_time:.2f}s")
                    self.logger.info(f"Gefundene Produkte: {self.stats['total_products_found']}")
                    self.logger.info(f"Verarbeitete Produkte: {self.stats['total_products_processed']}")
            except Exception as e:
                self.logger.error(f"Performance-Monitoring Fehler: {e}")
    async def scan_products(self, products: List[Dict] = None) -> List[Dict]:
        """Scannt Produkte."""
        if not self.running:
            await self.start()

        start_time = datetime.now()

        try:
            self.logger.info("Starte Produkt-Scan")

            # Produkte von HHVClient abrufen, wenn keine übergeben wurden
            if products is None:
                products = await self.hhv_client.get_products()

            if not isinstance(products, list):
                raise ValueError("Die zurückgegebenen Produkte sind keine Liste.")

            self.stats['total_products_found'] += len(products)
            self.logger.info(f"Gefundene Produkte: {len(products)}")

            # Verbesserte Produktverarbeitung
            products_to_scan = []
            for product in products:
                try:
                    if isinstance(product, dict):
                        # Extrahiere URL und andere relevante Daten
                        url = product.get('url') or product.get('detail_url')
                        if url:
                            products_to_scan.append({
                                "url": url,
                                "sku": product.get('sku', ''),
                                "price": product.get('price', '0.0'),
                                "name": product.get('name', ''),
                                "brand": product.get('brand', '')
                            })
                    elif isinstance(product, str):
                        products_to_scan.append({"url": product})
                except Exception as e:
                    self.logger.error(f"Fehler bei der Produktverarbeitung: {e}")
                    continue

            if not products_to_scan:
                self.logger.warning("Keine gültigen Produkte zum Scannen gefunden.")
                return []

            # Batch-Verarbeitung
            batch_size = getattr(self.config, 'batch_size', 100)
            batches = [
                products_to_scan[i:i + batch_size]
                for i in range(0, len(products_to_scan), batch_size)
            ]

            all_results = []
            for i, batch in enumerate(batches):
                if not self.running:
                    break

                self.logger.info(f"Verarbeite Batch {i+1}/{len(batches)}")
                async with self.semaphore:
                    batch_results = await self._process_batch(batch)
                    if batch_results:
                        all_results.extend(batch_results)
                        self.logger.info(f"Batch {i+1} verarbeitet: {len(batch_results)} Produkte")

                await asyncio.sleep(1)

            # Scan-Statistiken aktualisieren
            scan_duration = (datetime.now() - start_time).total_seconds()
            self._update_scan_stats(scan_duration, len(all_results))
            self.stats['total_products_processed'] += len(all_results)

            return all_results

        except Exception as e:
            self.logger.error(f"Fehler beim Scannen: {e}")
            self.stats['failed_scans'] += 1
            return []

    async def _process_batch(self, batch: List[Dict]) -> List[Dict]:
        """Verarbeitet einen Batch von Produkten."""
        try:
            tasks = [self._process_product(product) for product in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            processed_products = []
            for result in results:
                if isinstance(result, dict):
                    processed_products.append(result)

            successful = len(processed_products)
            failed = len(batch) - successful

            # Statistiken aktualisieren
            self.stats['successful_scans'] += successful
            self.stats['failed_scans'] += failed

            return processed_products

        except Exception as e:
            self.logger.error(f"Fehler bei Batch-Verarbeitung: {e}")
            return []

    def _update_scan_stats(self, duration: float, success_count: int):
        """Aktualisiert Scan-Statistiken."""
        try:
            self.scan_history.append({
                'timestamp': datetime.now(),
                'duration': duration,
                'success_count': success_count
            })

            if len(self.scan_history) > 100:
                self.scan_history.pop(0)

            self.stats.update({
                'last_scan_time': datetime.now(),
                'scan_duration': duration,
                'products_scanned': self.stats['products_scanned'] + success_count
            })

            self.logger.info(
                f"Scan-Statistiken aktualisiert - "
                f"Dauer: {duration:.2f}s, "
                f"Erfolgreiche Scans: {success_count}"
            )

        except Exception as e:
            self.logger.error(f"Fehler beim Aktualisieren der Scan-Statistiken: {e}")
    async def _process_product(self, product: Dict) -> Optional[Dict]:
        """Verarbeitet ein einzelnes Produkt."""
        if not isinstance(product, dict) or 'url' not in product:
            return None

        retry_count = 0
        while retry_count < self.max_retries:
            try:
                # Proxy abrufen
                proxy = await self.proxy_manager.get_proxy()

                # HTTP-Anfrage mit Proxy
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        product['url'],
                        proxy=proxy['http'] if proxy else None,
                        timeout=getattr(self.config, 'timeout', 30)
                    ) as response:
                        if response.status == 200:
                            try:
                                # JSON-Daten extrahieren
                                product_data = await response.json()
                                return {
                                    **product_data,
                                    'url': product['url'],
                                    'scan_time': datetime.now().isoformat(),
                                    'proxy_used': proxy['http'] if proxy else None
                                }
                            except Exception as e:
                                self.logger.error(f"Fehler beim Verarbeiten der Antwort: {e}")
                                return None
                        elif response.status in [429, 403]:
                            # Retry bei Rate-Limiting oder Forbidden
                            retry_count += 1
                            self.logger.warning(f"Rate-Limit oder Forbidden (Versuch {retry_count}): {response.status}")
                            await asyncio.sleep(self.retry_delay * (2 ** retry_count))
                        else:
                            self.logger.error(f"HTTP-Fehler: {response.status}")
                            return None

            except Exception as e:
                retry_count += 1
                self.logger.error(f"Fehler bei Produktverarbeitung (Versuch {retry_count}): {e}")
                if retry_count < self.max_retries:
                    await asyncio.sleep(self.retry_delay * (2 ** retry_count))

        # Rückgabe von None nach Erreichen der maximalen Versuche
        return None

    async def cleanup(self):
        """Räumt Ressourcen auf."""
        self.running = False
        for task in self.active_tasks:
            task.cancel()
        await asyncio.gather(*self.active_tasks, return_exceptions=True)
        self.logger.info("Scanner erfolgreich gestoppt und Ressourcen bereinigt.")
