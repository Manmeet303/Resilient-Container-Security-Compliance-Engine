import requests
from cache.cache_common import ConsistentHashRing, sha256_text
from shared.utils.logger import get_logger

logger = get_logger("cache.worker_cache_client")


class DistributedCacheClient:
    def __init__(self, cache_nodes: list, virtual_replicas: int = 100):
        self.cache_nodes = list(cache_nodes)          # master list — never shrinks
        self.ring = ConsistentHashRing(cache_nodes, virtual_replicas=virtual_replicas)

    def get_responsible_node(self, layer_hash: str) -> str:
        node = self.ring.get_node(layer_hash)
        if not node:
            raise RuntimeError("No cache nodes available in ring")
        return node

    # ── GET — with automatic failover to next ring node ───────────────────────

    def get_layer_scan(self, layer_hash: str):
        """
        Try the responsible node first. If it's down, walk the ring to the next
        available node. This means one dead cache node never blocks a lookup.
        """
        tried = set()

        # Try up to len(cache_nodes) times — one per node in the ring
        for _ in range(len(self.cache_nodes)):
            node = self.ring.get_node(layer_hash)
            if not node or node in tried:
                break
            tried.add(node)

            url = f"{node}/cache/{layer_hash}"
            try:
                response = requests.get(url, timeout=3)
                response.raise_for_status()
                data = response.json()
                if node != self._primary_node(layer_hash):
                    logger.info(f"Cache GET served by fallback node {node}")
                return data

            except requests.RequestException as exc:
                logger.warning(
                    f"Cache node {node} unreachable on GET "
                    f"(hash={layer_hash[:12]}): {exc} — trying next node"
                )
                # Temporarily remove from ring so next iteration picks a different node
                self.ring.remove_node(node)
                # Schedule re-add after a short delay (best-effort — sync context)
                self._schedule_readd(node)

        # All nodes tried and failed
        logger.error(f"All cache nodes failed for GET hash={layer_hash[:12]}")
        return {"hit": False, "error": "all_nodes_unreachable", "layer_hash": layer_hash}

    # ── PUT — write-through to ALL nodes ─────────────────────────────────────

    def put_layer_scan(self, layer_hash: str, scan_result: dict):
        """
        Write to every known cache node, not just the responsible one.
        This means a lookup always hits regardless of which node the ring
        routes to — important during node restarts or ring rebalancing.
        Falls back gracefully if some nodes are down.
        """
        payload  = {"layer_hash": layer_hash, "scan_result": scan_result}
        success  = 0
        last_err = None

        for node in self.cache_nodes:
            url = f"{node}/cache"
            try:
                response = requests.post(url, json=payload, timeout=3)
                response.raise_for_status()
                success += 1
                logger.info(f"Cache write-through OK → {node} (hash={layer_hash[:12]}...)")
            except requests.RequestException as exc:
                last_err = str(exc)
                logger.warning(f"Cache write-through FAILED → {node}: {exc}")

        if success == 0:
            return {"status": "error", "error": last_err, "layer_hash": layer_hash}

        return {
            "status":       "stored",
            "layer_hash":   layer_hash,
            "nodes_written": success,
            "nodes_total":   len(self.cache_nodes),
        }

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _primary_node(self, layer_hash: str) -> str:
        """Return the hash-responsible node without any failover logic."""
        return self.ring.get_node(layer_hash) or ""

    def _schedule_readd(self, node: str):
        """
        Re-add a removed node to the ring in a background thread.
        Pings /health — only re-adds if the node has recovered.
        Uses a thread because this client is called from sync contexts.
        """
        import threading

        def _check_and_readd():
            import time
            time.sleep(15)          # wait 15s before checking recovery
            try:
                r = requests.get(f"{node}/health", timeout=2)
                if r.status_code == 200:
                    self.ring.add_node(node)
                    logger.info(f"Cache node {node} recovered — re-added to ring")
                else:
                    logger.warning(f"Cache node {node} still unhealthy — not re-added")
            except Exception:
                logger.warning(f"Cache node {node} still unreachable after 15s")

        t = threading.Thread(target=_check_and_readd, daemon=True)
        t.start()

    def ring_view(self):
        """Return current ring state — useful for debugging."""
        return self.ring.get_ring_view()


def build_layer_hash(image_name: str, layer_digest: str) -> str:
    """Build a stable SHA-256 cache key for a container image layer."""
    return sha256_text(f"{image_name}:{layer_digest}")