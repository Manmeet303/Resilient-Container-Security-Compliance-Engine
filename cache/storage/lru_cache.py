from collections import OrderedDict
from typing import Optional, Dict, Any
import threading
from shared.utils.logger import get_logger

logger = get_logger("cache.lru_cache")

class LRUCache:
    def __init__(self, max_size=1000):
        self.max_size = max_size
        self._cache: OrderedDict = OrderedDict()
        self._lock = threading.Lock()
        self.hits = 0; self.misses = 0

    def get(self, key):
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                self._cache[key]["hit_count"] = self._cache[key].get("hit_count", 0) + 1
                self.hits += 1
                return self._cache[key]
            self.misses += 1
            return None

    def set(self, key, value):
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = value
            if len(self._cache) > self.max_size:
                evicted, _ = self._cache.popitem(last=False)
                logger.info(f"Evicted: {evicted[:16]}...")

    def hit_ratio(self):
        total = self.hits + self.misses
        return round(self.hits / total, 3) if total > 0 else 0.0

    def size(self):
        return len(self._cache)
