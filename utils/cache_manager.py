import redis
from typing import Optional, Any, Dict
import json
import logging
from datetime import timedelta, datetime

class CacheManager:
    def __init__(self, redis_url: str, default_ttl: int = 300):
        self.redis = redis.Redis.from_url(redis_url)
        self.default_ttl = default_ttl
        self.logger = logging.getLogger("CacheManager")
        self.prefix = {
            'product': 'prod_',
            'price': 'price_',
            'prediction': 'pred_',
            'restock': 'restock_'
        }

    async def get(self, key: str, category: str = None) -> Optional[Any]:
        """Holt Daten aus dem Cache."""
        try:
            full_key = f"{self.prefix.get(category, '')}{key}"
            data = self.redis.get(full_key)
            if data:
                cached_data = json.loads(data)
                if self._is_valid_cache(cached_data):
                    return cached_data.get('data')
            return None
        except Exception as e:
            self.logger.error(f"Cache get error for {key}: {e}")
            return None

    async def set(
        self,
        key: str,
        value: Any,
        category: str = None,
        ttl: Optional[int] = None
    ) -> bool:
        """Speichert Daten im Cache."""
        try:
            full_key = f"{self.prefix.get(category, '')}{key}"
            cache_data = {
                'data': value,
                'timestamp': datetime.now().isoformat(),
                'category': category
            }
            return self.redis.setex(
                full_key,
                ttl or self.default_ttl,
                json.dumps(cache_data)
            )
        except Exception as e:
            self.logger.error(f"Cache set error for {key}: {e}")
            return False

    async def delete(self, key: str, category: str = None) -> bool:
        """Löscht einen Cache-Eintrag."""
        try:
            full_key = f"{self.prefix.get(category, '')}{key}"
            return bool(self.redis.delete(full_key))
        except Exception as e:
            self.logger.error(f"Cache delete error for {key}: {e}")
            return False

    async def clear_category(self, category: str) -> bool:
        """Löscht alle Einträge einer Kategorie."""
        try:
            pattern = f"{self.prefix.get(category, '')}*"
            keys = self.redis.keys(pattern)
            if keys:
                return bool(self.redis.delete(*keys))
            return True
        except Exception as e:
            self.logger.error(f"Cache clear error for category {category}: {e}")
            return False

    async def get_many(self, keys: list, category: str = None) -> Dict[str, Any]:
        """Holt mehrere Einträge aus dem Cache."""
        results = {}
        try:
            pipe = self.redis.pipeline()
            full_keys = [f"{self.prefix.get(category, '')}{key}" for key in keys]
            for key in full_keys:
                pipe.get(key)
            values = pipe.execute()
            
            for key, value in zip(keys, values):
                if value:
                    cached_data = json.loads(value)
                    if self._is_valid_cache(cached_data):
                        results[key] = cached_data.get('data')
            return results
        except Exception as e:
            self.logger.error(f"Cache get_many error: {e}")
            return results

    def _is_valid_cache(self, cached_data: Dict) -> bool:
        """Prüft ob Cache-Eintrag noch gültig ist."""
        try:
            if not isinstance(cached_data, dict):
                return False
            timestamp = datetime.fromisoformat(cached_data.get('timestamp', ''))
            age = datetime.now() - timestamp
            return age.total_seconds() < self.default_ttl
        except Exception:
            return False

    async def cleanup(self) -> None:
        """Bereinigt abgelaufene Cache-Einträge."""
        try:
            for category in self.prefix.values():
                pattern = f"{category}*"
                keys = self.redis.keys(pattern)
                for key in keys:
                    data = self.redis.get(key)
                    if data:
                        cached_data = json.loads(data)
                        if not self._is_valid_cache(cached_data):
                            self.redis.delete(key)
            self.logger.info("Cache cleanup completed")
        except Exception as e:
            self.logger.error(f"Cache cleanup error: {e}")
