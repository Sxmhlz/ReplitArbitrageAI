from typing import Dict, Optional, List
import logging
import aiohttp
from .base_client import BaseAPIClient

class AliasClient(BaseAPIClient):
    def __init__(self, config, proxy_manager, rate_limit: int = 10, timeout: int = 30):
        """Initialisiert den Alias Client."""
        super().__init__(
            base_url=config.API.ALIAS_ANALYTICS_URL,
            proxy_manager=proxy_manager,
            rate_limit=rate_limit,
            timeout=timeout
        )
        self.config = config
        self.logger = logging.getLogger("AliasClient")
        self.headers = self._get_ios_headers()
        self.session = None

    def _get_ios_headers(self) -> Dict[str, str]:
        """Erstellt iOS-spezifische Headers für Alias-Requests."""
        return {
            "User-Agent": self.config.API.ALIAS_USER_AGENT,
            "Authorization": self.config.API.ALIAS_AUTH_TOKEN,
            "X-Algolia-API-Key": self.config.API.ALIAS_ALGOLIA_API_KEY,
            "X-Algolia-Application-Id": self.config.API.ALIAS_ALGOLIA_APP_ID,
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

    async def initialize(self):
        """Initialisiert den Client und erstellt eine Session."""
        self.session = aiohttp.ClientSession(headers=self.headers)
        self.logger.info("Alias Client initialisiert")
        return True

    async def get_market_data(self, sku: str) -> Optional[Dict]:
        """Holt Marktdaten für ein Produkt von Alias."""
        try:
            url = f"{self.config.API.ALIAS_ANALYTICS_URL}"
            async with self.session.get(url, params={"sku": sku}) as response:
                if response.status == 200:
                    return await response.json()
                self.logger.error(f"Failed to get market data for SKU {sku}: {response.status}")
                return None
        except Exception as e:
            self.logger.error(f"Error fetching market data for SKU {sku}: {e}")
            return None

    async def search_products(self, query: str) -> List[Dict]:
        """Sucht Produkte über Algolia Search."""
        try:
            url = f"{self.config.API.ALIAS_SEARCH_URL}"
            params = {
                "query": query,
                "hitsPerPage": 100
            }
            async with self.session.post(url, json=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("hits", [])
                return []
        except Exception as e:
            self.logger.error(f"Search error: {e}")
            return []

    async def check_availability(self, sku: str) -> bool:
        """Prüft die Verfügbarkeit eines Produkts."""
        try:
            url = f"{self.config.API.ALIAS_ANALYTICS_URL}/availability"
            async with self.session.get(url, params={"sku": sku}) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("available", False)
                return False
        except Exception as e:
            self.logger.error(f"Availability check error for SKU {sku}: {e}")
            return False

    async def cleanup(self):
        """Schließt Alias-spezifische Ressourcen."""
        try:
            if self.session:
                await self.session.close()
            await super().close()
            self.logger.info("Alias Client resources closed")
        except Exception as e:
            self.logger.error(f"Error closing Alias client: {e}")
            raise
