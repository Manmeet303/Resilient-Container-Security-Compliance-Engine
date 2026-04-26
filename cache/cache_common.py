"""
cache/cache_common.py
─────────────────────
Core cache primitives shared across the distributed cache subsystem.

Changes from original
─────────────────────
• LayerScanCache now accepts an optional CacheDB instance.
  - put()        → writes through to the DB automatically.
  - get()        → DB fallback on LRU miss (cold-restart survival).
  - update()     → overwrite a stale result + reset TTL in both layers.
  - invalidate() → removes from LRU *and* DB.
  - warm_from_db() → replays all unexpired DB rows back into the LRU.
• stats() extended with hit/miss counters and DB stats.
"""

import hashlib
import threading
import time
from bisect import bisect_right
from collections import OrderedDict
from typing import Optional


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


# ─────────────────────────────────────────────────────────────────────── #
#  In-memory LRU                                                          #
# ─────────────────────────────────────────────────────────────────────── #

class LRUCache:
    def __init__(self, capacity: int = 1000):
        self.capacity = capacity
        self.lock = threading.Lock()
        self.cache: OrderedDict = OrderedDict()

    def get(self, key: str):
        with self.lock:
            if key not in self.cache:
                return None
            self.cache.move_to_end(key)
            return self.cache[key]

    def put(self, key: str, value) -> Optional[str]:
        """Store value. Returns the evicted key if one was dropped, else None."""
        with self.lock:
            if key in self.cache:
                self.cache.move_to_end(key)
            self.cache[key] = value
            if len(self.cache) > self.capacity:
                evicted_key, _ = self.cache.popitem(last=False)
                return evicted_key
            return None

    def delete(self, key: str):
        with self.lock:
            self.cache.pop(key, None)

    def size(self) -> int:
        with self.lock:
            return len(self.cache)

    def keys(self):
        with self.lock:
            return list(self.cache.keys())


# ─────────────────────────────────────────────────────────────────────── #
#  Layer scan cache (LRU + optional DB write-through)                     #
# ─────────────────────────────────────────────────────────────────────── #

class LayerScanCache:
    """
    Two-level cache:  in-memory LRU (fast) + SQLite (durable).

    Parameters
    ──────────
    capacity    – max entries held in the LRU ring.
    ttl_seconds – entry lifetime; applies to both LRU and DB rows.
    db          – optional CacheDB instance.  Pass None to run in
                  memory-only mode (useful for unit tests).
    """

    def __init__(self, capacity: int = 1000, ttl_seconds: int = 3600, db=None):
        self.lru = LRUCache(capacity=capacity)
        self.ttl_seconds = ttl_seconds
        self.db = db
        self._hits = 0
        self._misses = 0
        self._lru_hits = 0
        self._db_hits = 0

        if self.db:
            self.warm_from_db()

    # ------------------------------------------------------------------ #

    def get(self, layer_hash: str):
        """
        1. Check LRU (fastest path).
        2. On LRU miss, fall back to DB (handles cold-restart scenario).
        3. If found in DB but not LRU, re-hydrate the LRU entry.
        """
        item = self.lru.get(layer_hash)
        if item is not None:
            if time.time() <= item["expires_at"]:
                self._hits += 1
                self._lru_hits += 1
                item["hit_count"] = item.get("hit_count", 0) + 1
                return item["data"]
            # Expired in-memory entry
            self.lru.delete(layer_hash)
            if self.db:
                self.db.delete(layer_hash)

        # DB fallback
        if self.db:
            result = self.db.get(layer_hash)
            if result is not None:
                self._put_lru(layer_hash, result)
                self._hits += 1
                self._db_hits += 1
                return result

        self._misses += 1
        return None

    def put(self, layer_hash: str, scan_result: dict):
        """Store a new entry in LRU (and DB if available)."""
        evicted = self._put_lru(layer_hash, scan_result)
        if self.db:
            self.db.put(layer_hash, scan_result, ttl_seconds=self.ttl_seconds)
            if evicted:
                self.db.delete(evicted)

    def update(self, layer_hash: str, scan_result: dict) -> bool:
        """
        Overwrite an existing entry with a fresh scan result and reset its TTL.
        Returns True if the key existed, False if it was unknown.
        Used when a worker re-scans a layer and gets a fresher report.
        """
        existing = self.lru.get(layer_hash)
        db_existed = False

        if existing is not None:
            self._put_lru(layer_hash, scan_result)

        if self.db:
            db_existed = self.db.update(layer_hash, scan_result, ttl_seconds=self.ttl_seconds)
            if db_existed and existing is None:
                self._put_lru(layer_hash, scan_result)

        return existing is not None or db_existed

    def invalidate(self, layer_hash: str):
        """Explicitly remove an entry from LRU and DB."""
        self.lru.delete(layer_hash)
        if self.db:
            self.db.delete(layer_hash)

    def warm_from_db(self):
        """Replay unexpired DB entries back into the LRU on node startup."""
        if not self.db:
            return
        rows = self.db.load_all_valid()
        for row in rows:
            payload = {
                "data": row["scan_result"],
                "created_at": time.time(),
                "expires_at": row["expires_at"],
                "hit_count": row["hit_count"],
            }
            self.lru.put(row["layer_hash"], payload)

    def stats(self) -> dict:
        total = self._hits + self._misses
        base = {
            "entries": self.lru.size(),
            "capacity": self.lru.capacity,
            "ttl_seconds": self.ttl_seconds,
            "total_requests": total,
            "hits": self._hits,
            "misses": self._misses,
            "hit_ratio": round(self._hits / total, 3) if total > 0 else 0.0,
            "lru_hits": self._lru_hits,
            "db_hits": self._db_hits,
        }
        if self.db:
            base.update(self.db.stats())
        return base

    # ------------------------------------------------------------------ #
    #  Private helpers                                                     #
    # ------------------------------------------------------------------ #

    def _put_lru(self, layer_hash: str, scan_result: dict) -> Optional[str]:
        payload = {
            "data": scan_result,
            "created_at": time.time(),
            "expires_at": time.time() + self.ttl_seconds,
            "hit_count": 0,
        }
        return self.lru.put(layer_hash, payload)


# ─────────────────────────────────────────────────────────────────────── #
#  Consistent hash ring (unchanged)                                       #
# ─────────────────────────────────────────────────────────────────────── #

class ConsistentHashRing:
    def __init__(self, nodes=None, virtual_replicas: int = 100):
        self.virtual_replicas = virtual_replicas
        self.ring = {}
        self.sorted_keys = []
        self.nodes: set = set()

        if nodes:
            for node in nodes:
                self.add_node(node)

    def _hash(self, value: str) -> int:
        return int(hashlib.sha256(value.encode("utf-8")).hexdigest(), 16)

    def add_node(self, node: str):
        if node in self.nodes:
            return
        self.nodes.add(node)
        for i in range(self.virtual_replicas):
            h = self._hash(f"{node}#{i}")
            self.ring[h] = node
            self.sorted_keys.append(h)
        self.sorted_keys.sort()

    def remove_node(self, node: str):
        if node not in self.nodes:
            return
        self.nodes.discard(node)
        to_remove = [self._hash(f"{node}#{i}") for i in range(self.virtual_replicas)]
        for k in to_remove:
            self.ring.pop(k, None)
        self.sorted_keys = sorted(self.ring.keys())

    def get_node(self, key: str) -> Optional[str]:
        if not self.ring:
            return None
        h = self._hash(key)
        idx = bisect_right(self.sorted_keys, h)
        if idx == len(self.sorted_keys):
            idx = 0
        return self.ring[self.sorted_keys[idx]]

    def get_ring_view(self) -> dict:
        return {
            "nodes": list(self.nodes),
            "virtual_replicas": self.virtual_replicas,
            "ring_size": len(self.sorted_keys),
        }