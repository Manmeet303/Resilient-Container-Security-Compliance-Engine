import asyncio
from datetime import datetime
import docker
from docker.errors import DockerException
from shared.utils.logger import get_logger

logger = get_logger("control_plane.resilience")
HEALTH_POLL_INTERVAL = 0.2
HEALTH_POLL_TIMEOUT = 10.0

class ResilienceEngine:
    def __init__(self, state_store, ws_manager):
        self.state_store = state_store
        self.ws_manager = ws_manager
        try:
            self.docker_client = docker.from_env()
        except DockerException:
            self.docker_client = None
            logger.error("ResilienceEngine: Docker client unavailable.")

    async def handle_container_die(self, container_id, name, image):
        if not self.state_store.is_critical(container_id):
            logger.info(f"Container {name} died — not critical, skipping failover.")
            return
        logger.info(f"CRITICAL container {name} died — initiating auto-failover.")
        await self._failover(container_id, name, image)

    async def _failover(self, original_id, name, image):
        if not self.docker_client:
            logger.error("Cannot failover — Docker client not available.")
            return
        replica_name = f"{name}-replica-{original_id[:6]}"
        start_time = datetime.utcnow()
        try:
            loop = asyncio.get_event_loop()
            container = await loop.run_in_executor(None,
                lambda: self.docker_client.containers.create(image=image, name=replica_name, detach=True))
            logger.info(f"Replica created: {replica_name}")
            await loop.run_in_executor(None, container.start)
            logger.info(f"Replica started: {replica_name}")
            recovered = await self._confirm_healthy(container, loop)
            elapsed_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            status = "recovered" if recovered else "recovery_timeout"
            logger.info(f"Failover: {replica_name} | {status} | {elapsed_ms:.1f}ms")
            audit_entry = {"event_type": "auto_failover", "original_container": original_id,
                           "replica_name": replica_name, "image": image,
                           "status": status, "latency_ms": round(elapsed_ms, 1)}
            self.state_store.append_audit(audit_entry)
            self.state_store.upsert_container(container.id[:12], {
                "container_id": container.id[:12], "name": replica_name,
                "image": image, "status": "running" if recovered else "unknown",
                "is_replica": True, "original_id": original_id})
            self.state_store.mark_critical(container.id[:12])
            await self.ws_manager.broadcast(audit_entry)
        except DockerException as exc:
            logger.error(f"Failover failed for {name}: {exc}")
            self.state_store.append_audit({"event_type": "auto_failover_error",
                                           "original_container": original_id, "error": str(exc)})

    async def _confirm_healthy(self, container, loop):
        elapsed = 0.0
        while elapsed < HEALTH_POLL_TIMEOUT:
            await asyncio.sleep(HEALTH_POLL_INTERVAL)
            elapsed += HEALTH_POLL_INTERVAL
            try:
                await loop.run_in_executor(None, container.reload)
                if container.status == "running":
                    return True
            except DockerException:
                pass
        return False
