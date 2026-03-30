"""
Standby Master Node — Active-Passive Failover
=============================================
Run on port 8080:
    uvicorn control_plane.api.standby:app --port 8080 --reload

Behaviour:
- Starts in STANDBY mode — read-only, no Docker listener
- Every 2s pings primary /health (port 8000)
- Every 5s mirrors full state from primary /status + /audit-log
- After 3 consecutive health failures → promotes itself to PRIMARY
- Once promoted: starts Docker listener, accepts all write requests,
  broadcasts promotion event to dashboard WebSocket clients
"""

import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime

import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from control_plane.core.docker_listener import DockerEventListener
from control_plane.core.resilience import ResilienceEngine
from control_plane.core.state_store import StateStore
from control_plane.dashboard.ui import DASHBOARD_HTML
from control_plane.dashboard.ws_manager import WebSocketManager
from shared.utils.logger import get_logger

logger = get_logger("control_plane.standby")

# ── Config ────────────────────────────────────────────────────────────────────
PRIMARY_URL           = "http://localhost:8000"
HEALTH_CHECK_INTERVAL = 2    # seconds between health pings
STATE_SYNC_INTERVAL   = 5    # seconds between full state mirrors
FAILURE_THRESHOLD     = 3    # consecutive failures before promoting

# ── Shared state ──────────────────────────────────────────────────────────────
state_store       = StateStore()
ws_manager        = WebSocketManager()
resilience_engine = ResilienceEngine(state_store, ws_manager)
docker_listener   = DockerEventListener(state_store, resilience_engine, ws_manager)

is_primary    = False
failure_count = 0
promoted_at   = None


# ── Promotion ─────────────────────────────────────────────────────────────────

async def promote_to_primary():
    """Standby takes over — starts Docker listener, accepts writes."""
    global is_primary, promoted_at

    if is_primary:
        return   # already promoted, don't run twice

    is_primary   = True
    promoted_at  = datetime.utcnow().isoformat()

    logger.info("=" * 60)
    logger.info("STANDBY PROMOTED TO PRIMARY — primary node is down!")
    logger.info(f"Promotion time: {promoted_at}")
    logger.info("Docker listener starting on standby node...")
    logger.info("=" * 60)

    # Start Docker listener so this node now processes container events
    asyncio.create_task(docker_listener.listen())

    # Notify all dashboard WebSocket clients — includes redirect URL
    # so the dashboard auto-redirects to port 8080 after promotion
    await ws_manager.broadcast({
        "event_type":  "standby_promoted",
        "message":     "Standby master promoted to primary — taking over!",
        "redirect_url": "http://localhost:8080",
        "promoted_at": promoted_at,
        "timestamp":   promoted_at,
    })


# ── Health check loop ─────────────────────────────────────────────────────────

async def health_check_loop():
    """Ping primary /health every 2 s. On 3 consecutive failures → promote."""
    global failure_count

    async with httpx.AsyncClient() as client:
        while True:
            if is_primary:
                await asyncio.sleep(HEALTH_CHECK_INTERVAL)
                continue   # already primary, no need to ping

            try:
                resp = await client.get(
                    f"{PRIMARY_URL}/health", timeout=2.0
                )
                if resp.status_code == 200:
                    failure_count = 0
                    logger.info("Standby: primary healthy ✓")
                else:
                    raise ValueError(f"Unexpected status {resp.status_code}")

            except Exception as exc:
                failure_count += 1
                logger.warning(
                    f"Standby: primary unreachable "
                    f"({failure_count}/{FAILURE_THRESHOLD}) — {exc}"
                )
                if failure_count >= FAILURE_THRESHOLD:
                    await promote_to_primary()

            await asyncio.sleep(HEALTH_CHECK_INTERVAL)


# ── State mirror loop ─────────────────────────────────────────────────────────

async def state_mirror_loop():
    """
    Every 5 s pull /status and /audit-log from primary and mirror
    into local state_store so standby always has current state.
    If primary is gone and we're now primary, stop mirroring.
    """
    async with httpx.AsyncClient() as client:
        while True:
            if is_primary:
                await asyncio.sleep(STATE_SYNC_INTERVAL)
                continue   # we ARE the primary now

            try:
                # Mirror containers + workers + queue depth
                resp = await client.get(
                    f"{PRIMARY_URL}/status", timeout=3.0
                )
                data = resp.json()

                for container in data.get("containers", []):
                    cid = container.get("container_id")
                    if cid:
                        state_store.upsert_container(cid, container)

                for worker in data.get("workers", []):
                    wid = worker.get("worker_id", "unknown")
                    state_store.upsert_worker(wid, worker)

                state_store.set_queue_depth(
                    data.get("scan_queue_depth", 0)
                )

                # Mirror audit log — skip malformed non-dict entries
                audit_resp = await client.get(
                    f"{PRIMARY_URL}/audit-log", timeout=3.0
                )
                existing_ids = {
                    e.get("event_id")
                    for e in state_store.get_audit_log()
                    if isinstance(e, dict) and e.get("event_id")
                }
                for entry in audit_resp.json():
                    if not isinstance(entry, dict):
                        continue
                    if entry.get("event_id") not in existing_ids:
                        state_store.append_audit(entry)

                logger.info(
                    f"Standby: mirrored state — "
                    f"{len(data.get('containers', []))} containers, "
                    f"{len(data.get('workers', []))} workers"
                )

            except Exception as exc:
                logger.warning(f"Standby: state mirror failed — {exc}")

            await asyncio.sleep(STATE_SYNC_INTERVAL)


# ── FastAPI lifespan ──────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Standby master node starting on port 8080...")
    logger.info(f"Watching primary at {PRIMARY_URL}")
    logger.info(f"Will promote after {FAILURE_THRESHOLD} consecutive failures")
    asyncio.create_task(health_check_loop())
    asyncio.create_task(state_mirror_loop())
    yield
    logger.info("Standby master shutting down...")


# ── FastAPI app ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="RCSCE — Standby Master Node",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    return {
        "status":      "ok",
        "node":        "primary-promoted" if is_primary else "standby",
        "is_primary":  is_primary,
        "failure_count": failure_count,
        "promoted_at": promoted_at,
        "primary_url": PRIMARY_URL,
    }


@app.get("/status")
async def status():
    return {
        "containers":      state_store.get_all_containers(),
        "workers":         state_store.get_all_workers(),
        "scan_queue_depth": state_store.queue_depth(),
        "node_role":       "primary" if is_primary else "standby",
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