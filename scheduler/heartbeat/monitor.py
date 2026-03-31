import asyncio
import time
from shared.utils.logger import get_logger
from control_plane.core.state_store import StateStore

logger = get_logger("scheduler.heartbeat")


class HeartbeatMonitor:
    def __init__(self, registry, queue, timeout=6):
        self.registry = registry
        self.queue = queue
        self.timeout = timeout
        self.state_store = StateStore()

    async def monitor(self):
        while True:
            now = time.time()

            for worker_id, info in list(self.registry.workers.items()):
                if info["status"] == "dead":
                    continue

                if now - info["last_heartbeat"] > self.timeout:
                    logger.warning(f"Worker failure detected: {worker_id}")
                    self.registry.mark_dead(worker_id)

                    self.state_store.upsert_worker(
                        worker_id,
                        {
                            "worker_id": worker_id,
                            "status": "dead",
                            "load": info.get("load", 0),
                        },
                    )

                    jobs_to_requeue = [
                        job for job in list(self.queue._in_flight.values())
                        if job.get("worker_id") == worker_id
                    ]

                    for job in jobs_to_requeue:
                        logger.warning(
                            f"Worker {worker_id} died while handling job {job['job_id']}. Re-enqueueing job."
                        )
                        await self.queue.requeue(job)

            self.state_store.set_queue_depth(self.queue.depth())
            await asyncio.sleep(2)