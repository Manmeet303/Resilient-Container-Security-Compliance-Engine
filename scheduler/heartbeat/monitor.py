import asyncio
import time
from shared.utils.logger import get_logger

logger = get_logger("scheduler.heartbeat")


class HeartbeatMonitor:

    def __init__(self, registry, timeout=10):

        self.registry = registry
        self.timeout = timeout

    async def monitor(self):

        while True:

            now = time.time()

            for worker_id, info in self.registry.workers.items():

                if info["status"] == "dead":
                    continue

                if now - info["last_heartbeat"] > self.timeout:

                    logger.warning(f"Worker failure detected: {worker_id}")

                    self.registry.mark_dead(worker_id)

            await asyncio.sleep(5)