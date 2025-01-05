import asyncio
import logging
from typing import Optional, Set
import torch
from pathlib import Path

class BotTasks:
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger('BotTasks')
        self.running = True
        self.tasks = set()

    async def start_all_tasks(self):
        """Startet alle Bot-Tasks."""
        tasks = [
            self.scan_loop(),
            self.monitor_restocks(),
            self.process_queue(),
            self.train_model_loop()
        ]
        
        self.tasks.update([asyncio.create_task(t) for t in tasks])
        await asyncio.gather(*self.tasks, return_exceptions=True)

    async def scan_loop(self):
        """Hauptloop für das Scannen von Produkten."""
        while self.running:
            try:
                products = await self.bot.hhv_client.get_products()
                if products:
                    await self.bot.scanner.scan_products(products)
                    self.bot.stats['products_scanned'] += len(products)
                    self.logger.info(f"{len(products)} Produkte gescannt")
                await asyncio.sleep(self.bot.config.SCANNER.SCAN_INTERVAL)
            except Exception as e:
                self.logger.error(f"Fehler im Scan-Loop: {e}")
                self.bot.stats['errors'] += 1
                await asyncio.sleep(60)

    async def monitor_restocks(self):
        """Loop für das Restock-Monitoring."""
        while self.running:
            try:
                profitable_products = await self.bot.db.get_profitable_products(
                    self.bot.config.ARBITRAGE.MIN_PROFIT,
                    self.bot.config.ARBITRAGE.MIN_MONTHLY_SALES
                )
                await self.bot.restock_monitor.monitor_products(profitable_products)
                await asyncio.sleep(300)
            except Exception as e:
                self.logger.error(f"Fehler im Restock-Monitor: {e}")
                self.bot.stats['errors'] += 1
                await asyncio.sleep(60)

    async def process_queue(self):
        """Verarbeitet die Queue mit gefundenen Produkten."""
        while self.running:
            try:
                item = await self.bot.queue_manager.get_item()
                if item:
                    product_data = item['data']
                    alias_data = await self.bot.alias_client.get_market_data(product_data['sku'])
                    if alias_data:
                        profit_calc = await self.bot.price_analyzer.analyze_product({
                            **product_data,
                            'alias_price': alias_data['lowest_ask']
                        })
                        if profit_calc and profit_calc.net_profit >= self.bot.config.ARBITRAGE.MIN_PROFIT:
                            await self.bot.db.update_product(
                                product_data['sku'],
                                alias_price=alias_data['lowest_ask'],
                                profit_margin=profit_calc.net_profit,
                                monthly_sales=len(alias_data['sales_history'])
                            )
                            await self.bot.discord.send_deal_alert(
                                product_data,
                                profit_calc.__dict__,
                                alias_data
                            )
                            self.bot.stats['deals_found'] += 1
                        await self.bot.queue_manager.mark_completed(product_data['sku'])
                await asyncio.sleep(0.1)
            except Exception as e:
                self.logger.error(f"Fehler bei Queue-Verarbeitung: {e}")
                self.bot.stats['errors'] += 1
                await asyncio.sleep(1)

    async def train_model_loop(self):
        """Loop für das kontinuierliche Training des ML-Modells."""
        while self.running:
            try:
                historical_data = await self.bot.db.get_training_data()
                if len(historical_data) >= self.bot.config.ML.MIN_TRAINING_SAMPLES:
                    features, targets = self.bot.dataset_preparator.prepare_features(historical_data)
                    features = torch.FloatTensor(features).to(self.bot.device)
                    targets = torch.FloatTensor(targets).to(self.bot.device)
                    await self.bot.trainer.train(features, targets)
                    if self.bot.model.save_model('models/price_prediction.pt'):
                        self.logger.info("Modell erfolgreich gespeichert")
                    self.logger.info("Modell-Training abgeschlossen")
                await asyncio.sleep(3600)
            except Exception as e:
                self.logger.error(f"Fehler im Modell-Training: {e}")
                self.bot.stats['errors'] += 1
                await asyncio.sleep(300)

    async def stop_all_tasks(self):
        """Stoppt alle laufenden Tasks."""
        self.running = False
        for task in self.tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
