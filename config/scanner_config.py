from dataclasses import dataclass, field
import logging
from typing import Dict, List

@dataclass
class ScannerConfig:
    """Konfigurationsklasse für den Scanner."""

    # Standard Scanner Einstellungen
    max_threads: int = 8
    batch_size: int = 100
    retry_attempts: int = 3
    scan_interval: int = 60
    timeout: int = 30
    proxy_enabled: bool = True
    queue_size: int = 1000

    # Standard-Produkt-URLs
    product_urls: List[str] = field(default_factory=lambda: [
        "https://www.hhv.de/clothing/katalog/filter/schuhe-N10"
    ])

    def __post_init__(self):
        """Validiert die Konfigurationswerte nach der Initialisierung."""
        self.logger = logging.getLogger("ScannerConfig")
        self.validate()

    def validate(self) -> None:
        """Validiert die Konfigurationswerte."""
        if self.max_threads <= 0:
            raise ValueError("max_threads muss größer als 0 sein")
        if self.batch_size <= 0:
            raise ValueError("batch_size muss größer als 0 sein")
        if self.retry_attempts < 0:
            raise ValueError("retry_attempts darf nicht negativ sein")
        if self.scan_interval <= 0:
            raise ValueError("scan_interval muss größer als 0 sein")
        if self.timeout <= 0:
            raise ValueError("timeout muss größer als 0 sein")
        if not isinstance(self.product_urls, list):
            raise ValueError("product_urls muss eine Liste sein")
        if self.queue_size <= 0:
            raise ValueError("queue_size muss größer als 0 sein")

        self.logger.info("ScannerConfig validiert")

    def update(self, **kwargs) -> None:
        """Aktualisiert die Konfigurationswerte."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
                self.logger.info(f"Konfigurationswert {key} auf {value} aktualisiert")
            else:
                self.logger.warning(f"Unbekannter Konfigurationsparameter: {key}")
        self.validate()

    def to_dict(self) -> Dict:
        """Gibt die Konfiguration als Dictionary zurück."""
        return {
            "max_threads": self.max_threads,
            "batch_size": self.batch_size,
            "retry_attempts": self.retry_attempts,
            "scan_interval": self.scan_interval,
            "timeout": self.timeout,
            "proxy_enabled": self.proxy_enabled,
            "queue_size": self.queue_size,
            "product_urls": self.product_urls
        }

    def add_product_url(self, url: str) -> None:
        """Fügt eine neue Produkt-URL hinzu."""
        if url not in self.product_urls:
            self.product_urls.append(url)
            self.logger.info(f"Neue Produkt-URL hinzugefügt: {url}")

    def remove_product_url(self, url: str) -> None:
        """Entfernt eine Produkt-URL."""
        if url in self.product_urls:
            self.product_urls.remove(url)
            self.logger.info(f"Produkt-URL entfernt: {url}")

    @property
    def BATCH_SIZE(self) -> int:
        """Getter für batch_size zur Kompatibilität."""
        return self.batch_size

    @BATCH_SIZE.setter
    def BATCH_SIZE(self, value: int) -> None:
        """Setter für batch_size zur Kompatibilität."""
        if value <= 0:
            raise ValueError("batch_size muss größer als 0 sein")
        self.batch_size = value
        self.logger.info(f"batch_size auf {value} gesetzt")

    def log_config(self) -> None:
        """Loggt die aktuelle Konfiguration."""
        self.logger.info("\nAktuelle Scanner-Konfiguration:")
        for key, value in self.to_dict().items():
            self.logger.info(f"{key}: {value}")
