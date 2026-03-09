import asyncio

from scheduler.queue.job_queue import JobQueue
from scheduler.workers.worker_registry import WorkerRegistry
from scheduler.heartbeat.monitor import HeartbeatMonitor
from scheduler.dispatcher import Dispatcher

from shared.utils.logger import get_logger

logger = get_logger("scheduler.service")


class SchedulerService:

    def __init__(self):

        self.queue = JobQueue()

        self.registry = WorkerRegistry()

        self.monitor = HeartbeatMonitor(self.registry)

        self.dispatcher = Dispatcher(self.queue, self.registry)

    async def start(self):

        logger.info("Scheduler starting")

        asyncio.create_task(self.monitor.monitor())

        asyncio.create_task(self.dispatcher.dispatch_loop())

        while True:

            await asyncio.sleep(10)