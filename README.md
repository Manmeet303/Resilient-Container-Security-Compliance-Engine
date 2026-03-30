# 🛡️ Resilient Container Security & Compliance Engine

> **Advanced Operating Systems Project** — Texas A&M University–Corpus Christi  
> **Team:** Code Gems &nbsp;|&nbsp; **Course:** CSCE 5331 Advanced Operating Systems  
> **Members:** Manmeet Detroja · Margesh Vyas · Mahip Patel

---

## 📖 Overview

Modern container security tools like Trivy are powerful but traditionally deployed as **monolithic blockers** in CI/CD pipelines — every container waits for a full scan before it can run.

This project solves that by building a **custom distributed system** that decouples scanning from deployment:

- Containers start **instantly** — no blocking
- Scans run **asynchronously** in a fault-tolerant worker pool
- Identical image layers are **never scanned twice** thanks to a cryptographic distributed cache
- If any node fails — worker, cache, or even the master — **the system heals itself automatically**

---

## 🏗️ Architecture — Three Pillars

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CONTROL PLANE (Master)                        │
│  Docker Socket → Event Listener → State Store → WebSocket Dashboard  │
│                        ↓               ↓                             │
│               Auto-Failover      Disk Persistence                    │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ job enqueue (singleton queue)
┌──────────────────────────▼──────────────────────────────────────────┐
│                    DISTRIBUTED TASK SCHEDULER                         │
│   JobQueue → Dispatcher → WorkerPool → HeartbeatMonitor              │
│                              ↓                                        │
│              process_job() → scan result → cache write-back           │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ get/put layer scan
┌──────────────────────────▼──────────────────────────────────────────┐
│                      DISTRIBUTED CACHE                                │
│   ConsistentHashRing → CacheNode-1 (8001) + CacheNode-2 (8002)       │
│   SHA-256 layer hash → LRU eviction → TTL expiry → Hit/Miss stats    │
└─────────────────────────────────────────────────────────────────────┘

                    STANDBY MASTER (port 8080)
              Mirrors state every 5s · Promotes on failure
```

---

## ⚙️ Tech Stack

| Component | Technology |
|---|---|
| Language | Python 3.11+ |
| API Framework | FastAPI + Uvicorn |
| Container Events | Docker Engine API (`docker-py`) |
| Security Scanner | Trivy (Aqua Security) |
| Async Runtime | asyncio |
| Cache Communication | HTTP REST |
| Real-time Dashboard | WebSockets + HTML/CSS/JS |
| State Persistence | JSON file (`/tmp/rcsce_state.json`) |

---

## 👥 Team & Module Ownership

| Member | Module | Key Files |
|---|---|---|
| **Manmeet Detroja** | Control Plane & Resilience | `control_plane/api/main.py`, `control_plane/api/standby.py`, `control_plane/core/docker_listener.py`, `control_plane/core/resilience.py`, `control_plane/core/state_store.py`, `control_plane/dashboard/ui.py` |
| **Margesh Vyas** | Distributed Task Scheduler | `scheduler/dispatcher.py`, `scheduler/scheduler_service.py`, `scheduler/queue/job_queue.py`, `scheduler/workers/`, `scheduler/heartbeat/` |
| **Mahip Patel** | Distributed Cache | `cache/cache_node.py`, `cache/cache_common.py`, `cache/worker_cache_client.py`, `cache/storage/lru_cache.py` |

---

## 🚀 Getting Started

### Prerequisites

- Python 3.11+
- Docker Desktop running
- Git

### 1. Clone the repository

```bash
git clone https://github.com/Manmeet303/Resilient-Container-Security-Compliance-Engine.git
cd Resilient-Container-Security-Compliance-Engine
```

### 2. Create virtual environment and install dependencies

```bash
python -m venv venv

# Mac/Linux
source venv/bin/activate

# Windows
venv\Scripts\activate

# Install (Mac/Linux)
pip install -r requirements.txt

# Install (Windows — uvloop not supported on Windows)
pip install fastapi uvicorn docker requests pydantic aiohttp httpx websockets python-dotenv
```

### 3. Set Docker socket (Mac only)

```bash
export DOCKER_HOST=unix:///Users/<your-username>/.docker/run/docker.sock
```

> **Windows:** Docker socket is set automatically. Skip this step.

---

## 🖥️ Running the System

You need **4 terminals** for the full system. Open them all from the project root.

---

### Terminal 1 — Primary Master (Control Plane)

```bash
# Mac
export DOCKER_HOST=unix:///Users/<your-username>/.docker/run/docker.sock
uvicorn control_plane.api.main:app --port 8000

# Windows
uvicorn control_plane.api.main:app --port 8000
```

**Expected output:**
```
INFO: Uvicorn running on http://127.0.0.1:8000
INFO: Connected to Docker daemon via /var/run/docker.sock
INFO: Docker event listener started.
```

Open **http://localhost:8000** — dashboard should show CONNECTED.

---

### Terminal 2 — Standby Master (Failover Node)

```bash
# Mac
export DOCKER_HOST=unix:///Users/<your-username>/.docker/run/docker.sock
uvicorn control_plane.api.standby:app --port 8080

# Windows
uvicorn control_plane.api.standby:app --port 8080
```

**Expected output:**
```
INFO: Standby master node starting on port 8080...
INFO: Watching primary at http://localhost:8000
INFO: Standby: primary healthy ✓    ← repeats every 2s
INFO: Standby: mirrored state — 0 containers, 0 workers
```

Open **http://localhost:8080** — shows standby dashboard.

---

### Terminal 3 — Distributed Task Scheduler

```bash
python run_scheduler.py
```

**Expected output:**
```
INFO: Global JobQueue singleton created.
INFO: Worker registered: worker-1
INFO: Worker registered: worker-2
INFO: Scheduler starting
INFO: Scheduler heartbeat monitor and dispatcher running.
```

---

### Terminal 4 — Cache Node(s)

```bash
# Cache node 1
NODE_ID=cache-node-1 uvicorn cache.cache_node:app --port 8001

# Optionally in a 5th terminal — cache node 2
NODE_ID=cache-node-2 uvicorn cache.cache_node:app --port 8002
```

**Expected output:**
```
INFO: Uvicorn running on http://127.0.0.1:8001
INFO: Application startup complete.
```

---

## 🧪 Testing the System

### Test 1 — Container Start → Cache Miss → Scan Job

```bash
docker run -d --name test-nginx nginx
```

**Watch Terminal 1:**
```
INFO: Docker event: start | container=test-nginx | image=nginx
INFO: Cache MISS for nginx. Enqueuing scan job.
INFO: Enqueued job <uuid> for <container_id>
```

**Watch Terminal 3:**
```
INFO: Dispatching job <uuid> to worker worker-1
INFO: Completed job <uuid> on worker worker-1
INFO: Stored in cache (hash=...)
```

**Dashboard at localhost:8000:**
- Container appears in Active Containers
- Queue depth flashes then drops to 0
- Audit log shows `scan_enqueued` entry

---

### Test 2 — Same Image → Cache Hit (scan skipped)

```bash
docker run -d --name test-nginx-2 nginx
```

**Watch Terminal 1:**
```
INFO: Cache HIT for nginx (hash=...) on node cache-node-1
```

Dashboard shows Cache Hits counter increment — Trivy scan was skipped entirely.

---

### Test 3 — Auto-Failover (Critical Container)

```bash
# Mark as critical first
curl -X POST http://localhost:8000/containers/<container_id>/critical

# Then kill it
docker stop test-nginx
```

**Watch Terminal 1:**
```
INFO: CRITICAL container test-nginx died — initiating auto-failover.
INFO: Replica created: test-nginx-replica-<id>
INFO: Failover: recovered | 234ms
```

Dashboard Auto-Failovers counter increments.

---

### Test 4 — Master Node Failover (Kill Primary)

```bash
# With all 4 terminals running and a container active:
# Press Ctrl+C in Terminal 1 to kill the primary
```

**Watch Terminal 2 (standby):**
```
WARNING: Standby: primary unreachable (1/3)
WARNING: Standby: primary unreachable (2/3)
WARNING: Standby: primary unreachable (3/3)
INFO: STANDBY PROMOTED TO PRIMARY — primary node is down!
INFO: Docker listener starting on standby node...
```

Open **http://localhost:8080** — dashboard shows all state preserved, Docker listener now active on standby.

---

### Test 5 — Worker Failure → Job Reassignment

```bash
# With scheduler running and jobs in queue:
# Press Ctrl+C in Terminal 3 to kill the scheduler
# Wait 10 seconds (heartbeat timeout)
# Restart Terminal 3: python run_scheduler.py
```

In-flight jobs are reclaimed and re-dispatched to healthy workers automatically.

---

## 📊 API Endpoints

### Primary / Standby Master (ports 8000 / 8080)

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Live dashboard UI |
| `/health` | GET | Node health + role (primary/standby) |
| `/status` | GET | All containers, workers, queue depth |
| `/containers` | GET | List all tracked containers |
| `/containers/{id}/critical` | POST | Mark container as critical for failover |
| `/audit-log` | GET | Last 200 audit events |
| `/ws/dashboard` | WebSocket | Real-time event stream |

### Cache Nodes (ports 8001 / 8002)

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Node health + cache stats |
| `/cache/{layer_hash}` | GET | Look up scan result by layer hash |
| `/cache` | POST | Store scan result |
| `/cache/{layer_hash}` | DELETE | Evict cache entry |

---

## 🔑 Key Features

| Feature | Status | Description |
|---|---|---|
| Zero-blocking deployments | ✅ | Containers start instantly, scanned async |
| Distributed task scheduling | ✅ | Worker pool with load balancing |
| Worker fault tolerance | ✅ | Heartbeat + job reassignment on worker death |
| Cryptographic layer caching | ✅ | SHA-256 hash → LRU cache → 0 redundant scans |
| Consistent hash routing | ✅ | Jobs routed to cache nodes by hash ring |
| Auto-failover replication | ✅ | Critical containers spin up replicas on death |
| Active-passive master failover | ✅ | Standby promotes in ~6 seconds |
| State persistence | ✅ | Survives master restarts via disk snapshot |
| Real-time dashboard | ✅ | WebSocket pipeline visualization |
| Audit logging | ✅ | Full trace of every system event |

---

## 📁 Project Structure

```
Resilient-Container-Security-Compliance-Engine/
│
├── control_plane/              # Manmeet — Master node
│   ├── api/
│   │   ├── main.py             # Primary FastAPI app (port 8000)
│   │   └── standby.py          # Standby master node (port 8080)
│   ├── core/
│   │   ├── docker_listener.py  # Docker socket event listener
│   │   ├── resilience.py       # Auto-failover engine
│   │   └── state_store.py      # Thread-safe state + disk persistence
│   └── dashboard/
│       ├── ui.py               # Dashboard HTML/CSS/JS
│       └── ws_manager.py       # WebSocket broadcast manager
│
├── scheduler/                  # Margesh — Task scheduler
│   ├── dispatcher.py           # Job dispatcher with concurrent execution
│   ├── scheduler_service.py    # Service entry point
│   ├── queue/
│   │   └── job_queue.py        # Async job queue + singleton
│   ├── workers/
│   │   ├── worker_node.py      # Worker node with heartbeat
│   │   └── worker_registry.py  # Worker registry + load tracking
│   └── heartbeat/
│       └── monitor.py          # Heartbeat monitor + job recovery
│
├── cache/                      # Mahip — Distributed cache
│   ├── cache_node.py           # FastAPI cache server
│   ├── cache_common.py         # LRU cache + consistent hash ring
│   ├── worker_cache_client.py  # HTTP client for cache nodes
│   └── storage/
│       └── lru_cache.py        # Thread-safe LRU implementation
│
├── shared/                     # Shared utilities
│   ├── utils/
│   │   ├── logger.py           # JSON structured logger
│   │   └── hashing.py          # SHA-256 layer hash utilities
│   └── models/
│       └── container_event.py  # Pydantic event models
│
├── tests/
│   └── unit/
│       ├── test_hashing.py
│       └── test_lru_cache.py
│
├── run_scheduler.py            # Scheduler entry point
├── requirements.txt            # Python dependencies
└── README.md
```

---

## 🧩 How the Pipeline Works

```
docker run nginx
      ↓
DockerEventListener receives container_start event
      ↓
Compute SHA-256(image_name:layer_digest) = layer_hash
      ↓
Query cache node: GET /cache/{layer_hash}
      ↓
    HIT? ──→ Use cached result, skip scan ──→ Audit log: cache_hit
      ↓
    MISS? ──→ Enqueue scan job to JobQueue
              ↓
           Dispatcher picks lowest-load worker
              ↓
           worker.process_job(job) ← Trivy scan
              ↓
           Write result to cache: PUT /cache
              ↓
           queue.complete(job_id, result)
              ↓
           Audit log: scan_complete
```

---

## 🔥 Chaos Engineering Scenarios

The system is validated against these failure scenarios:

| Scenario | Expected Behaviour |
|---|---|
| Kill worker mid-scan | HeartbeatMonitor reclaims job in ≤10s, re-dispatches |
| Kill cache node | Client falls back to next node via consistent hash ring |
| Same image starts twice | Second start is cache HIT, Trivy not called |
| Kill critical container | Replica spun up in ≤500ms |
| Kill primary master | Standby promotes in ≤6s, all state preserved |
| Flood 20 containers | Queue handles backpressure, all jobs processed |

---

## 🔧 Troubleshooting

| Error | Fix |
|---|---|
| `Cannot connect to Docker daemon` | `export DOCKER_HOST=unix:///Users/<name>/.docker/run/docker.sock` |
| `ModuleNotFoundError: cache` | Run from project root, not inside a subfolder |
| `ModuleNotFoundError: cache_common` | `cache_common.py` must be inside `cache/` not at root |
| `uvloop` install error on Windows | Skip uvloop — `pip install fastapi uvicorn docker requests pydantic` |
| Dashboard shows old state after restart | State loads from `/tmp/rcsce_state.json` — delete it for a clean start: `rm /tmp/rcsce_state.json` |
| Workers marked dead immediately | Run `python run_scheduler.py` from project root |

---

*Built for Advanced Operating Systems — TAMU-CC · Spring 2026*