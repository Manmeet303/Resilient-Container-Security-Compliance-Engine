import asyncio
from datetime import datetime

import httpx

from cache.worker_cache_client import DistributedCacheClient, build_layer_hash
from shared.utils.logger import get_logger

logger = get_logger("scheduler.dispatcher")

CACHE_NODES       = ["http://localhost:9001"]
CONTROL_PLANE_URL = "http://localhost:9000"


class Dispatcher:

    def __init__(self, queue, registry):
        self.queue        = queue
        self.registry     = registry
        self.cache_client = DistributedCacheClient(CACHE_NODES)

    async def dispatch_loop(self):
        while True:
            workers = self.registry.available_workers()
            if not workers:
                logger.warning("No workers available")
                await asyncio.sleep(1)
                continue

            job       = await self.queue.dequeue()
            worker_id = workers[0]
            worker_node = self.registry.get_worker(worker_id)

            if worker_node is None:
                logger.warning(f"Worker node not found for {worker_id}. Re-queueing.")
                await self.queue.requeue(job)
                await asyncio.sleep(1)
                continue

            job["worker_id"] = worker_id
            self.registry.update_load(
                worker_id,
                self.registry.workers[worker_id]["load"] + 1,
            )
            logger.info(
                f"Dispatching job {job['job_id'][:8]} "
                f"to worker {worker_id[:8]}"
            )
            # Run concurrently — don't block next job
            asyncio.create_task(self._run_job(job, worker_id, worker_node))

    async def _run_job(self, job, worker_id, worker_node):
        start = datetime.utcnow()
        try:
            result = await worker_node.process_job(job)

            elapsed_ms = round(
                (datetime.utcnow() - start).total_seconds() * 1000, 1
            )
            result["elapsed_ms"] = elapsed_ms

            # Write scan result to Mahip's cache
            layer_hash = job.get("image_id") or build_layer_hash(
                job["image_name"], job["image_name"]
            )
            # Write directly to cache node via async httpx — bypasses sync requests issue
            try:
                async with httpx.AsyncClient() as cache_http:
                    cache_resp = await cache_http.post(
                        f"http://localhost:9001/cache",
                        json={"layer_hash": layer_hash, "scan_result": result},
                        timeout=3.0,
                    )
                    logger.info(f"Cache write: {cache_resp.status_code} | hash={layer_hash[:16]}")
            except Exception as cache_exc:
                logger.error(f"Cache write FAILED: {cache_exc}")
            logger.info(
                f"Completed job {job['job_id'][:8]} on worker {worker_id[:8]} "
                f"({elapsed_ms}ms) | cached hash={layer_hash[:16]}..."
            )

            self.queue.complete(job["job_id"], result)

            # Notify control plane — dashboard shows scan_complete in live feed
            await self._notify_scan_complete(result, job)

            # Push updated queue depth so dashboard counter drops in real-time
            await self._notify_queue_depth()

        except Exception as exc:
            logger.error(f"Worker {worker_id[:8]} failed job {job['job_id'][:8]}: {exc}")
            await self.queue.requeue(job)

        finally:
            current_load = self.registry.workers.get(worker_id, {}).get("load", 1)
            self.registry.update_load(worker_id, max(0, current_load - 1))

    async def _notify_queue_depth(self):
        """Tell control plane the current queue depth after each job completes."""
        try:
            pending  = self.queue._queue.qsize() if hasattr(self.queue, '_queue') else 0
            inflight = len(self.queue._in_flight) if hasattr(self.queue, '_in_flight') else 0
            # Redis queue — use async stats
            if hasattr(self.queue, 'stats'):
                try:
                    stats    = await self.queue.stats()
                    pending  = stats.get("pending", 0)
                    inflight = stats.get("inflight", 0)
                except Exception:
                    pass
            depth = pending + inflight
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"{CONTROL_PLANE_URL}/internal/queue/depth",
                    json={"depth": depth},
                    timeout=1.0,
                )
        except Exception:
            pass

    async def _notify_scan_complete(self, result: dict, job: dict):
        """POST scan completion to control plane so dashboard live feed updates."""
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"{CONTROL_PLANE_URL}/internal/scan/complete",
                    json={
                        "job_id":          job["job_id"],
                        "worker_id":       result.get("worker_id"),
                        "image_name":      job.get("image_name"),
                        "container_id":    job.get("container_id"),
                        "elapsed_ms":      result.get("elapsed_ms"),
                        "timestamp":       result.get("timestamp"),
                        # 🚨 NEW: Forward the Trivy results!
                        "vulnerabilities": result.get("vulnerabilities", {}),
                        "status":          result.get("status", "unknown"),
                    },
                    timeout=2.0,
                )
        except Exception as exc:
            logger.warning(f"Could not notify control plane of scan complete: {exc}")