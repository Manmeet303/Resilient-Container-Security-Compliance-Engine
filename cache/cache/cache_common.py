import hashlib
import json
import threading
import time
from collections import OrderedDict
from bisect import bisect_right


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class LRUCache:
    def __init__(self, capacity: int = 1000):
        self.capacity = capacity
        self.lock = threading.Lock()
        self.cache = OrderedDict()

    def get(self, key: str):
        with self.lock:
            if key not in self.cache:
                return None
            self.cache.move_to_end(key)
            return self.cache[key]

    def put(self, key: str, value):
        with self.lock:
            if key in self.cache:
                self.cache.move_to_end(key)

            self.cache[key] = value

            if len(self.cache) > self.capacity:
                self.cache.popitem(last=False)

    def delete(self, key: str):
        with self.lock:
            if key in self.cache:
                del self.cache[key]

    def size(self) -> int:
        with self.lock:
            return len(self.cache)

    def keys(self):
        with self.lock:
            return list(self.cache.keys())


class LayerScanCache:
    def __init__(self, capacity: int = 1000, ttl_seconds: int = 3600):
        self.lru = LRUCache(capacity=capacity)
        self.ttl_seconds = ttl_seconds

    def get(self, layer_hash: str):
        item = self.lru.get(layer_hash)
        if item is None:
            return None

        now = time.time()
        if now > item["expires_at"]:
            self.lru.delete(layer_hash)
            return None

        return item["data"]

    def put(self, layer_hash: str, scan_result: dict):
        payload = {
            "data": scan_result,
            "created_at": time.time(),
            "expires_at": time.time() + self.ttl_seconds,
        }
        self.lru.put(layer_hash, payload)

    def stats(self):
        return {
            "entries": self.lru.size(),
            "ttl_seconds": self.ttl_seconds,
            "capacity": self.lru.capacity,
        }


class ConsistentHashRing:
    def __init__(self, nodes=None, virtual_replicas: int = 100):
        self.virtual_replicas = virtual_replicas
        self.ring = {}
        self.sorted_keys = []
        self.nodes = set()

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
            virtual_key = f"{node}#{i}"
            hashed = self._hash(virtual_key)
            self.ring[hashed] = node
            self.sorted_keys.append(hashed)

        self.sorted_keys.sort()

    def remove_node(self, node: str):
        if node not in self.nodes:
            return

        self.nodes.remove(node)
        keys_to_remove = []
        for i in range(self.virtual_replicas):
            virtual_key = f"{node}#{i}"
            hashed = self._hash(virtual_key)
            keys_to_remove.append(hashed)

        for k in keys_to_remove:
            if k in self.ring:
                del self.ring[k]

        self.sorted_keys = sorted(self.ring.keys())

    def get_node(self, key: str):
        if not self.ring:
            return None

        hashed_key = self._hash(key)
        idx = bisect_right(self.sorted_keys, hashed_key)

        if idx == len(self.sorted_keys):
            idx = 0

        return self.ring[self.sorted_keys[idx]]

    def get_ring_view(self):
        return {
            "nodes": list(self.nodes),
            "virtual_replicas": self.virtual_replicas,
            "ring_size": len(self.sorted_keys),
        }