import asyncio, uuid
from datetime import datetime
from shared.utils.logger import get_logger

logger = get_logger("scheduler.job_queue")

class JobQueue:
    def __init__(self):
        self._queue = asyncio.Queue()
        self._in_flight = {}

    async def enqueue(self, container_id, image_id, image_name):
        job_id = str(uuid.uuid4())
        job = {"job_id": job_id, "container_id": container_id,
               "image_id": image_id, "image_name": image_name,
               "status": "pending", "submitted_at": datetime.utcnow().isoformat()}
        await self._queue.put(job)
        logger.info(f"Enqueued job {job_id} for {container_id}")
        return job_id

    async def dequeue(self):
        job = await self._queue.get()
        self._in_flight[job["job_id"]] = job
        return job

    def complete(self, job_id, result):
        if job_id in self._in_flight:
            self._in_flight[job_id].update({"status": "completed", "result": result})
            del self._in_flight[job_id]

    def depth(self):
        return self._queue.qsize()


# ── Singleton ──────────────────────────────────────────────────────────────────
# One shared queue instance used by BOTH docker_listener (producer)
# and SchedulerService/Dispatcher (consumer).
# Import get_queue() everywhere instead of constructing JobQueue() directly.
_global_queue: JobQueue | None = None


def get_queue() -> JobQueue:
    """Return the process-wide singleton JobQueue, creating it on first call."""
    global _global_queue
    if _global_queue is None:
        _global_queue = JobQueue()
        logger.info("Global JobQueue singleton created.")
    return _global_queue