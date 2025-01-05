import logging
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
import asyncio
from datetime import datetime
from config.config import Config
from utils.proxy_manager import ProxyManager
from api.base_client import BaseAPIClient
from fake_useragent import UserAgent
from playwright.async_api import async_playwright, Browser


class HHVClient(BaseAPIClient):
    def __init__(self, config: Config, proxy_manager: ProxyManager):
        super().__init__(
            base_url="https://www.hhv.de",
            proxy_manager=proxy_manager,
            rate_limit=config.API.RATE_LIMIT,
            timeout=config.API.TIMEOUT,
        )
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        self.user_agent = UserAgent()
        self.browser: Optional[Browser] = None

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

    async def _scrape_category(self, category_url: str) -> List[Dict]:
        """Scrapt eine Kategorie."""
        products = []
        url = f"{self.base_url}{category_url}"
        try:
            html_content = await self._render_page(url)
            if html_content:
                products = await self._parse_products(html_content)
                for product in products:
                    # Rufe Detailseite auf und extrahiere weitere Informationen
                    detail_url = f"{self.base_url}/clothing/artikel/{product['artikel_id']}"
                    product['url'] = detail_url  # URL zur Detailseite hinzufügen
                    details = await self._scrape_product_details(detail_url)
                    if details:
                        product.update(details)
                        product["sku"] = details.get("sku", "N/A")  # Ersetze Artikelnummer durch Katalognummer (SKU)
                        self.logger.info(f"Produkt erfolgreich extrahiert: {product}")
                    else:
                        self.logger.warning(f"Keine Details für Produkt mit Artikel-ID {product['artikel_id']} gefunden.")
            return products
        except Exception as e:
            self.logger.error(f"Fehler beim Scrapen der Kategorie {category_url}: {e}")
            return []

    async def _render_page(self, url: str) -> Optional[str]:
        """Rendert eine Seite mit Playwright und gibt den HTML-Inhalt zurück."""
        try:
            if not self.browser:
                raise RuntimeError("Browser ist nicht initialisiert.")
            
            page = await self.browser.new_page()
            await page.set_extra_http_headers({"User-Agent": self.user_agent.random})
            
            # Lade die Seite und warte auf Stabilisierung
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            
            # Warten auf ein spezifisches Element zur Stabilisierung (z. B. Produktliste oder Detailseite)
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
        """Parst Produkte aus dem HTML-Inhalt."""
        products = []
        try:
            soup = BeautifulSoup(html_content, 'lxml')
            product_entries = soup.select('turbo-frame[id^="item_gallery_entry_"]')
            
            for entry in product_entries:
                artikel_id = entry['id'].split('_')[-1].replace('_overlay', '')
                if artikel_id == "overlay":
                    continue
                
                product = {
                    "artikel_id": artikel_id,
                    "brand": entry.select_one('.brand').text.strip() if entry.select_one('.brand') else "",
                    "model": entry.select_one('.title').text.strip() if entry.select_one('.title') else "",
                    "price": entry.select_one('.price').text.strip() if entry.select_one('.price') else ""
                }
                products.append(product)
        
        except Exception as e:
            self.logger.error(f"Fehler beim Parsen der Produkte: {e}")
        
        return products

    async def _scrape_product_details(self, detail_url: str) -> Optional[Dict]:
        """Scrapt die Detailseite eines Produkts und extrahiert relevante Informationen."""
        try:
            html_content = await self._render_page(detail_url)
            if not html_content:
                return None
            
            soup = BeautifulSoup(html_content, 'lxml')
            
            # Extrahiere SKU aus der Tabelle (Katalog-Nr.)
            details_table = soup.select_one('.items--detail--flap--table--base-component table')
            
            sku = "N/A"
            
            if details_table:
                for row in details_table.select('tr'):
                    key = row.select_one('.title').text.strip().rstrip(':') if row.select_one('.title') else ""
                    value = row.select_one('.value').text.strip() if row.select_one('.value') else ""
                    if key == "Katalog-Nr":
                        sku = value
            
            # Extrahiere Name und Marke
            name_element = soup.select_one('div.items--detail--headline--base-component h1')
            
            name_brand = name_element.select_one('a.upper').text.strip() if name_element and name_element.select_one('a.upper') else ""
            name_model = name_element.select_one('span.lower').text.strip() if name_element and name_element.select_one('span.lower') else ""
            
            full_name = f"{name_brand} {name_model}".strip()
            
            # Extrahiere Preis (Fallback auf mehrere Selektoren)
            price_meta_tag = soup.select_one('meta[name="twitter:data1"]')
            
            price_table_row = soup.find(lambda tag: tag.name == "td" and tag.text.strip() == "Preis:")
            
            price_meta_value = price_meta_tag["content"].strip() if price_meta_tag else None
            price_table_value = (
                price_table_row.find_next_sibling("td").text.strip()
                if price_table_row and price_table_row.find_next_sibling("td")
                else None
            )
            
            # Priorisiere den Preis aus dem Meta-Tag und fallback auf die Tabelle
            price = price_meta_value or price_table_value or "N/A"
            
            return {
                "name": full_name,
                "brand": name_brand,
                "model": name_model,
                "sku": sku,
                "price": price,
                "detail_url": detail_url,
                "timestamp": datetime.now().isoformat(),
            }
        
        except Exception as e:
            self.logger.error(f"Fehler beim Extrahieren der Produktdetails von {detail_url}: {e}")
            return None

    async def cleanup(self):
        """Bereinigt alle Ressourcen."""
        try:
            if self.browser:
                await self.browser.close()
                self.logger.info("Playwright-Browser erfolgreich geschlossen.")
        except Exception as e:
            self.logger.error(f"Fehler beim Bereinigen der Ressourcen: {e}")
