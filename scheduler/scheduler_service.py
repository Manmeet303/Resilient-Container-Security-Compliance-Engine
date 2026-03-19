import asyncio

# ── Use the singleton queue so it is the SAME object docker_listener writes to ──
from scheduler.queue.job_queue import get_queue
from scheduler.workers.worker_registry import WorkerRegistry
from scheduler.heartbeat.monitor import HeartbeatMonitor
from scheduler.dispatcher import Dispatcher

from shared.utils.logger import get_logger

logger = get_logger("scheduler.service")


class SchedulerService:

    def __init__(self):
        # Pull the singleton — same instance docker_listener.enqueue() uses
        self.queue = get_queue()

        self.registry = WorkerRegistry()
        self.monitor = HeartbeatMonitor(self.registry)
        self.dispatcher = Dispatcher(self.queue, self.registry)

    async def _keep_workers_alive(self):
        """Simulate heartbeat for static workers until real worker nodes exist."""
        while True:
            self.registry.heartbeat("worker-1")
            self.registry.heartbeat("worker-2")
            await asyncio.sleep(5)   # must be < HeartbeatMonitor timeout (10s)

    async def start(self):
        logger.info("Scheduler starting")
        self.registry.register("worker-1")
        self.registry.register("worker-2")
        logger.info("Workers registered: worker-1, worker-2")
        asyncio.create_task(self.monitor.monitor())
        asyncio.create_task(self.dispatcher.dispatch_loop())
        asyncio.create_task(self._keep_workers_alive())   # ← add this line
        logger.info("Scheduler heartbeat monitor and dispatcher running.")
        while True:
            await asyncio.sleep(10)