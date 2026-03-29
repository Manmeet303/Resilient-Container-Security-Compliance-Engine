import asyncio
from datetime import datetime
from shared.utils.logger import get_logger
from cache.worker_cache_client import DistributedCacheClient, build_layer_hash

logger = get_logger("scheduler.dispatcher")

CACHE_NODES = ["http://localhost:8001", "http://localhost:8002"]


class Dispatcher:

    def __init__(self, queue, registry):
        self.queue = queue
        self.registry = registry
        self.cache_client = DistributedCacheClient(CACHE_NODES)

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
                logger.warning(
                    f"Worker node not found for {worker_id}. Re-queueing job."
                )
                await self.queue.requeue(job)
                await asyncio.sleep(1)
                continue

            job["worker_id"] = worker_id
            self.registry.update_load(
                worker_id,
                self.registry.workers[worker_id]["load"] + 1
            )

            logger.info(f"Dispatching job {job['job_id']} to worker {worker_id}")

            # Run in background so dispatch_loop immediately picks up next job
            # Without this, jobs process one-by-one and 20 containers = 60s wait
            asyncio.create_task(self._run_job(job, worker_id, worker_node))

    async def _run_job(self, job, worker_id, worker_node):
        """Process one job and write result back to cache."""
        start = datetime.utcnow()
        try:
            result = await worker_node.process_job(job)

            elapsed_ms = round(
                (datetime.utcnow() - start).total_seconds() * 1000, 1
            )
            result["elapsed_ms"] = elapsed_ms

            # Write scan result back to Mahip's cache
            # Next time same image starts → cache HIT, Trivy scan skipped
            layer_hash = job.get("image_id") or build_layer_hash(
                job["image_name"], job["image_name"]
            )
            self.cache_client.put_layer_scan(layer_hash, result)
            logger.info(
                f"Completed job {job['job_id']} on worker {worker_id} "
                f"({elapsed_ms}ms) | cached hash={layer_hash[:16]}..."
            )

            self.queue.complete(job["job_id"], result)

        except Exception as exc:
            logger.error(
                f"Worker {worker_id} failed job {job['job_id']}: {exc}"
            )
            await self.queue.requeue(job)

        finally:
            current_load = self.registry.workers.get(worker_id, {}).get("load", 1)
            self.registry.update_load(worker_id, max(0, current_load - 1))