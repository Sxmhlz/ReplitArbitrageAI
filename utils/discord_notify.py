from dotenv import load_dotenv
import os
import aiohttp
import logging
from typing import Dict, Optional
import asyncio
from datetime import datetime

class DiscordNotifier:
    def __init__(self, webhook_url: str = None):
        load_dotenv('env.env')
        self.webhook_url = webhook_url or os.getenv('DISCORD_WEBHOOK_URL')
        if not self.webhook_url:
            raise ValueError("DISCORD_WEBHOOK_URL nicht in env.env Datei gefunden")
        self.max_retries = 3
        self.logger = logging.getLogger("DiscordNotifier")
        self.session: Optional[aiohttp.ClientSession] = None

    async def start(self):
        await self.init_session()
        return await self.send_startup_notification()

    async def stop(self):
        if self.session:
            await self.send_shutdown_notification(0, {"products_scanned": 0, "deals_found": 0, "errors": 0})
            await self.close()

    async def init_session(self) -> None:
        if not self.session:
            self.session = aiohttp.ClientSession()

    async def close(self) -> None:
        if self.session:
            await self.session.close()
            self.session = None

    async def send_startup_notification(self) -> bool:
        embed = {
            "title": "🟢 ArbitrageAI Bot Gestartet",
            "description": f"Bot wurde gestartet um {datetime.now().strftime('%H:%M:%S')}",
            "color": 3066993,
            "timestamp": datetime.utcnow().isoformat()
        }
        return await self._send_webhook({"embeds": [embed]})

    async def send_shutdown_notification(self, uptime: float, stats: Dict) -> bool:
        hours = uptime / 3600
        embed = {
            "title": "🔴 ArbitrageAI Bot Heruntergefahren",
            "description": f"Bot wurde nach {hours:.2f} Stunden heruntergefahren",
            "color": 15158332,
            "fields": [{
                "name": "📊 Statistiken",
                "value": (
                    f"• Gescannte Produkte: {stats.get('products_scanned', 0)}\n"
                    f"• Gefundene Deals: {stats.get('deals_found', 0)}\n"
                    f"• Fehler: {stats.get('errors', 0)}"
                )
            }],
            "timestamp": datetime.utcnow().isoformat()
        }
        return await self._send_webhook({"embeds": [embed]})

    async def send_deal_notification(self, product: Dict, profit_data: Dict) -> bool:
        embed = {
            "title": f"💰 Deal Gefunden: {product.get('name', 'Unbekanntes Produkt')}",
            "description": (
                f"**SKU:** {product.get('sku', 'N/A')}\n"
                f"**Brand:** {product.get('brand', 'N/A')}\n"
                f"**Größe:** {product.get('size', 'N/A')}\n"
                f"**HHV Preis:** {product.get('price', 0)}€\n"
                f"**Alias Preis:** {profit_data.get('alias_price', 0)}€\n"
                f"**Profit:** {profit_data.get('net_profit', 0):.2f}€\n"
                f"**ROI:** {profit_data.get('roi', 0):.1f}%"
            ),
            "color": 3447003,
            "timestamp": datetime.utcnow().isoformat(),
            "footer": {
                "text": "ArbitrageAI Bot"
            }
        }
        return await self._send_webhook({"embeds": [embed]})

    async def send_restock_notification(self, restock_data: Dict) -> bool:
        embed = {
            "title": "🔄 Restock Erkannt",
            "description": (
                f"**SKU:** {restock_data.get('sku', 'N/A')}\n"
                f"**Brand:** {restock_data.get('brand', 'N/A')}\n"
                f"**Model:** {restock_data.get('model', 'N/A')}\n"
                f"**Profit Margin:** {restock_data.get('profit_margin', 0):.2f}€\n"
                f"**Confidence:** {restock_data.get('probability', 0)*100:.1f}%"
            ),
            "color": 45015,
            "timestamp": datetime.utcnow().isoformat()
        }
        return await self._send_webhook({"embeds": [embed]})

    async def send_error_notification(self, error_message: str) -> bool:
        embed = {
            "title": "⚠️ Bot-Fehler",
            "description": error_message,
            "color": 15158332,
            "timestamp": datetime.utcnow().isoformat()
        }
        return await self._send_webhook({"embeds": [embed]})

    async def _send_webhook(self, payload: Dict) -> bool:
        await self.init_session()
        for attempt in range(self.max_retries):
            try:
                async with self.session.post(
                    self.webhook_url,
                    json=payload,
                    timeout=10
                ) as response:
                    if response.status == 204:
                        return True
                    self.logger.error(
                        f"Discord API error: {response.status}, "
                        f"Attempt {attempt + 1}/{self.max_retries}"
                    )
                    if response.status != 429:  # Nicht bei Rate-Limiting wiederholen
                        return False
            except asyncio.TimeoutError:
                self.logger.warning(
                    f"Timeout beim Senden der Discord-Nachricht, "
                    f"Versuch {attempt + 1}/{self.max_retries}"
                )
            except Exception as e:
                self.logger.error(f"Fehler beim Senden der Discord-Nachricht: {e}")
                return False
            await asyncio.sleep(2 ** attempt)  # Exponentielles Backoff
        return False
