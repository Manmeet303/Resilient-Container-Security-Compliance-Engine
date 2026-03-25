import asyncio
import uuid
from shared.utils.logger import get_logger

logger = get_logger("scheduler.worker")


class WorkerNode:

    def __init__(self, registry):
        self.registry = registry
        self.worker_id = str(uuid.uuid4())
        self.registry.register(self.worker_id, self)

    async def heartbeat_loop(self):
        while True:
            self.registry.heartbeat(self.worker_id)
            await asyncio.sleep(2)

    async def process_job(self, job):
        logger.info(f"Worker {self.worker_id} processing {job['job_id']}")
        await asyncio.sleep(3)
        return {"status": "scan_complete", "worker_id": self.worker_id}
