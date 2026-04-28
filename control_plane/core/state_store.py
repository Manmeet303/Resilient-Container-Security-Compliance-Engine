import json
import os
import threading
from datetime import datetime
from typing import Any, Dict, List

from shared.utils.logger import get_logger

logger = get_logger("control_plane.state_store")

# Windows-safe state file path.
# Old path "/tmp/rcsce_state.json" causes problems on Windows.
PERSIST_PATH = os.path.join(os.getcwd(), "rcsce_state.json")


class StateStore:

    def __init__(self):
        self._lock = threading.Lock()
        self._containers: Dict[str, Dict[str, Any]] = {}
        self._workers: Dict[str, Dict[str, Any]] = {}
        self._critical_containers: set = set()
        self._audit_log: List[Dict[str, Any]] = []
        self._queue_depth: int = 0
        self._cache_hits: int = 0
        self._cache_misses: int = 0

        self.load_from_disk()

    # ── Containers ─────────────────────────────────────────────────────────────

    def upsert_container(self, container_id, data):
        with self._lock:
            self._containers[container_id] = {
                **self._containers.get(container_id, {}),
                **data,
                "updated_at": datetime.utcnow().isoformat(),
            }
        self.save_to_disk()

    def remove_container(self, container_id):
        with self._lock:
            self._containers.pop(container_id, None)
        self.save_to_disk()

    def get_all_containers(self):
        with self._lock:
            return list(self._containers.values())

    def get_container(self, container_id):
        with self._lock:
            return self._containers.get(container_id)

    # ── Critical containers ────────────────────────────────────────────────────

    def mark_critical(self, container_id):
        with self._lock:
            self._critical_containers.add(container_id)
            if container_id in self._containers:
                self._containers[container_id]["is_critical"] = True
        self.save_to_disk()

    def is_critical(self, container_id):
        with self._lock:
            return container_id in self._critical_containers

    # ── Workers ────────────────────────────────────────────────────────────────

    def upsert_worker(self, worker_id, data):
        with self._lock:
            self._workers[worker_id] = {
                **self._workers.get(worker_id, {}),
                **data,
                "worker_id": worker_id,
                "last_seen": datetime.utcnow().isoformat(),
            }
        self.save_to_disk()

    def get_all_workers(self):
        with self._lock:
            return list(self._workers.values())

    def remove_worker(self, worker_id: str):
        """
        Permanently delete one worker record.
        """
        with self._lock:
            self._workers.pop(worker_id, None)
        self.save_to_disk()

    def clear_all_workers(self):
        """
        Delete ALL worker records.

        Layman meaning:
        When we restart the project, remove old dead/ghost worker cards
        so the dashboard does not keep increasing from 2 to 4 to 8 to 10.
        """
        with self._lock:
            count = len(self._workers)
            self._workers = {}
        self.save_to_disk()
        return count

    def mark_worker_dead(self, worker_id: str):
        """
        Keep worker visible but mark it dead.
        This is useful during demo when a live worker fails.
        """
        with self._lock:
            self._workers[worker_id] = {
                **self._workers.get(worker_id, {}),
                "worker_id": worker_id,
                "status": "dead",
                "load": 0,
                "last_seen": datetime.utcnow().isoformat(),
            }
        self.save_to_disk()

    # ── Queue depth ────────────────────────────────────────────────────────────

    def set_queue_depth(self, depth):
        with self._lock:
            self._queue_depth = depth
        self.save_to_disk()

    def queue_depth(self):
        with self._lock:
            return self._queue_depth

    # ── Cache stats ────────────────────────────────────────────────────────────

    def record_cache_event(self, hit: bool):
        with self._lock:
            if hit:
                self._cache_hits += 1
            else:
                self._cache_misses += 1
        self.save_to_disk()

    def get_cache_stats(self):
        with self._lock:
            hits = self._cache_hits
            misses = self._cache_misses
            total = hits + misses
            return {
                "hits": hits,
                "misses": misses,
                "hit_rate": round(hits / total * 100) if total > 0 else 0,
            }

    # ── Audit log ──────────────────────────────────────────────────────────────

    def append_audit(self, event):
        with self._lock:
            self._audit_log.append({
                **event,
                "logged_at": datetime.utcnow().isoformat(),
            })

            if len(self._audit_log) > 200:
                self._audit_log = self._audit_log[-200:]

        self.save_to_disk()

    def get_audit_log(self):
        with self._lock:
            return list(self._audit_log[-200:])

    # ── Persistence ────────────────────────────────────────────────────────────

    def save_to_disk(self):
        """
        Save current state to rcsce_state.json.
        """
        try:
            with self._lock:
                snapshot = {
                    "containers": dict(self._containers),
                    "workers": dict(self._workers),
                    "critical_containers": list(self._critical_containers),
                    "audit_log": list(self._audit_log[-200:]),
                    "queue_depth": self._queue_depth,
                    "cache_hits": self._cache_hits,
                    "cache_misses": self._cache_misses,
                    "saved_at": datetime.utcnow().isoformat(),
                }

            with open(PERSIST_PATH, "w") as f:
                json.dump(snapshot, f, default=str, indent=2)

        except Exception as exc:
            logger.warning(f"StateStore: could not save to disk: {exc}")

    def load_from_disk(self):
        """
        Load old state from rcsce_state.json.

        Containers/audit can survive restart, but workers will be cleared
        by control_plane/api/main.py on startup.
        """
        if not os.path.exists(PERSIST_PATH):
            logger.info("StateStore: no snapshot found — starting fresh.")
            return

        try:
            with open(PERSIST_PATH) as f:
                snapshot = json.load(f)

            with self._lock:
                self._containers = snapshot.get("containers", {})
                self._workers = snapshot.get("workers", {})
                self._critical_containers = set(snapshot.get("critical_containers", []))
                self._audit_log = snapshot.get("audit_log", [])
                self._queue_depth = snapshot.get("queue_depth", 0)
                self._cache_hits = snapshot.get("cache_hits", 0)
                self._cache_misses = snapshot.get("cache_misses", 0)

            saved_at = snapshot.get("saved_at", "unknown")
            logger.info(
                f"StateStore: restored from disk snapshot "
                f"({len(self._containers)} containers, "
                f"{len(self._workers)} workers, "
                f"{len(self._audit_log)} audit entries, "
                f"saved at {saved_at})"
            )

        except Exception as exc:
            logger.warning(f"StateStore: could not restore from disk: {exc}")

    def clear_disk_snapshot(self):
        """
        Delete saved state file.
        """
        try:
            if os.path.exists(PERSIST_PATH):
                os.remove(PERSIST_PATH)
                logger.info("StateStore: disk snapshot cleared.")
        except Exception as exc:
            logger.warning(f"StateStore: could not clear snapshot: {exc}")