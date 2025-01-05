import sys
import importlib
import logging
from pathlib import Path
from typing import Optional
import asyncio
from dotenv import load_dotenv
import os

class BotInitializer:
    def __init__(self):
        self.logger = None
        self.project_root = Path(__file__).parent.parent
        self.required_packages = [
            'aiosqlite',
            'sqlalchemy',
            'aiohttp',
            'torch',
            'pandas',
            'numpy',
            'discord',
            'redis',
            'playwright',
            'fake_useragent'
        ]

    async def initialize(self) -> bool:
        """Hauptinitialisierungsmethode."""
        try:
            if not self.check_dependencies():
                return False
            
            self.setup_environment()
            self.logger = self.setup_logging()
            self.logger.info("Starting bot initialization...")
            
            # Lade Umgebungsvariablen
            load_dotenv(self.project_root / 'env.env')
            
            # Initialisiere Komponenten
            await self.init_database()
            await self.init_cache()
            await self.init_queue()
            await self.init_clients()
            await self.init_ml_components()
            
            self.logger.info("Bot initialization completed successfully")
            return True
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Initialization failed: {e}")
            else:
                print(f"Initialization failed: {e}")
            return False

    def check_dependencies(self) -> bool:
        """Überprüft ob alle erforderlichen Pakete installiert sind."""
        missing_packages = []
        for package in self.required_packages:
            try:
                importlib.import_module(package)
            except ImportError:
                missing_packages.append(package)
        
        if missing_packages:
            error_msg = f"Fehlende Pakete: {', '.join(missing_packages)}"
            if self.logger:
                self.logger.error(error_msg)
            else:
                print(error_msg)
            print("Bitte ausführen: pip install -r requirements.txt")
            return False
        return True

    def setup_environment(self) -> None:
        """Konfiguriert die Projektumgebung."""
        directories = ['data', 'logs', 'models', 'config', 'database', 'ml']
        for directory in directories:
            dir_path = self.project_root / directory
            dir_path.mkdir(parents=True, exist_ok=True)
            init_file = dir_path / '__init__.py'
            init_file.touch(exist_ok=True)

    def setup_logging(self) -> logging.Logger:
        """Konfiguriert das Logging-System."""
        logger = logging.getLogger('ArbitrageBot')
        logger.setLevel(logging.INFO)
        
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # File Handler
        log_path = self.project_root / 'logs' / 'bot.log'
        fh = logging.FileHandler(log_path)
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(formatter)
        
        # Console Handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(formatter)
        
        # Error Handler
        error_log_path = self.project_root / 'logs' / 'error.log'
        eh = logging.FileHandler(error_log_path)
        eh.setLevel(logging.ERROR)
        eh.setFormatter(formatter)
        
        logger.addHandler(fh)
        logger.addHandler(ch)
        logger.addHandler(eh)
        
        return logger

    async def init_database(self) -> None:
        """Initialisiert die Datenbankverbindung."""
        from database.models import Base
        from database.database import DatabaseManager
        
        db_url = os.getenv('DATABASE_URL', 'sqlite+aiosqlite:///arbitrage.db')
        self.db = DatabaseManager(db_url)
        await self.db.init_db()
        self.logger.info("Database initialized")

    async def init_cache(self) -> None:
        """Initialisiert das Cache-System."""
        from utils.cache_manager import CacheManager
        
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
        self.cache = CacheManager(redis_url)
        self.logger.info("Cache system initialized")

    async def init_queue(self) -> None:
        """Initialisiert das Queue-Management."""
        from utils.queue_manager import QueueManager
        
        queue_size = int(os.getenv('QUEUE_SIZE', '1000'))
        self.queue = QueueManager(queue_size)
        self.logger.info("Queue manager initialized")

    async def init_clients(self) -> None:
        """Initialisiert API-Clients."""
        from api.hhv_client import HHVClient
        from api.alias_client import AliasClient
        from utils.proxy_manager import ProxyManager
        from utils.discord_notify import DiscordNotifier
        
        self.proxy_manager = ProxyManager()
        self.hhv_client = HHVClient(self.proxy_manager)
        self.alias_client = AliasClient(self.proxy_manager)
        self.discord = DiscordNotifier()
        
        self.logger.info("API clients initialized")

    async def init_ml_components(self) -> None:
        """Initialisiert ML-Komponenten."""
        from ml.model import PricePredictionModel
        from ml.trainer import ModelTrainer
        
        self.model = PricePredictionModel()
        self.trainer = ModelTrainer(self.model)
        self.logger.info("ML components initialized")

    async def cleanup(self) -> None:
        """Bereinigt Ressourcen bei Shutdown."""
        try:
            await self.db.close()
            await self.cache.cleanup()
            await self.queue.cleanup()
            await self.hhv_client.close()
            await self.alias_client.close()
            self.logger.info("Cleanup completed")
        except Exception as e:
            self.logger.error(f"Cleanup error: {e}")
