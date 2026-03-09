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

            worker = workers[0]

            logger.info(f"Dispatching job {job['job_id']} to worker {worker}")