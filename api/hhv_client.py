import logging
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
import asyncio
from datetime import datetime
from urllib.parse import urlparse

from config.config import Config
from utils.proxy_manager import ProxyManager
from api.base_client import BaseAPIClient
from fake_useragent import UserAgent
from playwright.async_api import async_playwright, Browser


class HHVClient(BaseAPIClient):
    def __init__(self, config: Config, proxy_manager: ProxyManager):
        super().__init__(
            base_url=config.API.HHV_BASE_URL,
            proxy_manager=proxy_manager,
            rate_limit=config.API.RATE_LIMIT,
            timeout=config.API.TIMEOUT,
        )
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        self.user_agent = UserAgent()
        self.browser: Optional[Browser] = None
        self.proxy_manager = proxy_manager

    async def initialize(self):
        """Initialisiert den HHV Client."""
        try:
            playwright = await async_playwright().start()
            self.browser = await playwright.chromium.launch(headless=True)
            self.logger.info("Playwright-Browser erfolgreich gestartet.")
            return True
        except Exception as e:
            self.logger.error(f"Fehler bei der Initialisierung des Browsers: {e}")
            return False

    async def get_products(self) -> List[Dict]:
        """Holt Produkte von allen Kategorien."""
        try:
            all_products = []
            category_url = "/clothing/katalog/filter/schuhe-N10"
            products = await self._scrape_category(category_url)
            all_products.extend(products)
            self.logger.info(f"{len(products)} Produkte aus Kategorie {category_url} gefunden.")
            return all_products
        except Exception as e:
            self.logger.error(f"Fehler beim Abrufen der Produkte: {e}")
            return []
    async def scrape_all_categories(self, categories: List[str]) -> List[Dict]:
        """
        Scrapt alle Kategorien parallel mit mehreren Workern.
        :param categories: Liste von Kategorie-URLs.
        :return: Liste aller gescrapten Produkte.
        """
        try:
            self.logger.info(f"Starte Scraping für {len(categories)} Kategorien mit 20 Workern...")
            all_products = []

            # Semaphore für gleichzeitige Worker
            semaphore = asyncio.Semaphore(20)

            async def scrape_category_worker(category_url: str):
                """Worker-Funktion zum Scrapen einer Kategorie."""
                async with semaphore:
                    self.logger.info(f"Worker startet für Kategorie: {category_url}")
                    products = await self._scrape_category(category_url)
                    if products:
                        all_products.extend(products)
                        self.logger.info(f"{len(products)} Produkte aus Kategorie {category_url} erfolgreich gescrapt.")

            # Starte alle Worker parallel
            tasks = [asyncio.create_task(scrape_category_worker(category)) for category in categories]
            await asyncio.gather(*tasks)
            
            self.logger.info(f"Scraping abgeschlossen. Insgesamt {len(all_products)} Produkte gefunden.")
            return all_products

        except Exception as e:
            self.logger.error(f"Fehler beim parallelen Scraping der Kategorien: {e}")
            return []
    async def _scrape_category(self, category_url: str) -> List[Dict]:
        """
        Scrapt eine Kategorie und extrahiert Produkte.
        :param category_url: Die URL der Kategorie.
        :return: Liste der gescrapten Produkte.
        """
        products = []
        url = f"{self.base_url}{category_url}"

        try:
            html_content = await self._render_page(url)
            if html_content:
                products = await self._parse_products(html_content)

                # Ergänze Produktdetails
                for product in products:
                    detail_url = f"{self.base_url}/clothing/artikel/{product['artikel_id']}"
                    product['url'] = detail_url
                    details = await self._scrape_product_details(detail_url)
                    if details and isinstance(details, dict):
                        product.update(details)
                        product["sku"] = details.get("sku", "N/A")
                        self.logger.info(f"Produkt erfolgreich extrahiert: {product}")
                    else:
                        self.logger.warning(f"Keine Details für Produkt mit Artikel-ID {product['artikel_id']} gefunden.")

            return products

        except Exception as e:
            self.logger.error(f"Fehler beim Scrapen der Kategorie {category_url}: {e}")
            return []

    async def _render_page(self, url: str) -> Optional[str]:
        """
        Rendert eine Seite mit Playwright und gibt den HTML-Inhalt zurück.
        :param url: Die URL der Seite.
        :return: HTML-Inhalt der gerenderten Seite.
        """
        try:
            if not self.browser:
                raise RuntimeError("Browser ist nicht initialisiert.")

            page = await self.browser.new_page()
            await page.set_extra_http_headers({"User-Agent": self.user_agent.random})
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)

            # Warte auf spezifische Selektoren basierend auf der URL
            if "/artikel/" in url:
                await page.wait_for_selector('.items--detail--headline--base-component', timeout=30000)
            else:
                await page.wait_for_selector('turbo-frame[id^="item_gallery_entry_"]', timeout=30000)

            html_content = await page.content()
            await page.close()
            return html_content

        except Exception as e:
            self.logger.error(f"Fehler beim Rendern der Seite {url}: {e}")
            return None
    async def _parse_products(self, html_content: str) -> List[Dict]:
        """
        Parst Produkte aus dem HTML-Inhalt einer Kategorie-Seite.
        :param html_content: HTML-Inhalt der Seite.
        :return: Liste der extrahierten Produkte.
        """
        products = []
        try:
            soup = BeautifulSoup(html_content, 'lxml')
            product_entries = soup.select('turbo-frame[id^="item_gallery_entry_"]')

            for entry in product_entries:
                artikel_id = entry['id'].split('_')[-1].replace('_overlay', '')
                if artikel_id == "overlay":
                    continue

                brand_elem = entry.select_one('.brand')
                title_elem = entry.select_one('.title')
                price_elem = entry.select_one('.price')

                product = {
                    "artikel_id": artikel_id,
                    "brand": brand_elem.text.strip() if brand_elem else "",
                    "model": title_elem.text.strip() if title_elem else "",
                    "price": price_elem.text.strip() if price_elem else "",
                    "url": f"{self.base_url}/clothing/artikel/{artikel_id}"
                }
                products.append(product)

            self.logger.info(f"{len(products)} Produkte erfolgreich aus HTML-Inhalt extrahiert.")
            return products

        except Exception as e:
            self.logger.error(f"Fehler beim Parsen der Produkte: {e}")
            return []

    async def _scrape_product_details(self, detail_url: str) -> Optional[Dict]:
        """
        Scrapt die Detailseite eines Produkts und extrahiert relevante Informationen.
        :param detail_url: URL der Produktdetailseite.
        :return: Ein Dictionary mit den Produktdetails oder None bei Fehlern.
        """
        try:
            html_content = await self._render_page(detail_url)
            if not html_content:
                return None

            soup = BeautifulSoup(html_content, 'lxml')

            # Extrahiere SKU aus der Tabelle
            details_table = soup.select_one('.items--detail--flap--table--base-component table')
            sku = "N/A"
            if details_table:
                for row in details_table.select('tr'):
                    key = row.select_one('.title')
                    value = row.select_one('.value')
                    if key and value and key.text.strip().rstrip(':') == "Katalog-Nr":
                        sku = value.text.strip()
                        break

            # Extrahiere Name und Marke
            name_element = soup.select_one('div.items--detail--headline--base-component h1')
            name_brand = name_element.select_one('a.upper').text.strip() if name_element and name_element.select_one('a.upper') else ""
            name_model = name_element.select_one('span.lower').text.strip() if name_element and name_element.select_one('span.lower') else ""
            full_name = f"{name_brand} {name_model}".strip()

            # Extrahiere Preis mit Fallback-Optionen
            price = "N/A"
            price_meta_tag = soup.select_one('meta[name="twitter:data1"]')
            if price_meta_tag and price_meta_tag.get("content"):
                price = price_meta_tag["content"].strip()
            else:
                price_element = soup.select_one('.price')
                if price_element:
                    price = price_element.text.strip()

            product_details = {
                "name": full_name,
                "brand": name_brand,
                "model": name_model,
                "sku": sku,
                "price": price,
                "detail_url": detail_url,
                "timestamp": datetime.now().isoformat()
            }

            self.logger.info(f"Details für Produkt {sku} erfolgreich extrahiert.")
            return product_details

        except Exception as e:
            self.logger.error(f"Fehler beim Extrahieren der Produktdetails von {detail_url}: {e}")
            return None
    async def cleanup(self):
        """
        Bereinigt alle Ressourcen.
        """
        try:
            if self.browser:
                await self.browser.close()
                self.logger.info("Playwright-Browser erfolgreich geschlossen.")
        except Exception as e:
            self.logger.error(f"Fehler beim Bereinigen der Ressourcen: {e}")

    def __del__(self):
        """
        Destruktor für sauberes Aufräumen.
        """
        try:
            if self.browser:
                asyncio.create_task(self.cleanup())
        except Exception as e:
            self.logger.error(f"Fehler beim Aufräumen im Destruktor: {e}", exc_info=True)
    async def validate_proxies(self):
        """
        Validiert die geladenen Proxies, um sicherzustellen, dass sie funktionieren.
        """
        try:
            valid_proxies = []
            test_url = f"{self.base_url}/clothing/katalog/filter/schuhe-N10"

            async def test_proxy(proxy: str):
                """Testet einen einzelnen Proxy."""
                try:
                    async with self.session.get(test_url, proxy=proxy, timeout=10) as response:
                        if response.status == 200:
                            valid_proxies.append(proxy)
                            self.logger.info(f"Proxy validiert: {proxy}")
                except Exception as e:
                    self.logger.warning(f"Proxy ungültig: {proxy} - Fehler: {e}")

            tasks = [test_proxy(proxy) for proxy in self.proxy_manager.proxies]
            await asyncio.gather(*tasks)

            self.proxy_manager.proxies = valid_proxies
            self.logger.info(f"{len(valid_proxies)} gültige Proxies gefunden.")
        except Exception as e:
            self.logger.error(f"Fehler bei der Proxy-Validierung: {e}")

    async def fetch_product_count(self, category_url: str) -> int:
        """
        Holt die Gesamtanzahl der Produkte in einer Kategorie.
        :param category_url: URL der Kategorie.
        :return: Anzahl der Produkte.
        """
        try:
            html_content = await self._render_page(category_url)
            if not html_content:
                return 0

            soup = BeautifulSoup(html_content, 'lxml')
            count_element = soup.select_one('.pagination--info')
            if count_element:
                match = re.search(r'von (\d+)', count_element.text)
                if match:
                    return int(match.group(1))
            return 0
        except Exception as e:
            self.logger.error(f"Fehler beim Abrufen der Produktanzahl für {category_url}: {e}")
            return 0
