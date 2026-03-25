import asyncio
from shared.utils.logger import get_logger

logger = get_logger("scheduler.dispatcher")


class Dispatcher:
    def __init__(self, queue, registry):
        self.queue = queue
        self.registry = registry

    async def dispatch_loop(self):
        while True:
            workers = self.registry.available_workers()

            if not workers:
                logger.warning("No workers available")
                await asyncio.sleep(1)
                continue

            job = await self.queue.dequeue()

            worker_id = workers[0]
            worker_node = self.registry.get_worker(worker_id)

            if worker_node is None:
                logger.warning(f"Worker node not found for {worker_id}. Re-queueing job.")
                await self.queue.requeue(job)
                await asyncio.sleep(1)
                continue

            job["worker_id"] = worker_id
            self.registry.update_load(
                worker_id,
                self.registry.workers[worker_id]["load"] + 1
            )

            logger.info(f"Dispatching job {job['job_id']} to worker {worker_id}")

            try:
                result = await worker_node.process_job(job)
                self.queue.complete(job["job_id"], result)
                logger.info(f"Completed job {job['job_id']} on worker {worker_id}")
            except Exception as exc:
                logger.error(f"Worker {worker_id} failed job {job['job_id']}: {exc}")
                await self.queue.requeue(job)
            finally:
                current_load = self.registry.workers.get(worker_id, {}).get("load", 1)
                self.registry.update_load(worker_id, max(0, current_load - 1))