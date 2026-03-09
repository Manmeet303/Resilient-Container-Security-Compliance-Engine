import asyncio

from scheduler.scheduler_service import SchedulerService
from scheduler.workers.worker_node import WorkerNode


async def main():

    print("Starting Scheduler Test")

    scheduler = SchedulerService()

    # create workers
    worker1 = WorkerNode(scheduler.registry)
    worker2 = WorkerNode(scheduler.registry)

    asyncio.create_task(worker1.heartbeat_loop())
    asyncio.create_task(worker2.heartbeat_loop())

    # simulate jobs
    await scheduler.queue.enqueue("container1", "img1", "nginx")
    await scheduler.queue.enqueue("container2", "img2", "redis")

    await scheduler.start()


asyncio.run(main())