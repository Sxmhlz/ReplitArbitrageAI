from dataclasses import dataclass, field
from typing import List, Optional, Dict
from pathlib import Path
import os
import json


@dataclass
class APIConfig:
    """API-Konfiguration für HTTP Clients."""
    HHV_BASE_URL: str = "https://www.hhv.de"
    HHV_PRODUCT_ENDPOINT: str = "/clothing/katalog/filter/schuhe-N10"

    # Alias API Einstellungen
    ALIAS_ANALYTICS_URL: str = "https://sell-api.goat.com/api/v1/analytics/variants/availability"
    ALIAS_SEARCH_URL: str = "https://2fwotdvm2o-dsn.algolia.net/1/indexes/product_variants_v2"

    # Alias API Headers
    ALIAS_USER_AGENT: str = "alias/1.33.1 (iPhone; iOS 17.5.1; Scale/3.00) Locale/en"
    ALIAS_AUTH_TOKEN: str = "Bearer dpH4GMpJmzgKrMgh1wntLf8Cq3qQsW3o1HiMlzyzVss.6cBDEA1gMmvUgnnikhTycNocfCsd6DcCGtcJYP9zeiY"
    ALIAS_ALGOLIA_API_KEY: str = "838ecd564b6aedc176ff73b67087ff43"
    ALIAS_ALGOLIA_APP_ID: str = "2FWOTDVM2O"

    # API Client Einstellungen
    RATE_LIMIT: int = 10
    TIMEOUT: int = 30
    RETRY_ATTEMPTS: int = 3
    RETRY_DELAY: float = 1.0
    MAX_CONNECTIONS: int = 10
    MAX_PARALLEL_REQUESTS: int = 5


@dataclass
class DatabaseConfig:
    """Datenbank-Konfiguration."""
    DB_URL: str = "sqlite+aiosqlite:///arbitrage.db"
    POOL_SIZE: int = 5
    MAX_OVERFLOW: int = 10
    ECHO: bool = False


@dataclass
class CacheConfig:
    """Cache-Konfiguration."""
    REDIS_URL: str = "redis://localhost:6379"
    DEFAULT_TTL: int = 3600
    MAX_ITEMS: int = 10000


@dataclass
class ScannerConfig:
    """Scanner-Konfiguration."""
    SCAN_INTERVAL: int = 300
    QUEUE_SIZE: int = 1000
    BATCH_SIZE: int = 50

    product_urls: List[str] = field(default_factory=lambda: [
        "https://www.hhv.de/clothing/katalog/filter/schuhe-N10",
    ])


@dataclass
class MonitorConfig:
    """Konfiguration für den Restock-Monitor."""
    RESTOCK_INTERVAL: int = 300  # Intervall für Restock-Checks in Sekunden
    CHECK_INTERVAL: int = 60  # Zeit zwischen einzelnen Produktchecks
    MAX_RETRIES: int = 3  # Maximale Anzahl von Wiederholungen bei Fehlern
    RETRY_DELAY: int = 30  # Verzögerung zwischen Wiederholungen in Sekunden


@dataclass
class ArbitrageConfig:
    """Konfiguration für Arbitrage-Strategien."""
    MIN_PROFIT: float = 10.0  # Mindestgewinn in Euro
    MIN_MONTHLY_SALES: int = 5  # Mindestanzahl monatlicher Verkäufe
    MAX_PRICE: float = 1000.0  # Maximaler Preis eines Produkts


@dataclass
class MLConfig:
    """Konfiguration für Machine Learning."""
    ENABLED: bool = True  # Aktiviert oder deaktiviert ML-Modelle
    MODEL_PATH: str = "models/price_prediction.pkl"  # Pfad zum ML-Modell
    TRAINING_INTERVAL: int = 86400  # Trainingsintervall in Sekunden (1 Tag)
    MIN_SAMPLES: int = 1000  # Minimale Anzahl von Datenpunkten für Training


@dataclass
class NotificationConfig:
    """Konfiguration für Benachrichtigungen."""
    ENABLED: bool = True  # Aktiviert oder deaktiviert Benachrichtigungen
    DISCORD_WEBHOOK: Optional[str] = None  # Discord Webhook URL
    NOTIFICATION_INTERVAL: int = 300  # Intervall für Benachrichtigungen in Sekunden
    MIN_PROFIT_ALERT: float = 20.0  # Mindestgewinn für Alerts


class Config:
    """Hauptkonfigurationsklasse für den ArbitrageBot."""

    def __init__(self):
        self.API = APIConfig()
        self.DB = DatabaseConfig()
        self.CACHE = CacheConfig()
        self.SCANNER = ScannerConfig()
        self.MONITOR = MonitorConfig()
        self.ARBITRAGE = ArbitrageConfig()
        self.ML = MLConfig()
        self.NOTIFICATION = NotificationConfig()

        # Komponenten-Instanzen (optional)
        self.proxy_list: List[str] = self._load_proxies()

        # Konfiguration laden und initialisieren (falls erforderlich)
        self._load_config()

        print("Konfigurationsobjekt erfolgreich initialisiert.")

    def _load_config(self):
        """Lädt Konfiguration aus einer JSON-Datei basierend auf der Umgebung."""
        try:
            env_name = os.getenv('BOT_ENV', 'development')
            config_path = Path(f"config/config_{env_name}.json")

            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                self._update_config(config_data)
                print(f"Konfigurationsdatei {config_path} erfolgreich geladen.")
            else:
                print(f"Keine spezifische Konfigurationsdatei gefunden für Umgebung '{env_name}'.")

        except Exception as e:
            print(f"Fehler beim Laden der Konfigurationsdatei: {e}")

    def _update_config(self, config_data: Dict):
        """Aktualisiert die Konfigurationswerte aus einem Dictionary."""
        for section, values in config_data.items():
            if hasattr(self, section):
                section_obj = getattr(self, section)
                for key, value in values.items():
                    if hasattr(section_obj, key):
                        setattr(section_obj, key, value)

    def _load_proxies(self) -> List[str]:
        """Lädt Proxy-Liste aus einer Datei basierend auf der Umgebung."""
        try:
            proxy_file_path = Path("config/proxies.txt")
            if proxy_file_path.exists():
                with open(proxy_file_path, 'r', encoding='utf-8') as f:
                    return [line.strip() for line in f if line.strip()]
            return []
        except Exception as e:
            print(f"Fehler beim Laden der Proxy-Liste: {e}")
            return []
