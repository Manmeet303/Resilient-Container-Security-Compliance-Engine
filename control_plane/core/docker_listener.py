import asyncio, uuid
from datetime import datetime
import docker
from docker.errors import DockerException
from shared.utils.logger import get_logger

logger = get_logger("control_plane.docker_listener")
WATCHED_EVENTS = {"start", "die", "stop", "kill"}

class DockerEventListener:
    def __init__(self, state_store, resilience_engine, ws_manager):
        self.state_store = state_store
        self.resilience_engine = resilience_engine
        self.ws_manager = ws_manager
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
        def _blocking_listen():
            for raw_event in self.client.events(decode=True, filters={"type": "container"}):
                action = raw_event.get("Action", "")
                if action not in WATCHED_EVENTS:
                    continue
                asyncio.run_coroutine_threadsafe(self._handle_event(raw_event), loop)
        await loop.run_in_executor(None, _blocking_listen)

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
        logger.info(f"Docker event: {action} | container={container_name} | image={image_name}")
        if action == "start":
            self.state_store.upsert_container(container_id, {
                "container_id": container_id, "name": container_name,
                "image": image_name, "status": "running"})
            self.state_store.append_audit({**event_payload, "action": "scan_enqueued"})
        elif action == "die":
            self.state_store.upsert_container(container_id, {"status": "dead"})
            self.state_store.append_audit({**event_payload, "action": "container_died"})
            await self.resilience_engine.handle_container_die(container_id, container_name, image_name)
        await self.ws_manager.broadcast(event_payload)
