import asyncio

from scheduler.scheduler_service import SchedulerService
from scheduler.workers.worker_node import WorkerNode


async def main():
    print("Starting Scheduler")

    scheduler = SchedulerService()

    # Create 2 WorkerNodes — each registers itself in local registry
    # AND reports to control plane via HTTP so dashboard shows them
    worker1 = WorkerNode(scheduler.registry)
    worker2 = WorkerNode(scheduler.registry)

    # Start heartbeat loops — keeps workers alive in both registry and dashboard
    asyncio.create_task(worker1.heartbeat_loop())
    asyncio.create_task(worker2.heartbeat_loop())

    await scheduler.start()


asyncio.run(main())
