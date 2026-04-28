import asyncio
from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import httpx
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from control_plane.core.docker_listener import DockerEventListener
from control_plane.core.resilience import ResilienceEngine
from control_plane.core.state_store import StateStore
from control_plane.dashboard.ui import DASHBOARD_HTML
from control_plane.dashboard.ws_manager import WebSocketManager
from shared.utils.logger import get_logger

logger = get_logger("control_plane.main")

state_store = StateStore()
ws_manager = WebSocketManager()
resilience_engine = ResilienceEngine(state_store, ws_manager)
docker_listener = DockerEventListener(state_store, resilience_engine, ws_manager)

SCHEDULER_URL = "http://localhost:9010"


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Control Plane master node...")

    # IMPORTANT FIX:
    # Remove old worker records every time Control Plane starts.
    # This prevents dashboard from showing old ghost workers and increasing
    # from 2 workers to 4, 8, 10, etc.
    cleared = state_store.clear_all_workers()
    logger.info(f"StateStore: cleared {cleared} stale workers from previous session.")

    listener_task = asyncio.create_task(docker_listener.listen())
    poller_task = asyncio.create_task(_poll_scheduler_queue_depth())

    yield

    logger.info("Shutting down Control Plane...")
    listener_task.cancel()
    poller_task.cancel()


async def _poll_scheduler_queue_depth():
    """
    Poll scheduler /health every 2 seconds.

    Layman meaning:
    The scheduler owns the job queue, so the dashboard asks the scheduler
    how many jobs are waiting or running.
    """
    async with httpx.AsyncClient() as client:
        while True:
            try:
                resp = await client.get(f"{SCHEDULER_URL}/health", timeout=2.0)

                if resp.status_code == 200:
                    data = resp.json()
                    queue = data.get("queue", {})

                    if isinstance(queue, dict):
                        depth = queue.get("pending", 0) + queue.get("inflight", 0)
                    else:
                        depth = data.get("queue_depth", 0)

                    state_store.set_queue_depth(depth)

                    await ws_manager.broadcast({
                        "event_type": "queue_depth_update",
                        "queue_depth": depth,
                    })

            except Exception:
                pass

            await asyncio.sleep(2)


app = FastAPI(
    title="Resilient Container Security Engine",
    version="0.1.0",
    lifespan=lifespan,
)


# ── Public endpoints ───────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "node": "master",
    }


@app.get("/status")
async def status():
    """
    Dashboard uses this endpoint.

    Returns:
    - containers
    - workers
    - scan queue depth
    """
    queue_depth = state_store.queue_depth()

    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{SCHEDULER_URL}/health", timeout=1.0)

            if r.status_code == 200:
                data = r.json()
                queue = data.get("queue", {})

                if isinstance(queue, dict):
                    queue_depth = queue.get("pending", 0) + queue.get("inflight", 0)
                else:
                    queue_depth = data.get("queue_depth", 0)

                state_store.set_queue_depth(queue_depth)

    except Exception:
        pass

    return {
        "containers": state_store.get_all_containers(),
        "workers": state_store.get_all_workers(),
        "scan_queue_depth": queue_depth,
    }


@app.get("/containers")
async def list_containers():
    return state_store.get_all_containers()


@app.post("/containers/{container_id}/critical")
async def mark_critical(container_id: str):
    """
    Mark a container as critical.

    Layman meaning:
    If this container dies, the system should create a replacement container.
    """
    state_store.mark_critical(container_id)

    await ws_manager.broadcast({
        "event_type": "container_critical",
        "container_id": container_id,
    })

    return {
        "container_id": container_id,
        "is_critical": True,
    }


@app.get("/audit-log")
async def audit_log():
    return state_store.get_audit_log()


# ── IPC endpoints called by Scheduler ──────────────────────────────────────────

class WorkerHeartbeat(BaseModel):
    worker_id:        str
    status:           str = "alive"
    load:             int = 0
    jobs_completed:   int = 0
    jobs_assigned:    int = 0
    events_assigned:  int = 0
    events_completed: int = 0


@app.post("/internal/workers/heartbeat")
async def worker_heartbeat(data: WorkerHeartbeat):
    """
    Scheduler workers send heartbeat here.

    Layman meaning:
    Worker says: "I am alive."
    Dashboard updates green alive status.
    """
    state_store.upsert_worker(data.worker_id, {
        "worker_id":        data.worker_id,
        "status":           data.status,
        "load":             data.load,
        "jobs_completed":   data.jobs_completed,
        "jobs_assigned":    data.jobs_assigned,
        "events_assigned":  data.events_assigned,
        "events_completed": data.events_completed,
    })

    await ws_manager.broadcast({
        "event_type":       "worker_update",
        "worker_id":        data.worker_id,
        "status":           data.status,
        "load":             data.load,
        "jobs_completed":   data.jobs_completed,
        "jobs_assigned":    data.jobs_assigned,
        "events_assigned":  data.events_assigned,
        "events_completed": data.events_completed,
    })

    return {
        "status": "ok",
        "worker_id": data.worker_id,
    }


@app.delete("/internal/workers/{worker_id}")
async def worker_dead(worker_id: str):
    """
    Scheduler calls this when a worker dies.

    Important:
    We do NOT delete the dead worker here.
    We mark it dead so professor can see red dead worker card.
    """
    state_store.mark_worker_dead(worker_id)

    await ws_manager.broadcast({
        "event_type": "worker_dead",
        "worker_id": worker_id,
        "status": "dead",
    })

    logger.warning(f"Worker {worker_id} marked dead via IPC")

    return {
        "status": "ok",
        "worker_id": worker_id,
    }


@app.post("/internal/scan/complete")
async def scan_complete(data: Dict[str, Any]):
    """
    Dispatcher calls this after each scan job completes.

    Layman meaning:
    Worker finished scanning a container.
    Dashboard receives vulnerability results.
    """
    container_id = data.get("container_id")
    vulns = data.get("vulnerabilities", {})
    status = data.get("status", "unknown")

    if container_id:
        state_store.upsert_container(container_id, {
            "vulnerabilities": vulns,
            "scan_status": status,
        })

    await ws_manager.broadcast({
        "event_type": "scan_complete",
        "job_id": data.get("job_id"),
        "worker_id": data.get("worker_id"),
        "image_name": data.get("image_name"),
        "elapsed_ms": data.get("elapsed_ms"),
        "container_id": container_id,
        "vulnerabilities": vulns,
        "timestamp": data.get("timestamp"),
    })

    return {
        "status": "ok",
    }


@app.post("/internal/queue/depth")
async def update_queue_depth(data: Dict[str, Any]):
    """
    Scheduler tells dashboard queue depth.

    Layman meaning:
    How many scan jobs are waiting or running.
    """
    depth = data.get("depth", 0)

    state_store.set_queue_depth(depth)

    await ws_manager.broadcast({
        "event_type": "queue_depth_update",
        "queue_depth": depth,
    })

    return {
        "status": "ok",
        "depth": depth,
    }


# ── WebSocket + Dashboard ──────────────────────────────────────────────────────

@app.websocket("/ws/dashboard")
async def dashboard_ws(websocket: WebSocket):
    await ws_manager.connect(websocket)

    try:
        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


@app.get("/", response_class=HTMLResponse)
async def dashboard_ui():
    return DASHBOARD_HTML