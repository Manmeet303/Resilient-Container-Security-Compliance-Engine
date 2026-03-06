#!/bin/bash
# ============================================================
# Resilient Container Security & Compliance Engine
# One-shot project file setup script
# Run this from INSIDE your cloned repo folder:
#   bash setup_project.sh
# ============================================================

set -e
echo "Creating folder structure..."

mkdir -p control_plane/api control_plane/core control_plane/dashboard
mkdir -p scheduler/queue scheduler/workers scheduler/heartbeat
mkdir -p cache/grpc cache/storage cache/eviction
mkdir -p shared/models shared/utils shared/protos
mkdir -p scripts tests/unit tests/integration tests/chaos docs

touch control_plane/__init__.py control_plane/api/__init__.py \
      control_plane/core/__init__.py control_plane/dashboard/__init__.py \
      scheduler/__init__.py scheduler/queue/__init__.py \
      scheduler/workers/__init__.py scheduler/heartbeat/__init__.py \
      cache/__init__.py cache/grpc/__init__.py \
      cache/storage/__init__.py cache/eviction/__init__.py \
      shared/__init__.py shared/models/__init__.py \
      shared/utils/__init__.py shared/protos/__init__.py

echo "Writing shared/utils/logger.py..."
cat > shared/utils/logger.py << 'PYEOF'
import logging, json, sys
from datetime import datetime

class JSONFormatter(logging.Formatter):
    def format(self, record):
        entry = {"timestamp": datetime.utcnow().isoformat(), "level": record.levelname,
                 "module": record.name, "message": record.getMessage()}
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry)

def get_logger(name):
    logger = logging.getLogger(name)
    if not logger.handlers:
        h = logging.StreamHandler(sys.stdout)
        h.setFormatter(JSONFormatter())
        logger.addHandler(h)
        logger.setLevel(logging.INFO)
    return logger
PYEOF

echo "Writing shared/utils/hashing.py..."
cat > shared/utils/hashing.py << 'PYEOF'
import hashlib
from typing import List

def compute_layer_hash(layer_id: str) -> str:
    return hashlib.sha256(layer_id.encode("utf-8")).hexdigest()

def compute_image_hash(layer_ids: List[str]) -> str:
    combined = "|".join(sorted(layer_ids))
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()
PYEOF

echo "Writing shared/models/container_event.py..."
cat > shared/models/container_event.py << 'PYEOF'
from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

class EventType(str, Enum):
    CONTAINER_START = "container_start"
    CONTAINER_DIE = "container_die"
    CONTAINER_STOP = "container_stop"
    CONTAINER_KILL = "container_kill"

class ContainerEvent(BaseModel):
    event_id: str
    event_type: EventType
    container_id: str
    container_name: str
    image_id: str
    image_name: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    is_critical: bool = False
    metadata: Dict[str, Any] = {}

class ScanJob(BaseModel):
    job_id: str
    container_id: str
    image_id: str
    image_name: str
    submitted_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = "pending"
    worker_id: Optional[str] = None
    result: Optional[Dict[str, Any]] = None

class CacheEntry(BaseModel):
    layer_hash: str
    scan_report: Dict[str, Any]
    cached_at: datetime = Field(default_factory=datetime.utcnow)
    hit_count: int = 0
    ttl_seconds: int = 3600

class NodeInfo(BaseModel):
    node_id: str
    role: str
    host: str
    port: int
    last_heartbeat: Optional[datetime] = None
    is_alive: bool = True
    cpu_load: float = 0.0
PYEOF

echo "Writing control_plane/core/state_store.py..."
cat > control_plane/core/state_store.py << 'PYEOF'
from typing import Dict, List, Any, Optional
from datetime import datetime
import threading

class StateStore:
    def __init__(self):
        self._lock = threading.Lock()
        self._containers: Dict[str, Dict[str, Any]] = {}
        self._workers: Dict[str, Dict[str, Any]] = {}
        self._critical_containers: set = set()
        self._audit_log: List[Dict[str, Any]] = []
        self._queue_depth: int = 0

    def upsert_container(self, container_id, data):
        with self._lock:
            self._containers[container_id] = {
                **self._containers.get(container_id, {}), **data,
                "updated_at": datetime.utcnow().isoformat()}

    def remove_container(self, container_id):
        with self._lock:
            self._containers.pop(container_id, None)

    def get_all_containers(self):
        with self._lock:
            return list(self._containers.values())

    def get_container(self, container_id):
        with self._lock:
            return self._containers.get(container_id)

    def mark_critical(self, container_id):
        with self._lock:
            self._critical_containers.add(container_id)
            if container_id in self._containers:
                self._containers[container_id]["is_critical"] = True

    def is_critical(self, container_id):
        with self._lock:
            return container_id in self._critical_containers

    def upsert_worker(self, worker_id, data):
        with self._lock:
            self._workers[worker_id] = {
                **self._workers.get(worker_id, {}), **data,
                "last_seen": datetime.utcnow().isoformat()}

    def get_all_workers(self):
        with self._lock:
            return list(self._workers.values())

    def set_queue_depth(self, depth):
        with self._lock:
            self._queue_depth = depth

    def queue_depth(self):
        with self._lock:
            return self._queue_depth

    def append_audit(self, event):
        with self._lock:
            self._audit_log.append({**event, "logged_at": datetime.utcnow().isoformat()})

    def get_audit_log(self):
        with self._lock:
            return list(self._audit_log[-200:])
PYEOF

echo "Writing control_plane/core/docker_listener.py..."
cat > control_plane/core/docker_listener.py << 'PYEOF'
import asyncio, uuid
from datetime import datetime
import docker
from docker.errors import DockerException
from shared.utils.logger import get_logger

logger = get_logger("control_plane.docker_listener")
WATCHED_EVENTS = {"start", "die", "stop", "kill"}

class DockerEventListener:
    def __init__(self, state_store, resilience_engine, ws_manager):
        self.state_store = state_store
        self.resilience_engine = resilience_engine
        self.ws_manager = ws_manager
        try:
            self.client = docker.from_env()
            logger.info("Connected to Docker daemon via /var/run/docker.sock")
        except DockerException as exc:
            logger.error(f"Cannot connect to Docker daemon: {exc}")
            self.client = None

    async def listen(self):
        if not self.client:
            logger.error("Docker client unavailable. Listener not started.")
            return
        logger.info("Docker event listener started.")
        loop = asyncio.get_event_loop()
        def _blocking_listen():
            for raw_event in self.client.events(decode=True, filters={"type": "container"}):
                action = raw_event.get("Action", "")
                if action not in WATCHED_EVENTS:
                    continue
                asyncio.run_coroutine_threadsafe(self._handle_event(raw_event), loop)
        await loop.run_in_executor(None, _blocking_listen)

    async def _handle_event(self, raw_event):
        action = raw_event.get("Action", "")
        actor = raw_event.get("Actor", {})
        attrs = actor.get("Attributes", {})
        container_id = actor.get("ID", "")[:12]
        container_name = attrs.get("name", "unknown")
        image_name = attrs.get("image", "unknown")
        event_payload = {
            "event_id": str(uuid.uuid4()),
            "event_type": f"container_{action}",
            "container_id": container_id,
            "container_name": container_name,
            "image_name": image_name,
            "timestamp": datetime.utcnow().isoformat(),
        }
        logger.info(f"Docker event: {action} | container={container_name} | image={image_name}")
        if action == "start":
            self.state_store.upsert_container(container_id, {
                "container_id": container_id, "name": container_name,
                "image": image_name, "status": "running"})
            self.state_store.append_audit({**event_payload, "action": "scan_enqueued"})
        elif action == "die":
            self.state_store.upsert_container(container_id, {"status": "dead"})
            self.state_store.append_audit({**event_payload, "action": "container_died"})
            await self.resilience_engine.handle_container_die(container_id, container_name, image_name)
        await self.ws_manager.broadcast(event_payload)
PYEOF

echo "Writing control_plane/core/resilience.py..."
cat > control_plane/core/resilience.py << 'PYEOF'
import asyncio
from datetime import datetime
import docker
from docker.errors import DockerException
from shared.utils.logger import get_logger

logger = get_logger("control_plane.resilience")
HEALTH_POLL_INTERVAL = 0.2
HEALTH_POLL_TIMEOUT = 10.0

class ResilienceEngine:
    def __init__(self, state_store, ws_manager):
        self.state_store = state_store
        self.ws_manager = ws_manager
        try:
            self.docker_client = docker.from_env()
        except DockerException:
            self.docker_client = None
            logger.error("ResilienceEngine: Docker client unavailable.")

    async def handle_container_die(self, container_id, name, image):
        if not self.state_store.is_critical(container_id):
            logger.info(f"Container {name} died — not critical, skipping failover.")
            return
        logger.info(f"CRITICAL container {name} died — initiating auto-failover.")
        await self._failover(container_id, name, image)

    async def _failover(self, original_id, name, image):
        if not self.docker_client:
            logger.error("Cannot failover — Docker client not available.")
            return
        replica_name = f"{name}-replica-{original_id[:6]}"
        start_time = datetime.utcnow()
        try:
            loop = asyncio.get_event_loop()
            container = await loop.run_in_executor(None,
                lambda: self.docker_client.containers.create(image=image, name=replica_name, detach=True))
            logger.info(f"Replica created: {replica_name}")
            await loop.run_in_executor(None, container.start)
            logger.info(f"Replica started: {replica_name}")
            recovered = await self._confirm_healthy(container, loop)
            elapsed_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            status = "recovered" if recovered else "recovery_timeout"
            logger.info(f"Failover: {replica_name} | {status} | {elapsed_ms:.1f}ms")
            audit_entry = {"event_type": "auto_failover", "original_container": original_id,
                           "replica_name": replica_name, "image": image,
                           "status": status, "latency_ms": round(elapsed_ms, 1)}
            self.state_store.append_audit(audit_entry)
            self.state_store.upsert_container(container.id[:12], {
                "container_id": container.id[:12], "name": replica_name,
                "image": image, "status": "running" if recovered else "unknown",
                "is_replica": True, "original_id": original_id})
            self.state_store.mark_critical(container.id[:12])
            await self.ws_manager.broadcast(audit_entry)
        except DockerException as exc:
            logger.error(f"Failover failed for {name}: {exc}")
            self.state_store.append_audit({"event_type": "auto_failover_error",
                                           "original_container": original_id, "error": str(exc)})

    async def _confirm_healthy(self, container, loop):
        elapsed = 0.0
        while elapsed < HEALTH_POLL_TIMEOUT:
            await asyncio.sleep(HEALTH_POLL_INTERVAL)
            elapsed += HEALTH_POLL_INTERVAL
            try:
                await loop.run_in_executor(None, container.reload)
                if container.status == "running":
                    return True
            except DockerException:
                pass
        return False
PYEOF

echo "Writing control_plane/dashboard/ws_manager.py..."
cat > control_plane/dashboard/ws_manager.py << 'PYEOF'
import json
from typing import List
from fastapi import WebSocket
from shared.utils.logger import get_logger

logger = get_logger("control_plane.ws_manager")

class WebSocketManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message):
        payload = json.dumps(message, default=str)
        dead = []
        for conn in self.active_connections:
            try:
                await conn.send_text(payload)
            except Exception:
                dead.append(conn)
        for d in dead:
            self.active_connections.remove(d)
PYEOF

echo "Writing control_plane/dashboard/ui.py..."
cat > control_plane/dashboard/ui.py << 'PYEOF'
DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <title>Container Security Engine</title>
  <style>
    *{box-sizing:border-box;margin:0;padding:0}
    body{font-family:'Segoe UI',sans-serif;background:#0f1117;color:#e2e8f0}
    header{background:#1a1f2e;padding:16px 24px;border-bottom:1px solid #2d3748;display:flex;align-items:center;gap:12px}
    header h1{font-size:1.2rem;font-weight:600;color:#63b3ed}
    .badge{font-size:.7rem;padding:2px 8px;border-radius:9999px;background:#22543d;color:#68d391;font-weight:600}
    main{padding:24px;display:grid;grid-template-columns:1fr 1fr;gap:20px}
    .card{background:#1a1f2e;border-radius:10px;padding:20px;border:1px solid #2d3748}
    .card h2{font-size:.85rem;text-transform:uppercase;letter-spacing:.05em;color:#90cdf4;margin-bottom:14px}
    table{width:100%;border-collapse:collapse;font-size:.85rem}
    th{text-align:left;padding:8px 10px;color:#718096;border-bottom:1px solid #2d3748;font-weight:500}
    td{padding:8px 10px;border-bottom:1px solid #1e2533}
    .run{color:#68d391;font-weight:600}.dead{color:#fc8181;font-weight:600}.crit{color:#f6ad55;font-weight:600}
    #feed{max-height:340px;overflow-y:auto;font-size:.8rem}
    .erow{padding:6px 8px;border-bottom:1px solid #1e2533;display:flex;gap:10px;align-items:flex-start}
    .etype{font-weight:600;color:#63b3ed;min-width:140px}
    .etime{color:#4a5568;font-size:.75rem;margin-left:auto;white-space:nowrap}
    .mg{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}
    .m{background:#161b27;border-radius:8px;padding:14px;text-align:center}
    .mv{font-size:2rem;font-weight:700;color:#63b3ed}
    .ml{font-size:.75rem;color:#718096;margin-top:4px}
    .dot{width:8px;height:8px;border-radius:50%;background:#fc8181;display:inline-block}
    .dot.on{background:#68d391}
  </style>
</head>
<body>
<header>
  <div><h1>&#x1F6E1; Resilient Container Security Engine</h1>
  <small style="color:#718096">Control Plane Dashboard &mdash; Live</small></div>
  <span class="badge">MASTER NODE</span>
  <span style="margin-left:auto;display:flex;align-items:center;gap:6px;font-size:.8rem;color:#718096">
    <span class="dot" id="dot"></span><span id="wslabel">Connecting...</span>
  </span>
</header>
<main>
  <div class="card" style="grid-column:1/-1">
    <h2>Active Containers</h2>
    <table><thead><tr><th>ID</th><th>Name</th><th>Image</th><th>Status</th><th>Critical</th><th>Updated</th></tr></thead>
    <tbody id="ctbl"><tr><td colspan="6" style="color:#4a5568;text-align:center;padding:20px">Waiting for events...</td></tr></tbody></table>
  </div>
  <div class="card"><h2>Live Event Feed</h2><div id="feed"></div></div>
  <div class="card"><h2>Metrics</h2>
    <div class="mg">
      <div class="m"><div class="mv" id="mtot">0</div><div class="ml">Total Events</div></div>
      <div class="m"><div class="mv" id="mfo">0</div><div class="ml">Auto-Failovers</div></div>
      <div class="m"><div class="mv" id="mrun">0</div><div class="ml">Running</div></div>
      <div class="m"><div class="mv" id="mcrit">0</div><div class="ml">Critical</div></div>
    </div>
  </div>
</main>
<script>
const containers={};let total=0,fo=0;
const ws=new WebSocket(`ws://${location.host}/ws/dashboard`);
const dot=document.getElementById('dot'),lbl=document.getElementById('wslabel');
ws.onopen=()=>{dot.classList.add('on');lbl.textContent='Connected'};
ws.onclose=()=>{dot.classList.remove('on');lbl.textContent='Disconnected'};
ws.onmessage=(m)=>{
  const e=JSON.parse(m.data);total++;
  document.getElementById('mtot').textContent=total;
  if(e.container_id){
    containers[e.container_id]=containers[e.container_id]||{};
    Object.assign(containers[e.container_id],{
      container_id:e.container_id,
      name:e.container_name||e.name||'—',
      image:e.image_name||e.image||'—',
      status:e.event_type==='container_start'?'running':e.event_type==='container_die'?'dead':'unknown',
      is_critical:e.is_critical||false,
      updated_at:e.timestamp
    });
    render();
  }
  if(e.event_type==='auto_failover'){fo++;document.getElementById('mfo').textContent=fo;}
  addRow(e);
};
function render(){
  const tbody=document.getElementById('ctbl');
  const r=Object.values(containers).map(c=>{
    const sc=c.status==='running'?'run':c.status==='dead'?'dead':'';
    return`<tr><td><code>${c.container_id}</code></td><td>${c.name}</td><td>${c.image}</td>
    <td class="${sc}">${c.status}</td>
    <td>${c.is_critical?'<span class="crit">YES</span>':'no'}</td>
    <td style="color:#4a5568;font-size:.75rem">${c.updated_at||''}</td></tr>`;
  });
  tbody.innerHTML=r.length?r.join(''):'<tr><td colspan="6" style="color:#4a5568;text-align:center;padding:20px">No containers yet</td></tr>';
  document.getElementById('mrun').textContent=Object.values(containers).filter(c=>c.status==='running').length;
  document.getElementById('mcrit').textContent=Object.values(containers).filter(c=>c.is_critical).length;
}
function addRow(e){
  const feed=document.getElementById('feed');
  const row=document.createElement('div');row.className='erow';
  const t=new Date(e.timestamp||Date.now()).toLocaleTimeString();
  row.innerHTML=`<span class="etype">${e.event_type||'event'}</span><span>${e.container_name||e.replica_name||'—'}</span><span class="etime">${t}</span>`;
  feed.prepend(row);
  if(feed.children.length>100)feed.removeChild(feed.lastChild);
}
</script>
</body></html>"""
PYEOF

echo "Writing control_plane/api/main.py..."
cat > control_plane/api/main.py << 'PYEOF'
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
PYEOF

echo "Writing cache/storage/lru_cache.py..."
cat > cache/storage/lru_cache.py << 'PYEOF'
from collections import OrderedDict
from typing import Optional, Dict, Any
import threading
from shared.utils.logger import get_logger

logger = get_logger("cache.lru_cache")

class LRUCache:
    def __init__(self, max_size=1000):
        self.max_size = max_size
        self._cache: OrderedDict = OrderedDict()
        self._lock = threading.Lock()
        self.hits = 0; self.misses = 0

    def get(self, key):
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                self._cache[key]["hit_count"] = self._cache[key].get("hit_count", 0) + 1
                self.hits += 1
                return self._cache[key]
            self.misses += 1
            return None

    def set(self, key, value):
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = value
            if len(self._cache) > self.max_size:
                evicted, _ = self._cache.popitem(last=False)
                logger.info(f"Evicted: {evicted[:16]}...")

    def hit_ratio(self):
        total = self.hits + self.misses
        return round(self.hits / total, 3) if total > 0 else 0.0

    def size(self):
        return len(self._cache)
PYEOF

echo "Writing scheduler/queue/job_queue.py..."
cat > scheduler/queue/job_queue.py << 'PYEOF'
import asyncio, uuid
from datetime import datetime
from shared.utils.logger import get_logger

logger = get_logger("scheduler.job_queue")

class JobQueue:
    def __init__(self):
        self._queue = asyncio.Queue()
        self._in_flight = {}

    async def enqueue(self, container_id, image_id, image_name):
        job_id = str(uuid.uuid4())
        job = {"job_id": job_id, "container_id": container_id,
               "image_id": image_id, "image_name": image_name,
               "status": "pending", "submitted_at": datetime.utcnow().isoformat()}
        await self._queue.put(job)
        logger.info(f"Enqueued job {job_id} for {container_id}")
        return job_id

    async def dequeue(self):
        job = await self._queue.get()
        self._in_flight[job["job_id"]] = job
        return job

    def complete(self, job_id, result):
        if job_id in self._in_flight:
            self._in_flight[job_id].update({"status": "completed", "result": result})
            del self._in_flight[job_id]

    def depth(self):
        return self._queue.qsize()
PYEOF

echo "Writing test files..."
cat > tests/unit/test_hashing.py << 'PYEOF'
from shared.utils.hashing import compute_layer_hash, compute_image_hash

def test_layer_hash_deterministic():
    assert compute_layer_hash("sha256:abc") == compute_layer_hash("sha256:abc")

def test_different_layers_different_hashes():
    assert compute_layer_hash("layer1") != compute_layer_hash("layer2")

def test_image_hash_order_independent():
    assert compute_image_hash(["a","b","c"]) == compute_image_hash(["c","a","b"])
PYEOF

cat > tests/unit/test_lru_cache.py << 'PYEOF'
from cache.storage.lru_cache import LRUCache

def test_set_and_get():
    c = LRUCache(max_size=10)
    c.set("k1", {"report": "data"})
    assert c.get("k1")["report"] == "data"

def test_miss_returns_none():
    assert LRUCache().get("missing") is None

def test_eviction():
    c = LRUCache(max_size=3)
    for i in range(1, 5):
        c.set(f"k{i}", {"v": i})
    assert c.get("k1") is None
    assert c.get("k4") is not None

def test_hit_ratio():
    c = LRUCache()
    c.set("k1", {"v": 1})
    c.get("k1"); c.get("missing")
    assert c.hit_ratio() == 0.5
PYEOF

echo ""
echo "============================================"
echo "  Setup complete! 44 files created."
echo "============================================"
echo ""
echo "Next steps:"
echo "  1.  pip install -r requirements.txt"
echo "  2.  uvicorn control_plane.api.main:app --reload --port 8000"
echo "  3.  Open http://localhost:8000 in your browser"
echo ""
