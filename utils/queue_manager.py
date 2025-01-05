import asyncio
from typing import Dict, Optional, List
from datetime import datetime, timedelta
import logging

class QueueManager:
    def __init__(self, max_size: int = 1000):
        self.queue = asyncio.PriorityQueue(maxsize=max_size)
        self.processing = set()
        self.logger = logging.getLogger("QueueManager")
        self.batch_size = 50
        self.timeout = timedelta(minutes=5)
        self.running = False

    async def initialize(self):
        """Initialisiert den Queue Manager."""
        try:
            self.running = True
            self.logger.info("Queue Manager initialisiert")
            return True
        except Exception as e:
            self.logger.error(f"Fehler bei Queue Manager Initialisierung: {e}")
            return False

    async def add_item(self, item: Dict, priority: int = 50, retry_count: int = 0) -> bool:
        try:
            if not self._validate_item(item):
                self.logger.warning(f"Ungültiges Item Format: {item}")
                return False

            if item['sku'] not in self.processing:
                queue_item = {
                    'data': item,
                    'added_at': datetime.now(),
                    'retry_count': retry_count,
                    'priority': priority
                }
                await self.queue.put((priority, queue_item))
                return True
            return False
        except Exception as e:
            self.logger.error(f"Fehler beim Hinzufügen des Items: {e}")
            return False

    async def get_item(self) -> Optional[Dict]:
        try:
            if not self.queue.empty():
                priority, item = await self.queue.get()
                if self._is_item_expired(item):
                    return None
                self.processing.add(item['data']['sku'])
                return item
            return None
        except Exception as e:
            self.logger.error(f"Fehler beim Abrufen des Items: {e}")
            return None

    async def get_batch(self, size: int = None) -> List[Dict]:
        batch_size = size or self.batch_size
        items = []
        try:
            for _ in range(batch_size):
                item = await self.get_item()
                if item:
                    items.append(item)
                else:
                    break
            return items
        except Exception as e:
            self.logger.error(f"Fehler beim Batch-Abruf: {e}")
            return items

    async def mark_completed(self, sku: str) -> None:
        try:
            if sku in self.processing:
                self.processing.remove(sku)
        except Exception as e:
            self.logger.error(f"Fehler beim Markieren als abgeschlossen: {e}")

    async def prioritize_product(self, sku: str, new_priority: int = 0) -> None:
        try:
            temp_queue = asyncio.PriorityQueue()
            while not self.queue.empty():
                priority, item = await self.queue.get()
                if item['data']['sku'] == sku:
                    item['priority'] = new_priority
                    await temp_queue.put((new_priority, item))
                else:
                    await temp_queue.put((priority, item))
            self.queue = temp_queue
        except Exception as e:
            self.logger.error(f"Fehler bei Produkt-Priorisierung: {e}")

    def _validate_item(self, item: Dict) -> bool:
        required_fields = ['sku']
        return all(field in item for field in required_fields)

    def _is_item_expired(self, item: Dict) -> bool:
        added_time = item['added_at']
        return datetime.now() - added_time > self.timeout

    async def cleanup(self) -> None:
        try:
            self.running = False
            self.processing.clear()
            temp_queue = asyncio.PriorityQueue()
            while not self.queue.empty():
                priority, item = await self.queue.get()
                if not self._is_item_expired(item):
                    await temp_queue.put((priority, item))
            self.queue = temp_queue
            self.logger.info("Queue erfolgreich bereinigt")
        except Exception as e:
            self.logger.error(f"Fehler beim Queue-Cleanup: {e}")

    async def get_stats(self) -> Dict:
        return {
            'queue_size': self.queue.qsize(),
            'processing_items': len(self.processing),
            'running': self.running
        }
