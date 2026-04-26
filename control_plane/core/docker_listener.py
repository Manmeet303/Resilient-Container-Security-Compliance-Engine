import asyncio
import uuid
from datetime import datetime

import docker
from docker.errors import DockerException

from shared.utils.logger import get_logger
import httpx
from cache.worker_cache_client import DistributedCacheClient, build_layer_hash
from control_plane.core.log_monitor import LogMonitor

logger = get_logger("control_plane.docker_listener")

WATCHED_EVENTS = {"start", "die", "stop", "kill"}

# Only include cache nodes that are actually running
# Remove 9002 if you're only running one cache node
CACHE_NODES = [
    "http://localhost:9001",
]


class DockerEventListener:

    def __init__(self, state_store, resilience_engine, ws_manager):
        self.state_store       = state_store
        self.resilience_engine = resilience_engine
        self.ws_manager        = ws_manager
        self.scheduler_url     = 'http://localhost:9010'
        self.cache_client      = DistributedCacheClient(CACHE_NODES)
        self.log_monitor       = LogMonitor(state_store, ws_manager)

        try:
            self.client = docker.from_env()
            logger.info("Connected to Docker daemon via /var/run/docker.sock")
        except DockerException as exc:
            logger.error(f"Cannot connect to Docker daemon: {exc}")
            self.client = None

    # ── Main listener loop ─────────────────────────────────────────────────────

    async def listen(self):
        if not self.client:
            logger.error("Docker client unavailable. Listener not started.")
            return

        logger.info("Docker event listener started.")
        loop = asyncio.get_event_loop()

        while True:
            try:
                def _blocking_listen():
                    for raw_event in self.client.events(
                        decode=True, filters={"type": "container"}
                    ):
                        action = raw_event.get("Action", "")
                        if action not in WATCHED_EVENTS:
                            continue
                        asyncio.run_coroutine_threadsafe(
                            self._handle_event(raw_event), loop
                        )

                await loop.run_in_executor(None, _blocking_listen)

            except Exception as exc:
                logger.warning(f"Docker listener disconnected: {exc}. Retrying in 5s...")
                await asyncio.sleep(5)

    # ── Event handler ──────────────────────────────────────────────────────────

    async def _handle_event(self, raw_event):
        action         = raw_event.get("Action", "")
        actor          = raw_event.get("Actor", {})
        attrs          = actor.get("Attributes", {})
        container_id   = actor.get("ID", "")[:12]
        container_name = attrs.get("name", "unknown")
        image_name     = attrs.get("image", "unknown")

        event_payload = {
            "event_id":       str(uuid.uuid4()),
            "event_type":     f"container_{action}",
            "container_id":   container_id,
            "container_name": container_name,
            "image_name":     image_name,
            "timestamp":      datetime.utcnow().isoformat(),
        }

        logger.info(f"Docker event: {action} | container={container_name} | image={image_name}")

        # ── container_start ────────────────────────────────────────────────────
        if action == "start":
            self.state_store.upsert_container(container_id, {
                "container_id": container_id,
                "name":         container_name,
                "image":        image_name,
                "status":       "running",
            })

            # Start log monitor for anomaly detection
            await self.log_monitor.start_monitoring(
                container_id, container_name, image_name
            )

            # Cache check — direct httpx to avoid consistent hash routing issues
            try:
                layer_digest = attrs.get("digest", image_name)
                layer_hash   = build_layer_hash(image_name, layer_digest)
                try:
                    async with httpx.AsyncClient() as cache_http:
                        cr = await cache_http.get(
                            f"http://localhost:9001/cache/{layer_hash}",
                            timeout=2.0,
                        )
                        cache_response = cr.json()
                except Exception:
                    cache_response = {"hit": False}

                if cache_response.get("hit"):
                    # ── CACHE HIT ──────────────────────────────────────────────
                    node_id     = cache_response.get("node_id", "cache-node-1")
                    scan_result = cache_response.get("scan_result") or {}
                    vulns       = scan_result.get("vulnerabilities", {})

                    logger.info(
                        f"Cache HIT for {image_name} "
                        f"(hash={layer_hash[:16]}...) on node {node_id}"
                    )

                    # Record hit in state_store for Cache Performance panel
                    self.state_store.record_cache_event(hit=True)

                    # ── FIX: propagate vuln data so container row resolves ──────
                    # Without this the Vulnerabilities column shows "scanning..."
                    # forever because no scan_complete event is ever fired on HITs.
                    self.state_store.upsert_container(container_id, {
                        "vulnerabilities": vulns,
                        "scan_status":     "cache_hit",
                    })

                    self.state_store.append_audit({
                        **event_payload,
                        "action":        "cache_hit",
                        "layer_hash":    layer_hash,
                        "cached_result": scan_result,
                    })

                    # Broadcast cache_hit (increments counter in UI)
                    await self.ws_manager.broadcast({
                        "event_type":      "cache_hit",
                        "container_id":    container_id,
                        "image_name":      image_name,
                        "layer_hash":      layer_hash,
                        "node_id":         node_id,
                        "timestamp":       event_payload["timestamp"],
                    })

                    # ── FIX: also fire scan_complete so container row updates ───
                    # The dashboard's scan_complete handler updates the vuln column.
                    # Re-using that same event means zero extra UI code needed.
                    await self.ws_manager.broadcast({
                        "event_type":      "scan_complete",
                        "container_id":    container_id,
                        "image_name":      image_name,
                        "vulnerabilities": vulns,
                        "status":          "cache_hit",
                        "elapsed_ms":      0,
                        "timestamp":       event_payload["timestamp"],
                    })

                else:
                    # ── CACHE MISS — enqueue scan job ──────────────────────────
                    logger.info(
                        f"Cache MISS for {image_name} "
                        f"(hash={layer_hash[:16]}...). Enqueuing scan job."
                    )
                    # Record miss in state_store for Cache Performance panel
                    self.state_store.record_cache_event(hit=False)

                    job_id = await self._push_job_to_scheduler(
                        container_id, layer_hash, image_name
                    )
                    self.state_store.append_audit({
                        **event_payload,
                        "action":     "scan_enqueued",
                        "job_id":     job_id,
                        "layer_hash": layer_hash,
                    })

                    # Broadcast so dashboard can count misses
                    await self.ws_manager.broadcast({
                        "event_type":   "cache_miss",
                        "container_id": container_id,
                        "image_name":   image_name,
                        "layer_hash":   layer_hash,
                        "timestamp":    event_payload["timestamp"],
                    })

            except Exception as exc:
                logger.warning(f"Cache/Queue error for {image_name}: {exc}")

        # ── container_die / stop / kill ────────────────────────────────────────
        elif action in ("die", "stop", "kill"):
            new_status = "dead" if action == "die" else "stopped"
            self.state_store.upsert_container(container_id, {"status": new_status})
            self.state_store.append_audit({
                **event_payload,
                "action": "container_stopped",
            })

            # Stop log monitor for this container
            await self.log_monitor.stop_monitoring(container_id)

            # Only auto-failover on unexpected die, not manual stop/kill
            if action == "die":
                await self.resilience_engine.handle_container_die(
                    container_id, container_name, image_name
                )

        # ── Broadcast Docker event to dashboard ────────────────────────────────
        await self.ws_manager.broadcast(event_payload)

    async def _push_job_to_scheduler(self, container_id, layer_hash, image_name):
        """Push scan job to scheduler process via HTTP on port 9010."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self.scheduler_url}/jobs/enqueue",
                    json={
                        "container_id": container_id,
                        "image_id":     layer_hash,
                        "image_name":   image_name,
                    },
                    timeout=3.0,
                )
                data = resp.json()
                job_id = data.get("job_id", "unknown")
                logger.info(f"Job pushed to scheduler: {job_id[:8]} | image={image_name}")
                return job_id
        except Exception as exc:
            logger.error(f"Could not push job to scheduler: {exc}")
            return "ipc-failed"