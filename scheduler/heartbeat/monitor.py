import asyncio
import time

import httpx

from shared.utils.logger import get_logger

logger = get_logger("scheduler.heartbeat")

CONTROL_PLANE_URL = "http://localhost:9000"


class HeartbeatMonitor:

    def __init__(self, registry, queue, timeout=10):
        self.registry = registry
        self.queue    = queue
        self.timeout  = timeout

    async def monitor(self):
        async with httpx.AsyncClient() as client:
            while True:
                now = time.time()
                for worker_id, info in list(self.registry.workers.items()):
                    if info["status"] == "dead":
                        continue
                    if now - info["last_heartbeat"] > self.timeout:
                        logger.warning(f"Worker failure detected: {worker_id[:8]}")
                        self.registry.mark_dead(worker_id)

                        # Notify control plane so dashboard shows worker as dead
                        await self._notify_worker_dead(client, worker_id)

                        # Reclaim in-flight jobs from dead worker
                        # Works with both RedisJobQueue and InMemoryJobQueue
                        await self._reclaim_jobs(worker_id)

                await asyncio.sleep(5)

    async def _reclaim_jobs(self, worker_id: str):
        """
        Find all in-flight jobs belonging to the dead worker and requeue them.
        Handles both Redis queue (HGETALL inflight) and in-memory queue (_in_flight dict).
        """
        from scheduler.queue.job_queue import RedisJobQueue, InMemoryJobQueue
        import json

        if isinstance(self.queue, RedisJobQueue):
            # Redis path — scan inflight hash for this worker's jobs
            try:
                inflight = await self.queue._redis.hgetall("rcsce:queue:inflight")
                for job_id, raw in inflight.items():
                    job = json.loads(raw)
                    if job.get("worker_id") == worker_id:
                        logger.warning(
                            f"Reclaiming job {job_id[:8]} from dead worker {worker_id[:8]}"
                        )
                        await self.queue.requeue(job)
            except Exception as exc:
                logger.error(f"Failed to reclaim jobs from Redis: {exc}")

        else:
            # In-memory path — original behavior
            jobs_to_requeue = [
                job for job in list(self.queue._in_flight.values())
                if job.get("worker_id") == worker_id
            ]
            for job in jobs_to_requeue:
                logger.warning(
                    f"Reclaiming job {job['job_id'][:8]} from dead worker {worker_id[:8]}"
                )
                await self.queue.requeue(job)

    async def _notify_worker_dead(self, client: httpx.AsyncClient, worker_id: str):
        """Tell control plane this worker is dead so dashboard updates immediately."""
        try:
            await client.delete(
                f"{CONTROL_PLANE_URL}/internal/workers/{worker_id}",
                timeout=2.0,
            )
            logger.info(f"Notified control plane: worker {worker_id[:8]} dead")
        except Exception as exc:
            logger.warning(f"Could not notify control plane of worker death: {exc}")