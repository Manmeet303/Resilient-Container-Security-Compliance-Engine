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
- Container logs are monitored in real-time for anomaly detection (FATAL, ERROR, unauthorized access)

---

## 🏗️ Architecture — Three Pillars

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CONTROL PLANE (Master)                        │
│  Docker Socket → Event Listener → State Store → WebSocket Dashboard  │
│                        ↓               ↓                             │
│               Auto-Failover      Disk Persistence                    │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ job enqueue (HTTP → port 9010)
┌──────────────────────────▼──────────────────────────────────────────┐
│                    DISTRIBUTED TASK SCHEDULER                         │
│   JobQueue → Dispatcher → WorkerPool → HeartbeatMonitor              │
│                              ↓                                        │
│              process_job() → scan result → cache write-back           │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ get/put layer scan (HTTP → port 9001)
┌──────────────────────────▼──────────────────────────────────────────┐
│                      DISTRIBUTED CACHE                                │
│   ConsistentHashRing → CacheNode-1 (9001) + CacheNode-2 (9002)       │
│   SHA-256 layer hash → LRU eviction → TTL expiry → Hit/Miss stats    │
└─────────────────────────────────────────────────────────────────────┘

                    STANDBY MASTER (port 9090)
              Mirrors state every 5s · Promotes on failure
```

---

## ⚙️ Tech Stack

| Component | Technology |
|---|---|
| Language | Python 3.11+ |
| API Framework | FastAPI + Uvicorn |
| Container Events | Docker Engine API (`docker-py`) |
| Security Scanner | Trivy (Aqua Security) — with mock fallback if not installed |
| Async Runtime | asyncio |
| Inter-service Communication | HTTP REST (FastAPI endpoints) |
| Real-time Dashboard | WebSockets + HTML/CSS/JS |
| State Persistence | JSON file (`/tmp/rcsce_state.json`) |

---

## 👥 Team & Module Ownership

| Member | Module | Key Files |
|---|---|---|
| **Manmeet Detroja** | Control Plane & Resilience | `control_plane/api/main.py`, `control_plane/api/standby.py`, `control_plane/core/docker_listener.py`, `control_plane/core/resilience.py`, `control_plane/core/state_store.py`, `control_plane/core/log_monitor.py`, `control_plane/dashboard/ui.py` |
| **Margesh Vyas** | Distributed Task Scheduler | `scheduler/dispatcher.py`, `scheduler/scheduler_service.py`, `scheduler/queue/job_queue.py`, `scheduler/workers/worker_node.py`, `scheduler/workers/worker_registry.py`, `scheduler/heartbeat/monitor.py` |
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
pip install fastapi uvicorn docker requests pydantic aiohttp httpx websockets python-dotenv psutil
```

### 3. Set Docker socket (Mac only)

```bash
export DOCKER_HOST=unix:///Users/<your-username>/.docker/run/docker.sock
```

> **Windows:** Docker socket is set automatically. Skip this step.

---

## 🖥️ Running the System

You need **4 terminals** for the full system. **Start them in this exact order** — the cache node must be up before the primary master starts processing Docker events.

---

### Terminal 1 — Cache Node *(start first)*

```bash
source venv/bin/activate
NODE_ID=cache-node-1 uvicorn cache.cache_node:app --port 9001
```

**Expected output:**
```
INFO: Uvicorn running on http://127.0.0.1:9001
INFO: Application startup complete.
```

Verify: `curl http://localhost:9001/health`

> **Optional — second cache node in Terminal 5:**
> ```bash
> NODE_ID=cache-node-2 uvicorn cache.cache_node:app --port 9002
> ```
> The consistent hash ring in `worker_cache_client.py` automatically routes across both nodes.

---

### Terminal 2 — Distributed Task Scheduler *(start second)*

```bash
source venv/bin/activate
python run_scheduler.py
```

**Expected output:**
```
INFO: Global JobQueue singleton created.
INFO: Worker registered: worker-1
INFO: Worker registered: worker-2
INFO: Scheduler starting
INFO: Scheduler heartbeat monitor and dispatcher running.
INFO: Uvicorn running on http://127.0.0.1:9010
```

Verify: `curl http://localhost:9010/health`

---

### Terminal 3 — Primary Master (Control Plane) *(start third)*

```bash
# Mac
export DOCKER_HOST=unix:///Users/<your-username>/.docker/run/docker.sock
uvicorn control_plane.api.main:app --port 9000

# Windows
uvicorn control_plane.api.main:app --port 9000
```

**Expected output:**
```
INFO: Uvicorn running on http://127.0.0.1:9000
INFO: Connected to Docker daemon via /var/run/docker.sock
INFO: Docker event listener started.
```

Open **http://localhost:9000** — dashboard should show CONNECTED.

---

### Terminal 4 — Standby Master (Failover Node) *(start last)*

```bash
# Mac
export DOCKER_HOST=unix:///Users/<your-username>/.docker/run/docker.sock
uvicorn control_plane.api.standby:app --port 9090

# Windows
uvicorn control_plane.api.standby:app --port 9090
```

**Expected output:**
```
INFO: Standby master node starting on port 9090...
INFO: Watching primary at http://localhost:9000
INFO: Standby: primary healthy ✓    ← repeats every 2s
INFO: Standby: mirrored state — 0 containers, 0 workers
```

Open **http://localhost:9090** — shows standby dashboard mirroring primary.

---

## 🧪 Testing the System

### Test 1 — Container Start → Cache Miss → Scan Job

```bash
docker run -d --name test-nginx nginx
```

**Watch Terminal 3:**
```
INFO: Docker event: start | container=test-nginx | image=nginx
INFO: Cache MISS for nginx. Enqueuing scan job.
INFO: Job pushed to scheduler
```

**Watch Terminal 2:**
```
INFO: Dispatching job <uuid> to worker <worker-id>
INFO: Completed job <uuid> on worker <worker-id>
INFO: Cache write: 200 | hash=...
```

**Dashboard at localhost:9000:**
- Container appears in Active Containers
- Queue depth flashes then drops to 0
- Vulnerabilities column fills in with CVE counts

---

### Test 2 — Same Image → Cache Hit (scan skipped)

```bash
docker run -d --name test-nginx-2 nginx
```

**Watch Terminal 3:**
```
INFO: Cache HIT for nginx (hash=...) on node cache-node-1
```

Dashboard Cache Hits counter increments. Vulnerabilities column fills in **immediately** — Trivy was never called.

---

### Test 3 — Log Anomaly Detection

```bash
docker run -d --name mock-app python:3.11 python -c "
import time, random, sys
while True:
    time.sleep(3)
    if random.random() < 0.2:
        print('[FATAL] Database connection lost on port 5432!', file=sys.stderr, flush=True)
    else:
        print('[INFO] health check ok', flush=True)
"
```

**Dashboard:** Red `anomaly_detected` events appear in Live Events feed in real-time as FATAL lines are logged.

---

### Test 4 — Auto-Failover (Critical Container)

```bash
# Get the container ID
CONTAINER_ID=$(docker ps --format "{{.ID}} {{.Names}}" | grep test-nginx | head -1 | awk '{print $1}')

# Mark it as critical
curl -X POST http://localhost:9000/containers/$CONTAINER_ID/critical

# Kill it
docker stop test-nginx
```

**Watch Terminal 3:**
```
INFO: CRITICAL container test-nginx died — initiating auto-failover.
INFO: Replica created: test-nginx-replica-<id>
INFO: Failover: recovered | ~200ms
```

Dashboard Auto-Failovers counter increments. Replica row appears in Containers table.

---

### Test 5 — Master Node Failover (Kill Primary)

```bash
# Press Ctrl+C in Terminal 3 to kill the primary master
```

**Watch Terminal 4 (standby):**
```
WARNING: Standby: primary unreachable (1/3)
WARNING: Standby: primary unreachable (2/3)
WARNING: Standby: primary unreachable (3/3)
INFO: STANDBY PROMOTED TO PRIMARY — primary node is down!
INFO: Docker listener starting on standby node...
```

**Dashboard at http://localhost:9090** shows red promotion banner. All state (containers, workers, audit log) is preserved — the standby mirrored it every 5 seconds.

---

### Test 6 — Worker Failure → Job Reassignment

```bash
# Press Ctrl+C in Terminal 2 to kill the scheduler
# Wait 10 seconds (heartbeat timeout)
# Restart:
python run_scheduler.py
```

In-flight jobs are reclaimed from the dead worker and re-dispatched to the newly started healthy workers automatically.

---

### Test 7 — Cleanup

```bash
docker stop test-nginx test-nginx-2 mock-app 2>/dev/null
docker rm  test-nginx test-nginx-2 mock-app 2>/dev/null

# Remove any auto-created replicas
docker ps -a --format "{{.Names}}" | grep replica | xargs docker rm -f 2>/dev/null

# Clear state for a clean next run
rm /tmp/rcsce_state.json
```

---

## 📈 Benchmark — CPU Savings from Caching

The `benchmark.py` script quantifies the performance impact of the distributed cache by running two controlled experiments:

- **Experiment A** — Cold scans: every container start triggers a full Trivy scan (cache empty)
- **Experiment B** — Cached scans: same images, cache pre-seeded, results returned instantly

```bash
# Run with cache node on port 9001
python benchmark.py --count 10 --image nginx --output results.csv
```

**Measured results (10 containers × nginx):**

| Metric | Cold (MISS) | Cached (HIT) |
|---|---|---|
| Total wall-clock time | ~40,000ms | ~20ms |
| Mean latency / container | ~4,000ms | ~2ms |
| Total CPU time consumed | ~26s | ~0.008s |
| Trivy scans skipped | 0 of 10 | 10 of 10 (100%) |

**Result: ~99.9% reduction in scan latency and ~100% CPU savings on repeat image deployments.**

Keys used by the benchmark are isolated from the live system and cleaned up automatically on completion.

---

## 📊 API Endpoints

### Primary / Standby Master (ports 9000 / 9090)

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Live dashboard UI |
| `/health` | GET | Node health + role (primary/standby) |
| `/status` | GET | All containers, workers, queue depth |
| `/containers` | GET | List all tracked containers |
| `/containers/{id}/critical` | POST | Mark container as critical for failover |
| `/audit-log` | GET | Last 200 audit events |
| `/ws/dashboard` | WebSocket | Real-time event stream |
| `/internal/workers/heartbeat` | POST | Worker heartbeat IPC (scheduler → master) |
| `/internal/scan/complete` | POST | Scan result IPC (dispatcher → master) |

### Scheduler (port 9010)

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Scheduler health + queue depth + worker count |
| `/jobs/enqueue` | POST | Accept scan job from control plane |

### Cache Nodes (ports 9001 / 9002)

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Node health + cache stats summary |
| `/stats` | GET | Detailed stats: entries, capacity, fill %, hit/miss ratio, key list |
| `/cache/{layer_hash}` | GET | Look up scan result by layer hash |
| `/cache` | POST | Store scan result (write-through to all nodes) |
| `/cache/{layer_hash}` | DELETE | Evict cache entry |

---

## 🔑 Key Features

| Feature | Status | Description |
|---|---|---|
| Zero-blocking deployments | ✅ | Containers start instantly, scanned async |
| Distributed task scheduling | ✅ | Worker pool with load balancing |
| Worker fault tolerance | ✅ | Heartbeat + job reassignment on worker death |
| Cryptographic layer caching | ✅ | SHA-256 hash → LRU cache → 0 redundant scans |
| Consistent hash routing | ✅ | Cache lookups routed by hash ring across nodes |
| Cache node failover | ✅ | Dead node removed from ring, retried on next node, re-added on recovery |
| Cache write-through | ✅ | Scan results written to all nodes — no miss on ring rebalance |
| Auto-failover replication | ✅ | Critical containers spin up replicas on death |
| Active-passive master failover | ✅ | Standby promotes in ~6 seconds |
| State persistence | ✅ | Containers, workers, audit log survive master restarts via disk snapshot |
| Real-time dashboard | ✅ | WebSocket pipeline visualization with live health graphs |
| Log anomaly detection | ✅ | Container stdout/stderr streamed and scanned for FATAL/ERROR/unauthorized |
| Audit logging | ✅ | Full persisted trace of every system event |
| CPU savings benchmark | ✅ | Controlled experiment proving cache impact (~99.9% latency reduction) |

---

## 📁 Project Structure

```
Resilient-Container-Security-Compliance-Engine/
│
├── control_plane/              # Manmeet — Master node
│   ├── api/
│   │   ├── main.py             # Primary FastAPI app (port 9000)
│   │   └── standby.py          # Standby master node (port 9090)
│   ├── core/
│   │   ├── docker_listener.py  # Docker socket event listener + cache check
│   │   ├── resilience.py       # Auto-failover engine
│   │   ├── log_monitor.py      # Real-time container log anomaly detection
│   │   └── state_store.py      # Thread-safe state + disk persistence
│   └── dashboard/
│       ├── ui.py               # Dashboard HTML/CSS/JS + Health tab
│       └── ws_manager.py       # WebSocket broadcast manager
│
├── scheduler/                  # Margesh — Task scheduler
│   ├── dispatcher.py           # Job dispatcher + cache write-back
│   ├── scheduler_service.py    # FastAPI service entry point (port 9010)
│   ├── queue/
│   │   └── job_queue.py        # Async job queue + singleton
│   ├── workers/
│   │   ├── worker_node.py      # Worker node + Trivy execution + heartbeat
│   │   └── worker_registry.py  # Worker registry + load tracking
│   └── heartbeat/
│       └── monitor.py          # Heartbeat monitor + dead worker job recovery
│
├── cache/                      # Mahip — Distributed cache
│   ├── cache_node.py           # FastAPI cache server (port 9001 / 9002)
│   ├── cache_common.py         # LRU cache + consistent hash ring
│   ├── worker_cache_client.py  # HTTP client with node failover + write-through
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
├── benchmark.py                # CPU savings benchmark (cold vs cached scans)
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
    HIT? ──→ Propagate cached vuln data to state + UI ──→ Audit log: cache_hit
      ↓
    MISS? ──→ Enqueue scan job → POST /jobs/enqueue (port 9010)
              ↓
           Dispatcher picks lowest-load worker
              ↓
           worker.process_job(job) ← Trivy scan (or mock if Trivy not installed)
              ↓
           Write result to ALL cache nodes: POST /cache (write-through)
              ↓
           Notify control plane: POST /internal/scan/complete
              ↓
           Dashboard updates: vulnerabilities column fills in live
```

---

## 🔥 Chaos Engineering Scenarios

The system is validated against these failure scenarios:

| Scenario | Expected Behaviour |
|---|---|
| Kill worker mid-scan | HeartbeatMonitor reclaims job in ≤10s, re-dispatches to healthy worker |
| Kill cache node | Client removes node from ring, retries on next node, re-adds after 15s recovery |
| Same image starts twice | Second start is cache HIT, Trivy not called, result shown instantly |
| Kill critical container | Replica spun up in ≤500ms, also marked critical for cascading protection |
| Kill primary master | Standby promotes in ≤6s, all state preserved, Docker listener restarts |
| Flood 20 containers | Queue handles backpressure, all jobs processed in order |
| Container logs FATAL | Anomaly detected and broadcast to dashboard in real-time |

---

## 🔧 Troubleshooting

| Error | Fix |
|---|---|
| `Cannot connect to Docker daemon` | `export DOCKER_HOST=unix:///Users/<n>/.docker/run/docker.sock` |
| `ModuleNotFoundError: cache` | Run from project root, not inside a subfolder |
| `ModuleNotFoundError: cache_common` | `cache_common.py` must be inside `cache/` not at root |
| `uvloop` install error on Windows | Skip uvloop — `pip install fastapi uvicorn docker requests pydantic psutil` |
| Dashboard shows old state after restart | Delete snapshot: `rm /tmp/rcsce_state.json` |
| Workers marked dead immediately | Run `python run_scheduler.py` from project root |
| Scheduler not receiving jobs | Ensure scheduler started before primary master (port 9010 must be up) |
| Cache entries show 0 in dashboard | Hit `GET /stats` on port 9001 — entries only count after first scan completes |

---

## 📐 Design Decisions

**HTTP REST instead of gRPC** — The proposal referenced gRPC for cache and worker communication. We chose FastAPI's native HTTP stack because it integrates directly with asyncio, eliminates protobuf compilation from the build, and the consistent hashing + LRU logic gRPC would have served is fully implemented at the application layer. The transport is an implementation detail; the distributed systems concepts are identical.

**Write-through cache replication** — Scan results are written to all cache nodes on every PUT, not just the hash-responsible node. This ensures lookups succeed even during ring rebalancing or node restarts, at the cost of slightly more write traffic (acceptable given read-heavy workload).

**Critical-only auto-failover** — Only containers explicitly marked via `POST /containers/{id}/critical` trigger replica creation on death. This prevents runaway replica loops when doing `docker rm -f` during development or chaos testing.

---

*Built for Advanced Operating Systems — TAMU-CC · Spring 2026*