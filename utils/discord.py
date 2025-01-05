class DiscordNotifier:
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
        self.session: Optional[aiohttp.ClientSession] = None

    async def send_deal_alert(self, product: Dict, profit_data: Dict):
        embed = {
            "title": f"Profitable Deal Found: {product['name']}",
            "description": self._format_deal_description(product, profit_data),
            "color": 3066993,
            "fields": [
                {
                    "name": "Profit Breakdown",
                    "value": self._format_profit_breakdown(profit_data)
                },
                {
                    "name": "Market Data",
                    "value": self._format_market_data(product)
                }
            ]
        }
        await self._send_webhook({"embeds": [embed]})