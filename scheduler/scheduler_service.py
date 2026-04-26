"""
scheduler_service.py — RCSCE Distributed Task Scheduler
=========================================================
Runs on port 9010. Exposes:
  GET  /health             — queue stats, worker count, backend info
  GET  /workers            — list all registered workers with load
  POST /jobs/enqueue       — accept scan job from control plane
  POST /workers/scale      — spawn N additional workers dynamically
  DELETE /workers/{id}     — manually deregister a worker (chaos testing)

Dynamic scaling: POST /workers/scale?count=3 spawns 3 new WorkerNode
instances inside this process, registers them, and starts their heartbeat
loops. They appear in the dashboard within 6 seconds.

Redis queue: jobs persist across scheduler restarts. If Redis is down,
falls back to in-memory queue automatically with a warning.
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
CONTROL_PLANE_URL = "http://localhost:9000"   # hard cap — prevents runaway scaling


class JobRequest(BaseModel):
    container_id: str
    image_id:     str
    image_name:   str


class SchedulerService:

    def __init__(self):
        self.queue      = None
        self.registry   = WorkerRegistry()
        self.monitor    = None
        self.dispatcher = None
        self._workers   = []
        self.app        = FastAPI(title="RCSCE Scheduler — Redis Edition")
        self._setup_routes()

    async def _notify_queue_depth(self):
        """Push current queue depth to control plane after every enqueue/complete."""
        try:
            q     = get_queue()
            stats = await q.stats()
            depth = stats.get("pending", 0) + stats.get("inflight", 0)
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"{CONTROL_PLANE_URL}/internal/queue/depth",
                    json={"depth": depth},
                    timeout=1.0,
                )
        except Exception:
            pass   # control plane not up — silently skip

    def _setup_routes(self):

        @self.app.get("/health")
        async def health():
            q     = get_queue()
            stats = await q.stats()
            alive = sum(1 for w in self.registry.workers.values() if w["status"] == "alive")
            return {
                "status":        "ok",
                "queue":         stats,
                "workers_total": len(self.registry.workers),
                "workers_alive": alive,
                "workers_dead":  len(self.registry.workers) - alive,
                "max_workers":   MAX_WORKERS,
            }

        @self.app.get("/workers")
        async def list_workers():
            return {
                "count": len(self.registry.workers),
                "workers": [
                    {"worker_id": wid, "status": info["status"], "load": info["load"]}
                    for wid, info in self.registry.workers.items()
                ]
            }

        @self.app.post("/jobs/enqueue")
        async def enqueue_job(req: JobRequest):
            q      = get_queue()
            job_id = await q.enqueue(
                container_id=req.container_id,
                image_id=req.image_id,
                image_name=req.image_name,
            )
            logger.info(f"Job received: {job_id[:8]} | image={req.image_name}")
            stats = await q.stats()
            asyncio.create_task(self._notify_queue_depth())
            return {"status": "queued", "job_id": job_id, "queue_depth": stats["pending"], "backend": stats["backend"]}

        @self.app.post("/workers/scale")
        async def scale_workers(
            count: int = Query(..., ge=1, le=MAX_WORKERS,
                               description="Number of NEW workers to spawn")
        ):
            """
            Dynamically spawn additional WorkerNode instances.

            Usage:
                curl -X POST "http://localhost:9010/workers/scale?count=3"

            Each new worker registers immediately in the WorkerRegistry,
            starts its heartbeat loop (appears in dashboard within 6s),
            and begins accepting jobs from the dispatcher within 1 dispatch cycle.
            """
            current_alive   = sum(1 for w in self.registry.workers.values() if w["status"] == "alive")
            available_slots = MAX_WORKERS - current_alive

            if available_slots <= 0:
                raise HTTPException(
                    status_code=400,
                    detail=f"Already at max workers ({MAX_WORKERS}). Scale down first."
                )

            to_spawn = min(count, available_slots)
            spawned  = []

            for _ in range(to_spawn):
                worker = WorkerNode(self.registry)
                self._workers.append(worker)
                asyncio.create_task(worker.heartbeat_loop())
                spawned.append(worker.worker_id[:8])
                logger.info(f"Dynamically spawned worker {worker.worker_id[:8]}")

            logger.info(f"Scale: spawned {to_spawn} workers | total_alive={current_alive + to_spawn}")

            return {
                "status":      "scaled",
                "spawned":     to_spawn,
                "requested":   count,
                "worker_ids":  spawned,
                "total_alive": current_alive + to_spawn,
                "max_workers": MAX_WORKERS,
            }

        @self.app.delete("/workers/{worker_id}")
        async def deregister_worker(worker_id: str):
            """Manually kill a worker — useful for chaos engineering demos."""
            if worker_id not in self.registry.workers:
                raise HTTPException(status_code=404, detail=f"Worker {worker_id} not found")
            self.registry.mark_dead(worker_id)
            logger.warning(f"Worker {worker_id[:8]} manually deregistered via API")
            return {"status": "deregistered", "worker_id": worker_id}

    async def _spawn_initial_workers(self, count: int):
        for _ in range(count):
            worker = WorkerNode(self.registry)
            self._workers.append(worker)
            asyncio.create_task(worker.heartbeat_loop())
            logger.info(f"Initial worker: {worker.worker_id[:8]}")

    async def start(self, initial_workers: int = 2):
        logger.info("Scheduler starting — initializing queue...")

        # Try Redis, fall back to in-memory
        self.queue = await create_queue()

        # Wire monitor and dispatcher now that queue is ready
        self.monitor    = HeartbeatMonitor(self.registry, self.queue)
        self.dispatcher = Dispatcher(self.queue, self.registry)

        asyncio.create_task(self.monitor.monitor())
        asyncio.create_task(self.dispatcher.dispatch_loop())
        logger.info("Heartbeat monitor and dispatcher running.")

        await self._spawn_initial_workers(initial_workers)
        logger.info(
            f"Scheduler ready — {initial_workers} workers active | "
            f"scale with: curl -X POST 'http://localhost:9010/workers/scale?count=N'"
        )

        config = uvicorn.Config(self.app, host="0.0.0.0", port=9010, log_level="warning")
        server = uvicorn.Server(config)
        await server.serve()
