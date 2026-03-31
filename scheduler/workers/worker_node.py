import asyncio
import uuid
from datetime import datetime

import httpx

from shared.utils.logger import get_logger

logger = get_logger("scheduler.worker")

CONTROL_PLANE_URL = "http://localhost:8000"


class WorkerNode:

    def __init__(self, registry):
        self.registry       = registry
        self.worker_id      = str(uuid.uuid4())
        self.jobs_completed = 0
        self.registry.register(self.worker_id, self)
        logger.info(f"WorkerNode created: {self.worker_id[:8]}...")

    async def heartbeat_loop(self):
        """
        1. Ping local WorkerRegistry every 2s — keeps HeartbeatMonitor happy
        2. POST worker status to control plane every 6s — updates dashboard
        """
        ipc_counter = 0
        async with httpx.AsyncClient() as client:
            while True:
                self.registry.heartbeat(self.worker_id)
                ipc_counter += 1
                if ipc_counter >= 3:   # 3 × 2s = 6s
                    ipc_counter = 0
                    await self._report_to_control_plane(client)
                await asyncio.sleep(2)

    async def _report_to_control_plane(self, client: httpx.AsyncClient):
        try:
            info = self.registry.workers.get(self.worker_id, {})
            await client.post(
                f"{CONTROL_PLANE_URL}/internal/workers/heartbeat",
                json={
                    "worker_id":      self.worker_id,
                    "status":         info.get("status", "alive"),
                    "load":           info.get("load", 0),
                    "jobs_completed": self.jobs_completed,
                },
                timeout=2.0,
            )
            logger.info(
                f"Worker {self.worker_id[:8]} → control plane "
                f"(load={info.get('load',0)}, done={self.jobs_completed})"
            )
        except Exception as exc:
            logger.warning(f"Worker {self.worker_id[:8]} IPC failed: {exc}")

    async def process_job(self, job):
        logger.info(
            f"Worker {self.worker_id[:8]} processing "
            f"job {job['job_id'][:8]} | image={job.get('image_name','?')}"
        )
        await asyncio.sleep(3)   # simulated Trivy scan
        self.jobs_completed += 1
        return {
            "status":     "scan_complete",
            "worker_id":  self.worker_id,
            "job_id":     job["job_id"],
            "image_name": job.get("image_name", "unknown"),
            "timestamp":  datetime.utcnow().isoformat(),
        }
