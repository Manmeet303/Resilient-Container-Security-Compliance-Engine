import asyncio
import uuid
from shared.utils.logger import get_logger

logger = get_logger("scheduler.worker")


class WorkerNode:
    def __init__(self, registry, name=None):
        self.registry = registry
        self.worker_id = name or str(uuid.uuid4())
        self.alive = True
        self.registry.register(self.worker_id, self)

    async def heartbeat_loop(self):
        while self.alive:
            self.registry.heartbeat(self.worker_id)
            await asyncio.sleep(2)

    def fail(self):
        logger.warning(f"Worker {self.worker_id} is being FAILED intentionally.")
        self.alive = False

    async def process_job(self, job):
        logger.info(f"Worker {self.worker_id} processing {job['job_id']}")

        # Long-running job so you can see failover happen
        for step in range(15):
            if not self.alive:
                logger.error(
                    f"Worker {self.worker_id} died during job {job['job_id']}"
                )
                raise RuntimeError(
                    f"Worker {self.worker_id} died during processing"
                )
            await asyncio.sleep(1)

        return {"status": "scan_complete", "worker_id": self.worker_id}