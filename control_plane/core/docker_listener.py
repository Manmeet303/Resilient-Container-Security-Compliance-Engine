import asyncio
import uuid
from datetime import datetime

import docker
from docker.errors import DockerException

from shared.utils.logger import get_logger
from scheduler.queue.job_queue import get_queue
from cache.worker_cache_client import DistributedCacheClient, build_layer_hash

logger = get_logger("control_plane.docker_listener")

WATCHED_EVENTS = {"start", "die", "stop", "kill"}

CACHE_NODES = [
    "http://localhost:8001",
    "http://localhost:8002",
]


class DockerEventListener:
    def __init__(self, state_store, resilience_engine, ws_manager):
        self.state_store = state_store
        self.resilience_engine = resilience_engine
        self.ws_manager = ws_manager

        self.job_queue = get_queue()
        self.cache_client = DistributedCacheClient(CACHE_NODES)

        try:
            self.client = docker.from_env()
            logger.info("Connected to Docker daemon via /var/run/docker.sock")
        except DockerException as exc:
            logger.error(f"Cannot connect to Docker daemon: {exc}")
            self.client = None

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
                logger.warning(
                    f"Docker listener disconnected: {exc}. Retrying in 5s..."
                )
                await asyncio.sleep(5)

    async def _handle_event(self, raw_event):
        action = raw_event.get("Action", "")
        actor = raw_event.get("Actor", {})
        attrs = actor.get("Attributes", {})

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

        if action == "start":
            self.state_store.upsert_container(
                container_id,
                {
                    "container_id": container_id,
                    "name": container_name,
                    "image": image_name,
                    "status": "running",
                },
            )

            layer_digest = attrs.get("digest", image_name)
            layer_hash = build_layer_hash(image_name, layer_digest)

            cache_response = self.cache_client.get_layer_scan(layer_hash)

            if cache_response.get("hit"):
                logger.info(
                    f"Cache HIT for {image_name} (hash={layer_hash[:16]}...) — skipping scan."
                )
                self.state_store.record_cache_event(hit=True)
                self.state_store.append_audit(
                    {
                        **event_payload,
                        "action": "cache_hit",
                        "layer_hash": layer_hash,
                    }
                )
            else:
                logger.info(
                    f"Cache MISS for {image_name} (hash={layer_hash[:16]}...) — creating placeholder and enqueuing scan."
                )
                self.state_store.record_cache_event(hit=False)

                placeholder_result = {
                    "container_id": container_id,
                    "container_name": container_name,
                    "image_name": image_name,
                    "status": "loaded",
                    "scan_status": "pending",
                    "timestamp": datetime.utcnow().isoformat(),
                }
                self.cache_client.put_layer_scan(layer_hash, placeholder_result)

                logger.info(
                    f"Placeholder cache entry stored for {container_name} with hash {layer_hash}"
                )

                self.state_store.append_audit(
                    {
                        **event_payload,
                        "action": "cache_miss",
                        "layer_hash": layer_hash,
                    }
                )

                # enqueue scan job using your actual queue API
                await self.job_queue.enqueue(
                    container_id=container_id,
                    image_id=image_name,
                    image_name=image_name,
                )

        elif action in ("die", "stop", "kill"):
            new_status = "dead" if action == "die" else "stopped"
            self.state_store.upsert_container(container_id, {"status": new_status})
            self.state_store.append_audit(
                {
                    **event_payload,
                    "action": "container_stopped",
                }
            )

            await self.resilience_engine.handle_container_die(
                container_id, container_name, image_name
            )

        await self.ws_manager.broadcast(event_payload)