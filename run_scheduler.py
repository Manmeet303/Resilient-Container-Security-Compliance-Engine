"""
run_scheduler.py — Entry point for the RCSCE Distributed Task Scheduler

Startup:
    python run_scheduler.py              # starts with 2 workers (default)
    python run_scheduler.py --workers 5  # starts with 5 workers

Dynamic scaling after startup:
    curl -X POST "http://localhost:9010/workers/scale?count=3"   # add 3 more
    curl http://localhost:9010/workers                            # list all

Redis queue (if Redis is running):
    redis-server &   # Mac/Linux — start Redis first
    Jobs will persist across scheduler restarts.
    Falls back to in-memory queue automatically if Redis is unavailable.
"""

import asyncio
import argparse

from scheduler.scheduler_service import SchedulerService


async def main(initial_workers: int):
    print(f"\n{'='*60}")
    print(f"  RCSCE Scheduler — Redis Edition")
    print(f"  Starting with {initial_workers} workers (max 20)")
    print(f"  Scale: curl -X POST 'http://localhost:9010/workers/scale?count=N'")
    print(f"{'='*60}\n")

    scheduler = SchedulerService()
    await scheduler.start(initial_workers=initial_workers)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RCSCE Scheduler")
    parser.add_argument(
        "--workers", type=int, default=2,
        help="Number of initial workers to spawn (default: 2, max: 20)"
    )
    args = parser.parse_args()
    asyncio.run(main(initial_workers=args.workers))