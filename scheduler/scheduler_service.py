"""
scheduler_service.py — RCSCE Distributed Task Scheduler
=========================================================

Runs on port 9010.

Behavior:
- Starts with N workers.
- If a worker dies, scheduler automatically creates ONLY ONE replacement worker.
- Dead workers remain visible for audit/demo proof.
- Alive worker count stays near desired_workers.
- If a worker had an unfinished task, heartbeat monitor requeues it.
"""

import asyncio

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
import uvicorn
import httpx

from scheduler.queue.job_queue import create_queue, get_queue
from scheduler.workers.worker_registry import WorkerRegistry
from scheduler.heartbeat.monitor import HeartbeatMonitor
from scheduler.dispatcher import Dispatcher
from scheduler.workers.worker_node import WorkerNode
from shared.utils.logger import get_logger

logger = get_logger("scheduler.service")

MAX_WORKERS = 20
CONTROL_PLANE_URL = "http://localhost:9000"


class JobRequest(BaseModel):
    container_id: str
    image_id: str
    image_name: str


class SchedulerService:

    def __init__(self):
        self.queue = None
        self.registry = WorkerRegistry()
        self.monitor = None
        self.dispatcher = None
        self._workers = []

        # The number of workers the system should keep alive.
        # Example:
        # Start with 2 workers.
        # If 1 dies, system creates 1 replacement.
        self.desired_workers = 2

        # This remembers which dead workers already got replacements.
        # Without this, the same dead worker can accidentally trigger
        # multiple replacement workers.
        self.replaced_dead_workers = set()

        self.app = FastAPI(title="RCSCE Scheduler — Redis Edition")
        self._setup_routes()

    def _alive_worker_count(self):
        """
        Count only workers that are currently alive.
        Dead workers may still appear in dashboard for audit proof,
        but they are not counted as active workers.
        """
        return sum(
            1 for worker in self.registry.workers.values()
            if worker["status"] == "alive"
        )

    async def _notify_queue_depth(self):
        """
        Push current queue depth to control plane.
        This helps the dashboard show pending/in-flight jobs.
        """
        try:
            q = get_queue()
            stats = await q.stats()
            depth = stats.get("pending", 0) + stats.get("inflight", 0)

            async with httpx.AsyncClient() as client:
                await client.post(
                    f"{CONTROL_PLANE_URL}/internal/queue/depth",
                    json={"depth": depth},
                    timeout=1.0,
                )
        except Exception:
            pass

    async def _notify_worker_dead_to_control_plane(self, worker_id):
        """
        Tell the dashboard/control plane that this worker is dead.
        """
        try:
            async with httpx.AsyncClient() as client:
                await client.delete(
                    f"{CONTROL_PLANE_URL}/internal/workers/{worker_id}",
                    timeout=2.0,
                )

            logger.info(f"Control plane notified: worker {worker_id[:8]} dead")

        except Exception as exc:
            logger.warning(
                f"Could not notify control plane about dead worker: {exc}"
            )

    async def _spawn_one_worker(self, reason="manual"):
        """
        Create one new worker and start its heartbeat loop.

        Layman meaning:
        This creates a new replacement worker.
        """
        current_alive = self._alive_worker_count()

        if current_alive >= MAX_WORKERS:
            logger.warning(
                "Cannot spawn worker because max worker limit reached"
            )
            return None

        worker = WorkerNode(self.registry)
        self._workers.append(worker)

        # Start heartbeat loop in background
        asyncio.create_task(worker.heartbeat_loop())

        logger.warning(
            f"New worker created: {worker.worker_id[:8]} | reason={reason}"
        )

        return worker

    async def _replace_worker_if_needed(self, dead_worker_id, reason="worker_failure"):
        """
        Create only ONE replacement for each dead worker.

        Correct behavior:
        Start: 2 alive
        Kill 1 worker
        Result: 1 dead + 2 alive

        Wrong behavior we are avoiding:
        Kill 1 worker
        Result: 1 dead + 4 alive + 6 alive + 8 alive...
        """

        # If this dead worker was already replaced, do not replace again.
        if dead_worker_id in self.replaced_dead_workers:
            logger.warning(
                f"Replacement already created for dead worker "
                f"{dead_worker_id[:8]}; skipping duplicate."
            )
            return

        alive = self._alive_worker_count()

        # If enough alive workers already exist, do not create more.
        if alive >= self.desired_workers:
            logger.info(
                f"No replacement needed. alive={alive}, "
                f"desired={self.desired_workers}"
            )

            # Mark this dead worker as handled so it does not trigger later.
            self.replaced_dead_workers.add(dead_worker_id)
            return

        missing = self.desired_workers - alive

        logger.warning(
            f"Worker replica needed. dead_worker={dead_worker_id[:8]}, "
            f"alive={alive}, desired={self.desired_workers}, missing={missing}"
        )

        # Mark as handled BEFORE spawning so duplicate monitor calls
        # cannot create multiple replacements.
        self.replaced_dead_workers.add(dead_worker_id)

        for _ in range(missing):
            await self._spawn_one_worker(reason=reason)

    async def _handle_worker_failure(self, dead_worker_id, reason="worker_failure"):
        """
        Called whenever a worker fails.

        Layman meaning:
        Worker died, so scheduler checks whether it needs to create a replacement.
        """
        logger.warning(
            f"Handling worker failure for {dead_worker_id[:8]} | reason={reason}"
        )

        await self._replace_worker_if_needed(dead_worker_id, reason=reason)

    def _setup_routes(self):

        @self.app.get("/health")
        async def health():
            q = get_queue()
            stats = await q.stats()
            alive = self._alive_worker_count()

            return {
                "status": "ok",
                "queue": stats,
                "workers_total": len(self.registry.workers),
                "workers_alive": alive,
                "workers_dead": len(self.registry.workers) - alive,
                "desired_workers": self.desired_workers,
                "max_workers": MAX_WORKERS,
            }

        @self.app.get("/workers")
        async def list_workers():
            return {
                "count": len(self.registry.workers),
                "alive": self._alive_worker_count(),
                "desired_workers": self.desired_workers,
                "workers": [
                    {
                        "worker_id": wid,
                        "status": info["status"],
                        "load": info["load"],
                    }
                    for wid, info in self.registry.workers.items()
                ],
            }

        @self.app.post("/jobs/enqueue")
        async def enqueue_job(req: JobRequest):
            q = get_queue()

            job_id = await q.enqueue(
                container_id=req.container_id,
                image_id=req.image_id,
                image_name=req.image_name,
            )

            logger.info(f"Job received: {job_id[:8]} | image={req.image_name}")

            stats = await q.stats()
            asyncio.create_task(self._notify_queue_depth())

            return {
                "status": "queued",
                "job_id": job_id,
                "queue_depth": stats["pending"],
                "backend": stats["backend"],
            }

        @self.app.post("/workers/scale")
        async def scale_workers(
            count: int = Query(
                ...,
                ge=1,
                le=MAX_WORKERS,
                description="Number of NEW workers to spawn",
            )
        ):
            """
            Manually spawn extra workers.

            Demo command:
            curl -X POST "http://localhost:9010/workers/scale?count=1"
            """
            current_alive = self._alive_worker_count()
            available_slots = MAX_WORKERS - current_alive

            if available_slots <= 0:
                raise HTTPException(
                    status_code=400,
                    detail=f"Already at max workers ({MAX_WORKERS}).",
                )

            to_spawn = min(count, available_slots)
            spawned = []

            for _ in range(to_spawn):
                worker = await self._spawn_one_worker(reason="manual_scale")
                if worker:
                    spawned.append(worker.worker_id[:8])

            logger.info(
                f"Scale: spawned {len(spawned)} workers | "
                f"total_alive={self._alive_worker_count()}"
            )

            return {
                "status": "scaled",
                "spawned": len(spawned),
                "requested": count,
                "worker_ids": spawned,
                "total_alive": self._alive_worker_count(),
                "desired_workers": self.desired_workers,
                "max_workers": MAX_WORKERS,
            }

        @self.app.delete("/workers/{worker_id}")
        async def deregister_worker(worker_id: str):
            """
            Manually kill a worker for chaos demo.

            New behavior:
            - Mark selected worker dead.
            - Reclaim unfinished jobs.
            - Automatically create only ONE replacement worker if needed.
            """
            if worker_id not in self.registry.workers:
                raise HTTPException(
                    status_code=404,
                    detail=f"Worker {worker_id} not found",
                )

            info = self.registry.workers[worker_id]

            # If worker is already dead, do not repeatedly replace it.
            if info["status"] == "dead":
                await self._replace_worker_if_needed(
                    worker_id,
                    reason="duplicate_kill_request",
                )

                return {
                    "status": "already_dead",
                    "dead_worker_id": worker_id,
                    "alive_workers": self._alive_worker_count(),
                    "desired_workers": self.desired_workers,
                    "message": "Worker was already dead; no duplicate replacement created.",
                }

            # Mark worker dead
            self.registry.mark_dead(worker_id)

            logger.warning(f"Worker {worker_id[:8]} manually killed via API")

            # Tell dashboard that old worker died
            await self._notify_worker_dead_to_control_plane(worker_id)

            # Reclaim unfinished jobs from this worker
            if self.monitor:
                await self.monitor._reclaim_jobs(worker_id)

            # Automatically create replacement if alive workers dropped below desired count
            await self._handle_worker_failure(
                worker_id,
                reason="manual_chaos_test",
            )

            return {
                "status": "deregistered_and_replaced",
                "dead_worker_id": worker_id,
                "alive_workers": self._alive_worker_count(),
                "desired_workers": self.desired_workers,
            }

    async def _spawn_initial_workers(self, count: int):
        """
        Create starting workers when scheduler starts.
        """
        for _ in range(count):
            worker = await self._spawn_one_worker(reason="initial_startup")
            if worker:
                logger.info(f"Initial worker: {worker.worker_id[:8]}")

    async def start(self, initial_workers: int = 2):
        """
        Start scheduler service.
        """
        self.desired_workers = initial_workers

        logger.info("Scheduler starting — initializing queue...")

        # Try Redis, fall back to in-memory queue
        self.queue = await create_queue()

        # Heartbeat monitor now has callback for automatic worker replacement
        self.monitor = HeartbeatMonitor(
            self.registry,
            self.queue,
            on_worker_failed=self._handle_worker_failure,
        )

        self.dispatcher = Dispatcher(self.queue, self.registry)

        asyncio.create_task(self.monitor.monitor())
        asyncio.create_task(self.dispatcher.dispatch_loop())

        logger.info("Heartbeat monitor and dispatcher running.")

        await self._spawn_initial_workers(initial_workers)

        logger.info(
            f"Scheduler ready — desired_workers={self.desired_workers} | "
            f"scale with: curl -X POST 'http://localhost:9010/workers/scale?count=N'"
        )

        config = uvicorn.Config(
            self.app,
            host="0.0.0.0",
            port=9010,
            log_level="warning",
        )

        server = uvicorn.Server(config)
        await server.serve()