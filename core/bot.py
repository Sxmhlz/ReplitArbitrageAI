from datetime import datetime
import logging
import asyncio
from pathlib import Path
from typing import Set

import torch

from config.config import Config
from core.scanner import Scanner
from core.price_analyzer import PriceAnalyzer
from core.restock_monitor import RestockMonitor
from core.database import DatabaseManager
from api.hhv_client import HHVClient
from api.alias_client import AliasClient
from utils.proxy_manager import ProxyManager
from utils.queue_manager import QueueManager
from utils.cache_manager import CacheManager

# DiscordNotifier Import (angepasst für Groß-/Kleinschreibung)
try:
    from utils.discord_notify import DiscordNotifier  # Wenn alles klein geschrieben ist.
except ImportError:
    from utils.Discord_notify import DiscordNotifier  # Wenn Großbuchstaben verwendet werden.


class ArbitrageBot:
    def __init__(self):
        """Initialisiert den ArbitrageBot."""
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info("Initialisiere ArbitrageBot...")

        # Basis-Konfiguration
        self.config = Config()
        self.running = False
        self.tasks: Set[asyncio.Task] = set()
        self.startup_time = datetime.now()
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

        # Komponenten (werden in initialize gesetzt)
        self.db = None
        self.cache = None
        self.proxy_manager = None
        self.queue_manager = None
        self.hhv_client = None
        self.alias_client = None
        self.model = None
        self.dataset_preparator = None
        self.trainer = None
        self.scanner = None
        self.price_analyzer = None
        self.restock_monitor = None
        self.discord = None

        # Statistiken
        self.stats = {
            'products_scanned': 0,
            'deals_found': 0,
            'restocks_detected': 0,
            'errors': 0,
        }

    async def initialize(self) -> bool:
        """Initialisiert alle Bot-Komponenten."""
        try:
            self.logger.info(f"Verwende Device: {self.device}")

            # Datenbank initialisieren
            self.db = DatabaseManager(self.config.DB.DB_URL)
            await self.db.init_db()
            self.logger.info("Datenbank initialisiert")

            # Cache und Manager initialisieren
            redis_url = str(self.config.CACHE.REDIS_URL)
            self.cache = CacheManager(redis_url)

            # ProxyManager mit Dateipfad initialisieren, nicht mit einer Liste!
            proxy_file_path = "config/proxies.txt"
            self.proxy_manager = ProxyManager(proxy_file=proxy_file_path)

            # Queue Manager initialisieren
            self.queue_manager = QueueManager(self.config.SCANNER.QUEUE_SIZE)
            self.logger.info("Manager initialisiert")

            # Discord Notifier initialisieren (mit Fehlerbehandlung)
            try:
                self.discord = DiscordNotifier(self.config.NOTIFICATION)
                self.logger.info("Discord Notifier initialisiert")
            except Exception as e:
                self.logger.warning(f"Discord Notifier konnte nicht initialisiert werden: {e}")
            # API Clients initialisieren
            self.hhv_client = HHVClient(
                base_url=self.config.API.HHV_BASE_URL,
                proxy_manager=self.proxy_manager,
                rate_limit=self.config.API.RATE_LIMIT
            )
            await self.hhv_client.initialize()

            self.alias_client = AliasClient(
                analytics_url=self.config.API.ALIAS_ANALYTICS_URL,
                proxy_manager=self.proxy_manager
            )
            self.logger.info("API Clients initialisiert")

            # Machine Learning-Komponenten initialisieren
            self.model = PricePredictionModel(
                input_size=8,
                hidden_size=128,
                num_layers=2
            ).to(self.device)

            model_path = Path('models/price_prediction.pt')
            if model_path.exists():
                self.model = PricePredictionModel.load_model(str(model_path)).to(self.device)
                self.logger.info("Gespeichertes Modell geladen")

            self.dataset_preparator = DatasetPreparator()
            self.trainer = ModelTrainer(self.model, device=self.device)
            self.logger.info("ML-Komponenten initialisiert")

            # Core-Komponenten initialisieren
            self.scanner = Scanner(
                self.config.SCANNER,
                self.proxy_manager,
                self.queue_manager,
                self.hhv_client
            )

            self.price_analyzer = PriceAnalyzer(
                self.model,
                self.cache,
                self.discord,
                self.alias_client
            )

            self.restock_monitor = RestockMonitor(
                self.model,
                self.cache,
                self.queue_manager,
                self.discord,
                self.alias_client
            )

            # Logging für erfolgreiche Initialisierung
            self.logger.info("Core-Komponenten initialisiert")
            self.logger.info("ArbitrageBot erfolgreich initialisiert")
            return True

        except Exception as e:
            # Fehlerbehandlung und Logging
            self.logger.error(f"Fehler bei der Initialisierung: {e}", exc_info=True)
            return False

    async def start(self):
        """Startet den Bot und alle Monitoring-Tasks."""
        try:
            # Setze den Bot auf "running"
            self.running = True
            self.logger.info("Starte ArbitrageBot...")

            # Erstelle Hauptaufgaben für verschiedene Prozesse
            scan_task = asyncio.create_task(self.scan_loop(), name="scan_loop")
            restock_task = asyncio.create_task(self.monitor_restocks(), name="restock_monitor")
            queue_task = asyncio.create_task(self.process_queue(), name="queue_processor")
            train_task = asyncio.create_task(self.train_model_loop(), name="model_trainer")

            # Füge Aufgaben zur Task-Liste hinzu und starte sie
            self.tasks.update({scan_task, restock_task, queue_task, train_task})
            await asyncio.gather(*self.tasks, return_exceptions=True)

        except Exception as e:
            # Fehlerbehandlung im Hauptloop
            self.logger.error(f"Fehler im Hauptloop: {e}", exc_info=True)
            await self.shutdown()
    async def shutdown(self):
        """Fährt den Bot sicher herunter."""
        try:
            # Logging für Shutdown-Prozess
            self.logger.info("Initiiere Shutdown...")
            self.running = False

            # Tasks beenden
            if self.tasks:
                for task in self.tasks:
                    if not task.done():
                        task.cancel()
                        self.logger.debug(f"Task beendet: {task.get_name()}")
                await asyncio.gather(*self.tasks, return_exceptions=True)

            # Clients schließen
            if self.hhv_client:
                await self.hhv_client.cleanup()
            if self.alias_client:
                await self.alias_client.cleanup()

            # Modell speichern
            if self.model:
                model_path = 'models/price_prediction_final.pt'
                torch.save(self.model.state_dict(), model_path)
                self.logger.info("Finales Modell gespeichert")

            # Discord-Benachrichtigung senden
            if self.discord:
                uptime = (datetime.now() - self.startup_time).total_seconds()
                await self.discord.send_notification(
                    f"Bot wird heruntergefahren\nUptime: {uptime:.0f}s\n"
                    f"Gescannte Produkte: {self.stats['products_scanned']}\n"
                    f"Gefundene Deals: {self.stats['deals_found']}\n"
                    f"Erkannte Restocks: {self.stats['restocks_detected']}\n"
                    f"Fehler: {self.stats['errors']}"
                )

            self.logger.info("Shutdown erfolgreich abgeschlossen")

        except Exception as e:
            self.logger.error(f"Fehler während Shutdown: {e}", exc_info=True)
            raise

    async def scan_loop(self):
        """Hauptloop für das Produkt-Scanning."""
        while self.running:
            try:
                await asyncio.sleep(1)
            except Exception as e:
                self.logger.error(f"Fehler im Scan-Loop: {e}")
                self.stats['errors'] += 1

    async def monitor_restocks(self):
        """Hauptloop für das Restock-Monitoring."""
        while self.running:
            try:
                await asyncio.sleep(1)
            except Exception as e:
                self.logger.error(f"Fehler im Restock-Monitor: {e}")
                self.stats['errors'] += 1

    async def process_queue(self):
        """Hauptloop für die Queue-Verarbeitung."""
        while self.running:
            try:
                await asyncio.sleep(1)
            except Exception as e:
                self.logger.error(f"Fehler in der Queue-Verarbeitung: {e}")
                self.stats['errors'] += 1

    async def train_model_loop(self):
        """Hauptloop für das Modell-Training."""
        while self.running:
            try:
                await asyncio.sleep(1)
            except Exception as e:
                self.logger.error(f"Fehler im Modell-Training: {e}")
                self.stats['errors'] += 1
