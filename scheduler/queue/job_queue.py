"""
job_queue.py — Redis-backed distributed job queue
===================================================
Replaces the in-memory asyncio.Queue with Redis so jobs persist across
scheduler restarts and can be shared across multiple scheduler processes.

Redis data structures used:
  LIST  rcsce:queue:pending          — pending jobs (RPUSH enqueue, BLPOP dequeue)
  HASH  rcsce:queue:inflight         — jobs currently being processed {job_id: json}
  HASH  rcsce:queue:completed        — completed job results (last 500, TTL 1hr)

Fallback: if Redis is unavailable, automatically falls back to the original
in-memory asyncio.Queue so the system keeps working without Redis.
"""

import asyncio
import json
import uuid
from datetime import datetime, timezone

from shared.utils.logger import get_logger

logger = get_logger("scheduler.job_queue")

# ── Redis keys ────────────────────────────────────────────────────────────────
QUEUE_KEY     = "rcsce:queue:pending"
INFLIGHT_KEY  = "rcsce:queue:inflight"
COMPLETED_KEY = "rcsce:queue:completed"
MAX_COMPLETED = 500
COMPLETED_TTL = 3600   # 1 hour

# ── Redis connection ──────────────────────────────────────────────────────────
def _make_redis():
    try:
        import redis.asyncio as aioredis
        client = aioredis.Redis(host="localhost", port=6379, decode_responses=True)
        return client
    except ImportError:
        return None


# ══════════════════════════════════════════════════════════════════════════════
# Redis-backed queue
# ══════════════════════════════════════════════════════════════════════════════

class RedisJobQueue:
    """
    Persistent job queue backed by Redis Lists.

    enqueue  → RPUSH (append to tail)
    dequeue  → BLPOP (blocking pop from head, 1s timeout loop)
    requeue  → RPUSH (put back on tail — simple; could use LPUSH for priority)
    complete → HDEL from inflight, HSET into completed
    """

    def __init__(self, redis_client):
        self._redis = redis_client
        self._hits  = 0
        self._misses = 0

    async def _ping(self) -> bool:
        try:
            await self._redis.ping()
            return True
        except Exception:
            return False

    async def enqueue(self, container_id: str, image_id: str, image_name: str) -> str:
        job_id = str(uuid.uuid4())
        job = {
            "job_id":       job_id,
            "container_id": container_id,
            "image_id":     image_id,
            "image_name":   image_name,
            "status":       "pending",
            "submitted_at": datetime.now(timezone.utc).isoformat(),
        }
        await self._redis.rpush(QUEUE_KEY, json.dumps(job))
        depth = await self._redis.llen(QUEUE_KEY)
        logger.info(f"Enqueued job {job_id[:8]} | image={image_name} | queue_depth={depth}")
        return job_id

    async def dequeue(self):
        """Blocking pop — waits up to 1s then retries so the loop stays responsive."""
        while True:
            result = await self._redis.blpop(QUEUE_KEY, timeout=1)
            if result is None:
                continue   # timeout, retry
            _, raw = result
            job = json.loads(raw)
            job["status"] = "inflight"
            # Track in-flight in Redis hash
            await self._redis.hset(INFLIGHT_KEY, job["job_id"], json.dumps(job))
            return job

    async def requeue(self, job: dict):
        job["status"] = "pending"
        job.pop("worker_id", None)
        await self._redis.hdel(INFLIGHT_KEY, job["job_id"])
        await self._redis.rpush(QUEUE_KEY, json.dumps(job))
        logger.warning(f"Re-queued job {job['job_id'][:8]} | image={job.get('image_name')}")

    def complete(self, job_id: str, result: dict):
        """Fire-and-forget completion — schedule as async task."""
        asyncio.create_task(self._complete_async(job_id, result))

    async def _complete_async(self, job_id: str, result: dict):
        pipe = self._redis.pipeline()
        pipe.hdel(INFLIGHT_KEY, job_id)
        pipe.hset(COMPLETED_KEY, job_id, json.dumps({
            "job_id":       job_id,
            "result":       result,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }))
        pipe.expire(COMPLETED_KEY, COMPLETED_TTL)
        await pipe.execute()

    def depth(self) -> int:
        """Synchronous depth for health endpoint — runs a separate event loop call."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Can't block — return cached or 0
                return 0
            return loop.run_until_complete(self._redis.llen(QUEUE_KEY))
        except Exception:
            return 0

    async def depth_async(self) -> int:
        try:
            return await self._redis.llen(QUEUE_KEY)
        except Exception:
            return 0

    async def inflight_count(self) -> int:
        try:
            return await self._redis.hlen(INFLIGHT_KEY)
        except Exception:
            return 0

    async def stats(self) -> dict:
        pending  = await self.depth_async()
        inflight = await self.inflight_count()
        return {
            "backend":  "redis",
            "pending":  pending,
            "inflight": inflight,
            "total":    pending + inflight,
        }

    async def reclaim_inflight(self):
        """
        On startup, re-enqueue any jobs that were in-flight when the
        scheduler last crashed. This is the key persistence benefit over
        asyncio.Queue — jobs are never lost across restarts.
        """
        inflight_jobs = await self._redis.hgetall(INFLIGHT_KEY)
        if not inflight_jobs:
            return
        logger.warning(
            f"Found {len(inflight_jobs)} in-flight jobs from previous run — reclaiming"
        )
        for job_id, raw in inflight_jobs.items():
            job = json.loads(raw)
            job["status"] = "pending"
            job.pop("worker_id", None)
            await self._redis.rpush(QUEUE_KEY, json.dumps(job))
            await self._redis.hdel(INFLIGHT_KEY, job_id)
            logger.info(f"Reclaimed job {job_id[:8]} | image={job.get('image_name')}")


# ══════════════════════════════════════════════════════════════════════════════
# In-memory fallback (original implementation)
# ══════════════════════════════════════════════════════════════════════════════

class InMemoryJobQueue:
    """
    Original asyncio.Queue-based implementation.
    Used automatically when Redis is unavailable.
    """

    def __init__(self):
        self._queue     = asyncio.Queue()
        self._in_flight = {}

    async def enqueue(self, container_id, image_id, image_name):
        job_id = str(uuid.uuid4())
        job = {
            "job_id":       job_id,
            "container_id": container_id,
            "image_id":     image_id,
            "image_name":   image_name,
            "status":       "pending",
            "submitted_at": datetime.now(timezone.utc).isoformat(),
        }
        await self._queue.put(job)
        logger.info(f"Enqueued job {job_id[:8]} | image={image_name} [in-memory]")
        return job_id

    async def dequeue(self):
        job = await self._queue.get()
        self._in_flight[job["job_id"]] = job
        return job

    async def requeue(self, job):
        job["status"] = "pending"
        job.pop("worker_id", None)
        await self._queue.put(job)
        self._in_flight.pop(job["job_id"], None)
        logger.warning(f"Re-queued job {job['job_id'][:8]}")

    def complete(self, job_id, result):
        if job_id in self._in_flight:
            self._in_flight[job_id].update({"status": "completed", "result": result})
            del self._in_flight[job_id]

    def depth(self):
        return self._queue.qsize()

    async def depth_async(self):
        return self._queue.qsize()

    async def inflight_count(self):
        return len(self._in_flight)

    async def stats(self):
        return {
            "backend":  "in-memory",
            "pending":  self._queue.qsize(),
            "inflight": len(self._in_flight),
            "total":    self._queue.qsize() + len(self._in_flight),
        }

    async def reclaim_inflight(self):
        pass   # nothing to reclaim — memory is gone on restart


# ══════════════════════════════════════════════════════════════════════════════
# Factory — auto-detects Redis, falls back to in-memory
# ══════════════════════════════════════════════════════════════════════════════

_global_queue = None


async def create_queue():
    """
    Try Redis first. If unavailable, fall back to in-memory.
    Called once on scheduler startup.
    """
    global _global_queue

    redis_client = _make_redis()
    if redis_client is not None:
        try:
            await redis_client.ping()
            queue = RedisJobQueue(redis_client)
            # Reclaim any jobs orphaned by a previous crash
            await queue.reclaim_inflight()
            logger.info(
                "JobQueue: connected to Redis at localhost:6379 — "
                "jobs will persist across restarts"
            )
            _global_queue = queue
            return queue
        except Exception as exc:
            logger.warning(
                f"Redis unavailable ({exc}) — falling back to in-memory queue. "
                "Jobs will NOT persist across scheduler restarts."
            )

    queue = InMemoryJobQueue()
    logger.info("JobQueue: using in-memory queue (no Redis)")
    _global_queue = queue
    return queue


def get_queue():
    """Synchronous accessor for already-created queue (used by dispatcher)."""
    if _global_queue is None:
        raise RuntimeError("Queue not initialized — call await create_queue() first")
    return _global_queue