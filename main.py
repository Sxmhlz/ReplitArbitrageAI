#!/usr/bin/env python3

import sys
import asyncio
import logging
import signal
import subprocess
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

# Füge Projektverzeichnis zum Python-Pfad hinzu
PROJECT_ROOT = Path(__file__).parent
sys.path.append(str(PROJECT_ROOT))

# Core Imports
from core.bot import ArbitrageBot
from core.scanner import Scanner
from core.restock_monitor import RestockMonitor
from core.database import DatabaseManager
from core.price_analyzer import PriceAnalyzer
from config.logging_config import setup_logging
from utils.initialization import setup_environment, check_dependencies
from api.hhv_client import HHVClient
from config.scanner_config import ScannerConfig
from config.config import Config
from utils.proxy_manager import ProxyManager

# DiscordNotifier Import (angepasst für Groß-/Kleinschreibung)
try:
    from utils.discord_notify import DiscordNotifier  # Wenn alles klein geschrieben ist.
except ImportError:
    from utils.Discord_notify import DiscordNotifier  # Wenn Großbuchstaben verwendet werden.

def start_redis_server():
    """Startet den Redis-Server automatisch."""
    try:
        subprocess.run(['redis-cli', 'ping'], capture_output=True, check=True)
        logging.info("Redis-Server läuft bereits")
    except (subprocess.CalledProcessError, FileNotFoundError):
        try:
            subprocess.Popen(['redis-server'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            logging.info("Redis-Server gestartet")
            time.sleep(2)
        except Exception as e:
            logging.error(f"Fehler beim Starten des Redis-Servers: {e}")
            sys.exit(1)

def setup_signal_handlers(bot, scanner, database):
    """Registriert Signal-Handler für sauberes Herunterfahren."""
    loop = asyncio.get_event_loop()

    async def cleanup():
        if scanner:
            await scanner.cleanup()
        if database:
            await database.close()
        if bot:
            await bot.shutdown()

        try:
            subprocess.run(['redis-cli', 'shutdown'], check=True)
            logging.info("Redis-Server gestoppt")
        except Exception as e:
            logging.error(f"Fehler beim Stoppen des Redis-Servers: {e}")

    def signal_handler():
        asyncio.create_task(cleanup())

    for sig in ('SIGINT', 'SIGTERM'):
        try:
            loop.add_signal_handler(getattr(signal, sig), signal_handler)
        except NotImplementedError:
            pass

async def process_products(products: list, price_analyzer: PriceAnalyzer, database: DatabaseManager):
    """Verarbeitet Produkte parallel mit dem PriceAnalyzer."""
    try:
        chunk_size = 50
        chunks = [products[i:i + chunk_size] for i in range(0, len(products), chunk_size)]

        for i, chunk in enumerate(chunks):
            results = await price_analyzer.analyze_batch(chunk)

            for product in results:
                # Speichere Produktdaten in der Datenbank
                await database.save_product(product)

                # Speichere profitable Produkte separat
                if product.get('profit_margin', 0) > 15:
                    await database.save_deal({
                        'sku': product['sku'],
                        'profit_margin': product['profit_margin'],
                        'timestamp': time.time()
                    })

            logging.info(f"Chunk {i + 1}/{len(chunks)} verarbeitet: {len(results)} Produkte analysiert")
            await asyncio.sleep(0.1)

    except Exception as e:
        logging.error(f"Fehler bei der Verarbeitung von Produkten: {e}")

async def main():
    """Hauptfunktion zum Starten des Bots."""
    bot = None
    scanner = None
    database = None

    try:
        # Grundlegende Initialisierung
        start_redis_server()
        setup_environment()
        logger = setup_logging()
        logger.info("Starte ArbitrageAI Bot...")

        if not check_dependencies():
            logger.error("Abhängigkeiten nicht erfüllt. Beende den Bot.")
            sys.exit(1)

        # Bot initialisieren und Konfiguration laden
        config = Config()

        # ScannerConfig erstellen und ProxyManager initialisieren mit Dateipfad statt Config-Objekt
        scanner_config = ScannerConfig(
            batch_size=100,
            max_threads=8,
            retry_attempts=3,
            scan_interval=60,
            timeout=30,
            proxy_enabled=True,
            queue_size=1000
        )
        
        proxy_manager = ProxyManager(proxy_file="config/proxies.txt")  # Nur Dateipfad übergeben

        # Datenbank initialisieren
        database = DatabaseManager()
        await database.init_db()

        # Bot erstellen und initialisieren
        bot = ArbitrageBot()
        if not await bot.initialize():
            logger.error("Bot-Initialisierung fehlgeschlagen")
            sys.exit(1)

        # HHV Client initialisieren mit ProxyManager und Config-Werten (falls notwendig)
        logger.info("Starte HHVClient...")
        hhv_client = HHVClient(base_url=config.API.HHV_BASE_URL, proxy_manager=proxy_manager)
        await hhv_client.initialize()
        
        logger.info("HHV Client erfolgreich initialisiert.")

        # Scanner starten und Produkte verarbeiten
        scanner = Scanner(scanner_config, proxy_manager, bot.queue_manager, hhv_client)
        await scanner.start()

        products = await scanner.scan_products()
        if products:
            price_analyzer = PriceAnalyzer(bot.model, bot.cache, DiscordNotifier(config.NOTIFICATION))
            await process_products(products, price_analyzer, database)

    except Exception as e:
        logger.error(f"Kritischer Fehler in main: {e}")

    finally:
        if scanner:
            await scanner.cleanup()
        if database:
            await database.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot durch Benutzer gestoppt")
    except Exception as e:
        print(f"Fataler Fehler: {e}")
 