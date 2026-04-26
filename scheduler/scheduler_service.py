import asyncio

from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn

from scheduler.queue.job_queue import get_queue
from scheduler.workers.worker_registry import WorkerRegistry
from scheduler.heartbeat.monitor import HeartbeatMonitor
from scheduler.dispatcher import Dispatcher
from shared.utils.logger import get_logger

logger = get_logger("scheduler.service")


class JobRequest(BaseModel):
    container_id: str
    image_id:     str
    image_name:   str


class SchedulerService:

    def __init__(self):
        self.queue      = get_queue()
        self.registry   = WorkerRegistry()
        self.monitor    = HeartbeatMonitor(self.registry, self.queue)
        self.dispatcher = Dispatcher(self.queue, self.registry)

        # FastAPI app so control plane can POST jobs directly
        self.app = FastAPI(title="RCSCE Scheduler")

        @self.app.get("/health")
        async def health():
            return {
                "status":      "ok",
                "queue_depth": self.queue.depth(),
                "workers":     len(self.registry.workers),
            }

        @self.app.post("/jobs/enqueue")
        async def enqueue_job(req: JobRequest):
            """
            Control plane POSTs here when a cache miss happens.
            This runs inside the scheduler process so the job lands
            in the same queue the dispatcher is watching.
            """
            job_id = await self.queue.enqueue(
                container_id=req.container_id,
                image_id=req.image_id,
                image_name=req.image_name,
            )
            logger.info(
                f"Job received from control plane: {job_id[:8]} | "
                f"image={req.image_name}"
            )
            return {"status": "queued", "job_id": job_id}

    async def start(self):
        logger.info("Scheduler starting")
        asyncio.create_task(self.monitor.monitor())
        asyncio.create_task(self.dispatcher.dispatch_loop())
        logger.info("Scheduler heartbeat monitor and dispatcher running.")

        # Run HTTP server on port 9010 alongside the scheduler
        config = uvicorn.Config(
            self.app,
            host="0.0.0.0",
            port=9010,
            log_level="warning",   # suppress uvicorn noise
        )
        server = uvicorn.Server(config)
        await server.serve()