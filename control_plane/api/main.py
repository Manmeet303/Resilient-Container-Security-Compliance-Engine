import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from control_plane.core.docker_listener import DockerEventListener
from control_plane.core.state_store import StateStore
from control_plane.core.resilience import ResilienceEngine
from control_plane.dashboard.ws_manager import WebSocketManager
from control_plane.dashboard.ui import DASHBOARD_HTML
from shared.utils.logger import get_logger

logger = get_logger("control_plane.main")
state_store = StateStore()
ws_manager = WebSocketManager()
resilience_engine = ResilienceEngine(state_store, ws_manager)
docker_listener = DockerEventListener(state_store, resilience_engine, ws_manager)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Control Plane master node...")
    asyncio.create_task(docker_listener.listen())
    yield
    logger.info("Shutting down Control Plane...")

app = FastAPI(title="Resilient Container Security Engine", version="0.1.0", lifespan=lifespan)

@app.get("/health")
async def health():
    return {"status": "ok", "node": "master"}

@app.get("/status")
async def status():
    return {"containers": state_store.get_all_containers(),
            "workers": state_store.get_all_workers(),
            "scan_queue_depth": state_store.queue_depth()}

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
