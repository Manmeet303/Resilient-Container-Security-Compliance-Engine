"""
cache/worker_cache_client.py
─────────────────────────────
HTTP client used by worker nodes to talk to the distributed cache shards.

Changes from original
─────────────────────
• update_layer_scan() – send an updated scan result when a worker
  re-scans a layer.
• invalidate_layer_scan() – remove a specific entry from the cache
  (e.g. when a CVE database update makes old results stale).
• get_stats() – fetch the extended stats from a responsible node.
• All methods handle network errors gracefully and return structured
  error dicts instead of raising, matching the original pattern.
"""

import requests

from cache.cache_common import ConsistentHashRing, sha256_text


class DistributedCacheClient:
    def __init__(self, cache_nodes: list, virtual_replicas: int = 100):
        self.cache_nodes = cache_nodes
        self.ring = ConsistentHashRing(cache_nodes, virtual_replicas=virtual_replicas)

    # ------------------------------------------------------------------ #
    #  Routing                                                             #
    # ------------------------------------------------------------------ #

    def get_responsible_node(self, layer_hash: str) -> str:
        node = self.ring.get_node(layer_hash)
        if not node:
            raise RuntimeError("No cache nodes available")
        return node

    # ------------------------------------------------------------------ #
    #  Core CRUD                                                           #
    # ------------------------------------------------------------------ #

    def get_layer_scan(self, layer_hash: str) -> dict:
        """Fetch a cached scan result. Returns {hit: bool, scan_result: ...}."""
        node = self.get_responsible_node(layer_hash)
        try:
            r = requests.get(f"{node}/cache/{layer_hash}", timeout=3)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as exc:
            return {"hit": False, "error": str(exc), "layer_hash": layer_hash, "node": node}

    def put_layer_scan(self, layer_hash: str, scan_result: dict) -> dict:
        """Store a new scan result. Overwrites silently if the key exists."""
        node = self.get_responsible_node(layer_hash)
        payload = {"layer_hash": layer_hash, "scan_result": scan_result}
        try:
            r = requests.post(f"{node}/cache", json=payload, timeout=3)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as exc:
            return {"status": "error", "error": str(exc), "layer_hash": layer_hash, "node": node}

    def update_layer_scan(self, layer_hash: str, scan_result: dict) -> dict:
        """
        Overwrite an existing scan result and reset its TTL.
        Use when a re-scan produces a fresher report for an already-cached layer.
        Returns {"status": "updated"} on success, or an error dict / 404 detail.
        """
        node = self.get_responsible_node(layer_hash)
        try:
            r = requests.put(
                f"{node}/cache/{layer_hash}",
                json={"scan_result": scan_result},
                timeout=3,
            )
            r.raise_for_status()
            return r.json()
        except requests.HTTPError as exc:
            return {"status": "not_found", "error": str(exc), "layer_hash": layer_hash, "node": node}
        except requests.RequestException as exc:
            return {"status": "error", "error": str(exc), "layer_hash": layer_hash, "node": node}

    def invalidate_layer_scan(self, layer_hash: str) -> dict:
        """
        Hard-delete a cache entry from the responsible node (LRU + DB).
        Useful when a CVE database update makes existing scan results stale.
        """
        node = self.get_responsible_node(layer_hash)
        try:
            r = requests.delete(f"{node}/cache/{layer_hash}", timeout=3)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as exc:
            return {"status": "error", "error": str(exc), "layer_hash": layer_hash, "node": node}

    def get_stats(self, layer_hash: str) -> dict:
        """Fetch extended stats from the node responsible for layer_hash."""
        node = self.get_responsible_node(layer_hash)
        try:
            r = requests.get(f"{node}/cache/stats", timeout=3)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as exc:
            return {"status": "error", "error": str(exc), "node": node}


# ─────────────────────────────────────────────────────────────────────── #
#  Helper                                                                 #
# ─────────────────────────────────────────────────────────────────────── #

def build_layer_hash(image_name: str, layer_digest: str) -> str:
    """Build a stable SHA-256 cache key for a container image layer."""
    return sha256_text(f"{image_name}:{layer_digest}")