import logging
import asyncio
import aiohttp
import random
from typing import Optional, List, Dict, Set, Union
from pathlib import Path
from collections import defaultdict

class ProxyManager:
    def __init__(
        self,
        proxy_file: Union[str, Path] = "config/proxies.txt",
        cache_manager=None
    ):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.cache_manager = cache_manager

        # Datei-Konfiguration
        self.proxy_file = Path(proxy_file).resolve()
        self.backup_file = Path("config/proxies_backup.txt").resolve()

        # Proxy-Listen und Status
        self.proxies: List[str] = []
        self.active_proxies: List[str] = []
        self.failed_proxies: Set[str] = set()

        # Performance-Tracking
        self.proxy_scores: Dict[str, float] = defaultdict(lambda: 0.5)
        self.proxy_usage: Dict[str, int] = defaultdict(int)

        # Konfigurationsparameter
        self.config = {
            'validation_interval': 300,
            'min_score': 0.3,
            'timeouts': {'default': 10},
            'retry_delays': 1,
            'max_retries': 3,
        }

        # Test-URL für Proxy-Validierung
        self.test_url = "https://www.google.com"

        # Initialisierung
        self._ensure_config_directory()
        self.load_proxies()

    def _ensure_config_directory(self) -> None:
        """Erstellt das Konfigurationsverzeichnis falls nicht vorhanden."""
        try:
            config_dir = Path("config")
            config_dir.mkdir(exist_ok=True)

            if not self.proxy_file.exists():
                self.proxy_file.touch()
                self.logger.info(f"Proxy-Datei erstellt: {self.proxy_file}")

            if not self.backup_file.exists():
                self.backup_file.touch()
                self.logger.info(f"Backup-Datei erstellt: {self.backup_file}")
        except Exception as e:
            self.logger.error(f"Fehler beim Erstellen des Konfigurationsverzeichnisses: {e}")

    def load_proxies(self) -> None:
        """Lädt Proxies aus der Konfigurationsdatei."""
        try:
            if not self.proxy_file.exists():
                raise FileNotFoundError(f"Proxy-Datei nicht gefunden: {self.proxy_file}")

            with open(self.proxy_file, 'r') as f:
                proxies = [line.strip() for line in f if line.strip()]
                if not proxies:
                    raise ValueError("Keine Proxies in der Datei gefunden.")
                self.proxies = proxies
                self.active_proxies = proxies.copy()
                self.logger.info(f"{len(proxies)} Proxies geladen.")
        except Exception as e:
            self.logger.error(f"Fehler beim Laden der Proxies: {e}")
    async def save_proxies(self) -> None:
        """Speichert die aktuelle Proxy-Liste."""
        try:
            if not self.proxies:
                raise ValueError("Keine Proxies zum Speichern vorhanden.")

            with open(self.proxy_file, 'w') as f:
                for proxy in sorted(set(self.proxies)):
                    f.write(f"{proxy}\n")

            # Erstelle ein Backup der Proxy-Datei
            backup_path = f"{self.backup_file}"
            os.rename(self.proxy_file, backup_path)

            self.logger.info(f"{len(self.proxies)} Proxies gespeichert und Backup erstellt.")
        except Exception as e:
            self.logger.error(f"Fehler beim Speichern der Proxies: {e}")

    async def cleanup(self):
        """Bereinigt Ressourcen beim Herunterfahren."""
        try:
            # Speichere die aktuellen Proxies
            await self.save_proxies()

            # Beende alle Hintergrundaufgaben
            for task in asyncio.all_tasks():
                task.cancel()
            await asyncio.gather(*asyncio.all_tasks(), return_exceptions=True)

            self.logger.info("ProxyManager erfolgreich heruntergefahren.")
        except Exception as e:
            self.logger.error(f"Fehler beim Bereinigen der Ressourcen: {e}")

    async def log_metrics(self):
        """Loggt Proxy-Metriken für Monitoring."""
        try:
            total_proxies = len(self.proxies)
            active_proxies = len(self.active_proxies)
            failed_proxies = len(self.failed_proxies)

            self.logger.info("\n=== Proxy Metriken ===")
            self.logger.info(f"Gesamtanzahl Proxies: {total_proxies}")
            self.logger.info(f"Aktive Proxies: {active_proxies}")
            self.logger.info(f"Fehlgeschlagene Proxies: {failed_proxies}")
            self.logger.info("======================\n")
        except Exception as e:
            self.logger.error(f"Fehler beim Loggen der Proxy-Metriken: {e}")

    async def _reactivate_failed_proxies(self) -> bool:
        """Reaktiviert fehlgeschlagene Proxies nach Validierung."""
        reactivated_any = False
        try:
            for proxy in list(self.failed_proxies):
                if await self.validate_proxy(proxy):
                    reactivated_any = True
                    self.failed_proxies.remove(proxy)
                    if proxy not in self.active_proxies:
                        self.active_proxies.append(proxy)
                        self.logger.info(f"Proxy reaktiviert: {proxy}")
        except Exception as e:
            self.logger.error(f"Fehler beim Reaktivieren der Proxies: {e}")
        
        return reactivated_any

    async def validate_proxy(self, proxy: str) -> bool:
        """Validiert einen Proxy."""
        try:
            timeout = aiohttp.ClientTimeout(total=self.config['timeouts']['default'])

            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(self.test_url, proxy=f"http://{proxy}") as response:
                    if response.status == 200:
                        return True
                    return False
        except Exception as e:
            self.logger.warning(f"Proxy-Validierung fehlgeschlagen ({proxy}): {e}")
            return False

    async def get_proxy(self) -> Optional[Dict[str, str]]:
        """Holt einen validen Proxy."""
        try:
            # Falls keine aktiven Proxies verfügbar sind, versuche fehlgeschlagene zu reaktivieren
            if not self.active_proxies and not await self._reactivate_failed_proxies():
                raise RuntimeError("Keine aktiven Proxies verfügbar.")

            # Wähle einen zufälligen Proxy aus den aktiven Proxies
            proxy = random.choice(self.active_proxies)

            # Validierung des ausgewählten Proxys vor Rückgabe
            if await self.validate_proxy(proxy):
                proxy_url = f"http://{proxy}"
                return {'http': proxy_url, 'https': proxy_url}

            # Entferne ungültige Proxies aus der aktiven Liste und versuche es erneut
            if proxy in self.active_proxies:
                self.active_proxies.remove(proxy)
                await asyncio.sleep(self.config['retry_delays'])
                return await self.get_proxy()
        except Exception as e:
            self.logger.error(f"Fehler beim Abrufen eines Proxys: {e}")
            return None
