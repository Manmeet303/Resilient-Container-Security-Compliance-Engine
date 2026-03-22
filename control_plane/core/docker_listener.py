import asyncio
import hashlib
import uuid
from datetime import datetime

import docker
from docker.errors import DockerException

from shared.utils.logger import get_logger

# Singleton queue shared with SchedulerService/Dispatcher
from scheduler.queue.job_queue import get_queue

# Mahip's distributed cache client
from cache.worker_cache_client import DistributedCacheClient, build_layer_hash

logger = get_logger("control_plane.docker_listener")

WATCHED_EVENTS = {"start", "die", "stop", "kill"}

# Cache node URLs — match docker-compose / local ports
CACHE_NODES = [
    "http://localhost:8001",
    "http://localhost:8002",
]


class DockerEventListener:

    def __init__(self, state_store, resilience_engine, ws_manager):
        self.state_store = state_store
        self.resilience_engine = resilience_engine
        self.ws_manager = ws_manager

        # Singleton queue — same object SchedulerService/Dispatcher uses
        self.job_queue = get_queue()

        # Distributed cache client (consistent hashing across Mahip's nodes)
        self.cache_client = DistributedCacheClient(CACHE_NODES)

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

        # Reconnect loop — retries every 5 s if Docker socket drops
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
                logger.warning(
                    f"Docker listener disconnected: {exc}. Retrying in 5s..."
                )
                await asyncio.sleep(5)

    # ── Event handler ──────────────────────────────────────────────────────────

    async def _handle_event(self, raw_event):
        action = raw_event.get("Action", "")
        actor = raw_event.get("Actor", {})
        attrs = actor.get("Attributes", {})

        # 12-char short ID — used consistently across all modules
        container_id = actor.get("ID", "")[:12]
        container_name = attrs.get("name", "unknown")
        image_name = attrs.get("image", "unknown")

        event_payload = {
            "event_id": str(uuid.uuid4()),
            "event_type": f"container_{action}",
            "container_id": container_id,
            "container_name": container_name,
            "image_name": image_name,
            "timestamp": datetime.utcnow().isoformat(),
        }

        logger.info(
            f"Docker event: {action} | container={container_name} | image={image_name}"
        )

        # ── container_start ────────────────────────────────────────────────────
        if action == "start":
            self.state_store.upsert_container(container_id, {
                "container_id": container_id,
                "name": container_name,
                "image": image_name,
                "status": "running",
            })

            # Build SHA-256 cache key for this image layer
            layer_digest = attrs.get("digest", image_name)
            layer_hash = build_layer_hash(image_name, layer_digest)

            # Check Mahip's distributed cache before dispatching scan
            cache_response = self.cache_client.get_layer_scan(layer_hash)

            if cache_response.get("hit"):
                # Cache HIT — reuse result, skip Trivy scan
                logger.info(
                    f"Cache HIT for {image_name} (hash={layer_hash[:16]}...) "
                    f"on node {cache_response.get('node_id', '?')}"
                )
                self.state_store.append_audit({
                    **event_payload,
                    "action": "cache_hit",
                    "layer_hash": layer_hash,
                    "cached_result": cache_response.get("scan_result"),
                })

            else:
                # Cache MISS — enqueue scan job for Margesh's dispatcher
                logger.info(
                    f"Cache MISS for {image_name} (hash={layer_hash[:16]}...). "
                    f"Enqueuing scan job."
                )
                job_id = await self.job_queue.enqueue(
                    container_id=container_id,
                    image_id=layer_hash,
                    image_name=image_name,
                )
                self.state_store.set_queue_depth(self.job_queue.depth())
                self.state_store.append_audit({
                    **event_payload,
                    "action": "scan_enqueued",
                    "job_id": job_id,
                    "layer_hash": layer_hash,
                })

        # ── container_die / stop / kill ────────────────────────────────────────
        elif action in ("die", "stop", "kill"):
            new_status = "dead" if action == "die" else "stopped"
            self.state_store.upsert_container(container_id, {"status": new_status})
            self.state_store.append_audit({
                **event_payload,
                "action": "container_stopped",
            })

            # Only trigger auto-failover on unintentional die (not manual stop/kill)
            if action == "die":
                await self.resilience_engine.handle_container_die(
                    container_id, container_name, image_name
                )

        # ── Broadcast all events to dashboard via WebSocket ────────────────────
        await self.ws_manager.broadcast(event_payload)
