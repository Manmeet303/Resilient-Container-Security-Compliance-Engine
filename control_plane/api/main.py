import asyncio
from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from control_plane.core.docker_listener import DockerEventListener
from control_plane.core.resilience import ResilienceEngine
from control_plane.core.state_store import StateStore
from control_plane.dashboard.ui import DASHBOARD_HTML
from control_plane.dashboard.ws_manager import WebSocketManager
from shared.utils.logger import get_logger

logger = get_logger("control_plane.main")
state_store       = StateStore()
ws_manager        = WebSocketManager()
resilience_engine = ResilienceEngine(state_store, ws_manager)
docker_listener   = DockerEventListener(state_store, resilience_engine, ws_manager)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Control Plane master node...")

    # Clear stale workers from previous run so dashboard doesn't show
    # ghost workers from last session (fixes 4-worker issue on restart)
    for w in state_store.get_all_workers():
        state_store.upsert_worker(w["worker_id"], {
            "worker_id": w["worker_id"],
            "status": "dead",
            "load": 0,
        })
    logger.info("StateStore: cleared stale workers from previous session.")

    listener_task = asyncio.create_task(docker_listener.listen())
    yield
    logger.info("Shutting down Control Plane...")
    listener_task.cancel()

app = FastAPI(
    title="Resilient Container Security Engine",
    version="0.1.0",
    lifespan=lifespan,
)


# ── Public endpoints ───────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "node": "master"}


@app.get("/status")
async def status():
    return {
        "containers":       state_store.get_all_containers(),
        "workers":          state_store.get_all_workers(),
        "scan_queue_depth": state_store.queue_depth(),
    }


@app.get("/containers")
async def list_containers():
    return state_store.get_all_containers()


@app.post("/containers/{container_id}/critical")
async def mark_critical(container_id: str):
    state_store.mark_critical(container_id)
    return {"container_id": container_id, "is_critical": True}


@app.get("/audit-log")
async def audit_log():
    return state_store.get_audit_log()


# ── IPC endpoints — called by scheduler process via HTTP ──────────────────────

class WorkerHeartbeat(BaseModel):
    worker_id:      str
    status:         str = "alive"
    load:           int = 0
    jobs_completed: int = 0


@app.post("/internal/workers/heartbeat")
async def worker_heartbeat(data: WorkerHeartbeat):
    """
    Scheduler process POSTs here every 5s for each live worker.
    Updates state_store so the dashboard Workers panel stays current.
    Broadcasts worker_update event so dashboard updates in real-time
    without waiting for the next 5s poll cycle.
    """
    state_store.upsert_worker(data.worker_id, {
        "worker_id":      data.worker_id,
        "status":         data.status,
        "load":           data.load,
        "jobs_completed": data.jobs_completed,
    })
    await ws_manager.broadcast({
        "event_type": "worker_update",
        "worker_id":  data.worker_id,
        "status":     data.status,
        "load":       data.load,
    })
    return {"status": "ok", "worker_id": data.worker_id}


@app.delete("/internal/workers/{worker_id}")
async def worker_dead(worker_id: str):
    """
    HeartbeatMonitor calls this when a worker fails.
    Updates state_store and broadcasts worker_dead to dashboard.
    """
    state_store.upsert_worker(worker_id, {
        "worker_id": worker_id,
        "status":    "dead",
        "load":      0,
    })
    await ws_manager.broadcast({
        "event_type": "worker_dead",
        "worker_id":  worker_id,
        "status":     "dead",
    })
    logger.warning(f"Worker {worker_id} marked dead via IPC")
    return {"status": "ok", "worker_id": worker_id}


@app.post("/internal/scan/complete")
async def scan_complete(data: Dict[str, Any]):
    """
    Dispatcher calls this after each scan job completes.
    Saves vulnerability counts to state and broadcasts to UI.
    """
    container_id = data.get("container_id")
    vulns = data.get("vulnerabilities", {})
    status = data.get("status", "unknown")

    # 1. Save the vulnerability data to the specific container
    if container_id:
        state_store.upsert_container(container_id, {
            "vulnerabilities": vulns,
            "scan_status": status
        })

    # 2. Broadcast the live event to the dashboard
    await ws_manager.broadcast({
        "event_type":      "scan_complete",
        "job_id":          data.get("job_id"),
        "worker_id":       data.get("worker_id"),
        "image_name":      data.get("image_name"),
        "elapsed_ms":      data.get("elapsed_ms"),
        "container_id":    container_id,
        "vulnerabilities": vulns,
        "timestamp":       data.get("timestamp"),
    })
    return {"status": "ok"}


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