"""
cache/cache_common.py
─────────────────────
Two-level distributed cache:
  Level 1  →  In-memory LRU  (microseconds, lost on restart)
  Level 2  →  Redis          (milliseconds, survives restart)

Behaviour
─────────
• On GET  → check LRU first; on miss, fall back to Redis and re-hydrate LRU.
• On PUT  → write to LRU immediately, write-through to Redis with TTL.
• On startup → warm LRU from Redis keys so a node restart is NOT a cold start.
• Graceful fallback → if Redis is down or not installed, runs in memory-only
  mode exactly as before. Nothing breaks.

Redis keys
──────────
  rcsce:cache:<layer_hash>   →  JSON string of the full payload
  TTL set via SETEX so Redis handles expiry automatically.

No other code needs to change. docker_listener.py, dispatcher.py, and
cache_node.py all continue to call GET /cache/{hash} and POST /cache
exactly as before.
"""

import hashlib
import json
import threading
import time
from bisect import bisect_right
from collections import OrderedDict
from typing import Optional

from shared.utils.logger import get_logger

logger = get_logger("cache.cache_common")

REDIS_KEY_PREFIX = "rcsce:cache:"


# ── SHA-256 helper ─────────────────────────────────────────────────────────────

def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


# ── Redis connection factory ───────────────────────────────────────────────────

def _make_redis():
    """
    Try to create a Redis client.
    Returns the client if Redis is reachable, None otherwise.
    Works even if the redis package is not installed.
    """
    try:
        import redis
        client = redis.Redis(
            host="localhost",
            port=6379,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        client.ping()                    # raises if Redis is not running
        logger.info("Cache: connected to Redis at localhost:6379 — entries will survive restarts")
        return client
    except ImportError:
        logger.warning("Cache: redis package not installed — running in memory-only mode")
        return None
    except Exception as exc:
        logger.warning(f"Cache: Redis unavailable ({exc}) — running in memory-only mode")
        return None


# ── In-memory LRU (unchanged from original) ───────────────────────────────────

class LRUCache:
    def __init__(self, capacity: int = 1000):
        self.capacity = capacity
        self.lock     = threading.Lock()
        self.cache    = OrderedDict()
        self.hits     = 0
        self.misses   = 0

    def get(self, key: str):
        with self.lock:
            if key not in self.cache:
                self.misses += 1
                return None
            self.cache.move_to_end(key)
            self.hits += 1
            return self.cache[key]

    def put(self, key: str, value) -> Optional[str]:
        """Returns the evicted key if capacity was exceeded, else None."""
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

    def hit_ratio(self):
        total = self.hits + self.misses
        return round(self.hits / total, 3) if total > 0 else 0.0


# ── Two-level cache: LRU + Redis ───────────────────────────────────────────────

class LayerScanCache:
    """
    Drop-in replacement for the original LayerScanCache.

    Constructor signature is unchanged — existing code that does:
        LayerScanCache(capacity=1000, ttl_seconds=3600)
    keeps working exactly as before.

    The Redis backend is detected and connected automatically.
    If Redis is unavailable the class runs in memory-only mode.
    """

    def __init__(self, capacity: int = 1000, ttl_seconds: int = 3600):
        self.lru         = LRUCache(capacity=capacity)
        self.ttl_seconds = ttl_seconds
        self._redis      = _make_redis()
        self._lru_hits   = 0
        self._redis_hits = 0
        self._misses     = 0

        # Warm LRU from Redis on startup so node restart is not a cold start
        if self._redis:
            self._warm_from_redis()

    # ── Public API (same as original) ─────────────────────────────────────────

    def get(self, layer_hash: str):
        """
        1. Check LRU (fastest — in memory).
        2. On miss, check Redis (slower but persistent).
        3. If found in Redis, re-hydrate the LRU.
        4. Return None if not found anywhere.
        """
        # Level 1: LRU
        item = self.lru.get(layer_hash)
        if item is not None:
            if time.time() <= item["expires_at"]:
                self._lru_hits += 1
                return item["data"]
            # Expired in LRU — clean up both layers
            self.lru.delete(layer_hash)
            self._delete_from_redis(layer_hash)

        # Level 2: Redis fallback
        if self._redis:
            try:
                raw = self._redis.get(REDIS_KEY_PREFIX + layer_hash)
                if raw:
                    payload = json.loads(raw)
                    if time.time() <= payload.get("expires_at", 0):
                        # Re-hydrate LRU so next request is served from memory
                        self.lru.put(layer_hash, payload)
                        self._redis_hits += 1
                        logger.info(
                            f"Cache: Redis fallback HIT for {layer_hash[:16]}... "
                            f"(LRU was cold — re-hydrated)"
                        )
                        return payload["data"]
                    else:
                        # Expired in Redis — clean up
                        self._delete_from_redis(layer_hash)
            except Exception as exc:
                logger.warning(f"Cache: Redis GET error — {exc}")

        self._misses += 1
        return None

    def put(self, layer_hash: str, scan_result: dict):
        """
        Write to LRU immediately, then write-through to Redis with TTL.
        If LRU evicts an entry due to capacity, remove it from Redis too.
        """
        payload = {
            "data":       scan_result,
            "created_at": time.time(),
            "expires_at": time.time() + self.ttl_seconds,
        }
        evicted = self.lru.put(layer_hash, payload)

        # Write-through to Redis
        if self._redis:
            try:
                self._redis.setex(
                    REDIS_KEY_PREFIX + layer_hash,
                    self.ttl_seconds,
                    json.dumps(payload),
                )
            except Exception as exc:
                logger.warning(f"Cache: Redis SET error — {exc}")

        # If LRU evicted an entry, remove it from Redis too
        if evicted:
            self._delete_from_redis(evicted)

    def delete(self, layer_hash: str):
        """Remove from both LRU and Redis."""
        self.lru.delete(layer_hash)
        self._delete_from_redis(layer_hash)

    def stats(self) -> dict:
        """Extended stats — same base keys as original plus Redis fields."""
        base = {
            "entries":     self.lru.size(),
            "capacity":    self.lru.capacity,
            "ttl_seconds": self.ttl_seconds,
            "lru_hits":    self._lru_hits,
            "redis_hits":  self._redis_hits,
            "misses":      self._misses,
            "hit_ratio":   self._hit_ratio(),
            "backend":     "redis+lru" if self._redis else "lru-only",
        }
        if self._redis:
            try:
                redis_entries = self._redis.keys(REDIS_KEY_PREFIX + "*")
                base["redis_entries"] = len(redis_entries)
            except Exception:
                base["redis_entries"] = "unavailable"
        return base

    # ── Private helpers ────────────────────────────────────────────────────────

    def _hit_ratio(self) -> float:
        total = self._lru_hits + self._redis_hits + self._misses
        hits  = self._lru_hits + self._redis_hits
        return round(hits / total, 3) if total > 0 else 0.0

    def _delete_from_redis(self, layer_hash: str):
        if self._redis:
            try:
                self._redis.delete(REDIS_KEY_PREFIX + layer_hash)
            except Exception:
                pass

    def _warm_from_redis(self):
        """
        On startup, load all unexpired cache entries from Redis into the LRU.
        This means a cache node restart does NOT cause a cache cold-start.

        Example output:
            Cache Recovery: Found 3 entries in Redis — warming LRU...
            Cache Recovery: Restored layer_hash=653bc09ee38cff31... (expires in 3421s)
            Cache Recovery: Complete — 3 entries restored, 0 skipped (LRU full)
        """
        try:
            keys = self._redis.keys(REDIS_KEY_PREFIX + "*")
            if not keys:
                logger.info("Cache Recovery: Redis empty — starting fresh")
                return

            logger.info(f"Cache Recovery: Found {len(keys)} entries in Redis — warming LRU...")

            restored = 0
            skipped  = 0
            now      = time.time()

            for full_key in keys:
                try:
                    raw = self._redis.get(full_key)
                    if not raw:
                        continue
                    payload = json.loads(raw)
                    if now > payload.get("expires_at", 0):
                        # Already expired — skip
                        self._redis.delete(full_key)
                        continue

                    layer_hash = full_key[len(REDIS_KEY_PREFIX):]
                    evicted    = self.lru.put(layer_hash, payload)
                    expires_in = round(payload["expires_at"] - now)

                    if evicted:
                        skipped += 1
                    else:
                        restored += 1
                        logger.info(
                            f"Cache Recovery: Restored {layer_hash[:16]}... "
                            f"(expires in {expires_in}s)"
                        )
                except Exception as exc:
                    logger.warning(f"Cache Recovery: Could not restore key {full_key}: {exc}")

            logger.info(
                f"Cache Recovery: Complete — "
                f"{restored} entries restored, {skipped} skipped (LRU full)"
            )
        except Exception as exc:
            logger.warning(f"Cache Recovery: Failed to warm from Redis — {exc}")


# ── Consistent Hash Ring (unchanged from original) ────────────────────────────

class ConsistentHashRing:
    def __init__(self, nodes=None, virtual_replicas: int = 100):
        self.virtual_replicas = virtual_replicas
        self.ring        = {}
        self.sorted_keys = []
        self.nodes       = set()

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
        for i in range(self.virtual_replicas):
            h = self._hash(f"{node}#{i}")
            self.ring.pop(h, None)
        self.sorted_keys = sorted(self.ring.keys())

    def get_node(self, key: str) -> Optional[str]:
        if not self.ring:
            return None
        h   = self._hash(key)
        idx = bisect_right(self.sorted_keys, h)
        if idx == len(self.sorted_keys):
            idx = 0
        return self.ring[self.sorted_keys[idx]]

    def get_ring_view(self) -> dict:
        return {
            "nodes":           list(self.nodes),
            "virtual_replicas": self.virtual_replicas,
            "ring_size":       len(self.sorted_keys),
        }