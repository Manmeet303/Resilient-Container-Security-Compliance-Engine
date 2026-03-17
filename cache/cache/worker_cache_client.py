import requests
from cache.cache_common import ConsistentHashRing, sha256_text


class DistributedCacheClient:
    def __init__(self, cache_nodes: list[str], virtual_replicas: int = 100):
        self.cache_nodes = cache_nodes
        self.ring = ConsistentHashRing(cache_nodes, virtual_replicas=virtual_replicas)

    def get_responsible_node(self, layer_hash: str) -> str:
        node = self.ring.get_node(layer_hash)
        if not node:
            raise RuntimeError("No cache nodes available")
        return node

    def get_layer_scan(self, layer_hash: str):
        node = self.get_responsible_node(layer_hash)
        url = f"{node}/cache/{layer_hash}"

        try:
            response = requests.get(url, timeout=3)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            return {
                "hit": False,
                "error": str(exc),
                "layer_hash": layer_hash,
                "node": node,
            }

    def put_layer_scan(self, layer_hash: str, scan_result: dict):
        node = self.get_responsible_node(layer_hash)
        url = f"{node}/cache"

        payload = {
            "layer_hash": layer_hash,
            "scan_result": scan_result,
        }

        try:
            response = requests.post(url, json=payload, timeout=3)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            return {
                "status": "error",
                "error": str(exc),
                "layer_hash": layer_hash,
                "node": node,
            }


def build_layer_hash(image_name: str, layer_digest: str) -> str:
    """
    Build a stable cache key for a container layer.
    """
    return sha256_text(f"{image_name}:{layer_digest}")