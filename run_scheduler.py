import asyncio

from scheduler.scheduler_service import SchedulerService
from scheduler.workers.worker_node import WorkerNode
from control_plane.core.state_store import StateStore


async def sync_workers_to_dashboard(scheduler, state_store):
    while True:
        for worker_id, info in scheduler.registry.workers.items():
            state_store.upsert_worker(
                worker_id,
                {
                    "worker_id": worker_id,
                    "status": info.get("status", "unknown"),
                    "load": info.get("load", 0),
                },
            )
        state_store.set_queue_depth(scheduler.queue.depth())
        await asyncio.sleep(1)


async def fail_worker_later(worker, delay=4):
    await asyncio.sleep(delay)
    print(f"Simulating failure of worker: {worker.worker_id}")
    worker.fail()


async def main():
    print("Starting Scheduler")

    scheduler = SchedulerService()
    state_store = StateStore()

    # Clear old worker state for clean demo
    state_store.upsert_worker("worker-1", {"worker_id": "worker-1", "status": "alive", "load": 0})
    state_store.upsert_worker("worker-2", {"worker_id": "worker-2", "status": "alive", "load": 0})

    worker1 = WorkerNode(scheduler.registry, name="worker-1")
    worker2 = WorkerNode(scheduler.registry, name="worker-2")

    asyncio.create_task(worker1.heartbeat_loop())
    asyncio.create_task(worker2.heartbeat_loop())
    asyncio.create_task(sync_workers_to_dashboard(scheduler, state_store))

    # One demo job only, so it is easy to explain
    await scheduler.queue.enqueue("demo-container", "demo-image", "nginx")

    # Kill worker-1 while it is processing
    asyncio.create_task(fail_worker_later(worker1, delay=4))

    await scheduler.start()


asyncio.run(main())