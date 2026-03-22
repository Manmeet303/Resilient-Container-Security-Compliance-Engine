import asyncio

from scheduler.scheduler_service import SchedulerService
from scheduler.workers.worker_node import WorkerNode


async def main():
    print("Starting Scheduler")

    scheduler = SchedulerService()

    # WorkerNode registers itself in the registry AND runs heartbeat_loop
    # so HeartbeatMonitor never marks them dead
    worker1 = WorkerNode(scheduler.registry)
    worker2 = WorkerNode(scheduler.registry)

    asyncio.create_task(worker1.heartbeat_loop())
    asyncio.create_task(worker2.heartbeat_loop())

    # Simulate two test jobs on startup (remove in production)
    await scheduler.queue.enqueue("container1", "img1", "nginx")
    await scheduler.queue.enqueue("container2", "img2", "redis")

    await scheduler.start()


asyncio.run(main())
