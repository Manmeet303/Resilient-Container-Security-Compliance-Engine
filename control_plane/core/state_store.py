# import json
# import os
# import threading
# import sqlite3

# DB_PATH = "rcsce.db"
# from datetime import datetime
# from typing import Any, Dict, List

# from shared.utils.logger import get_logger

# logger = get_logger("control_plane.state_store")

# # Persist state here — survives uvicorn restarts and is readable by standby
# PERSIST_PATH = "/tmp/rcsce_state.json"


# class StateStore:

#     def __init__(self):
#         self._lock = threading.Lock()
#         self._containers: Dict[str, Dict[str, Any]] = {}
#         self._workers: Dict[str, Dict[str, Any]] = {}
#         self._critical_containers: set = set()
#         self._audit_log: List[Dict[str, Any]] = []
#         self._queue_depth:   int = 0
#         self._cache_hits:    int = 0
#         self._cache_misses:  int = 0

#         # Load existing state from disk on startup
#         # This means containers survive uvicorn --reload and master restarts
#         self.load_from_disk()

#         # ------------------------------------------------------------------
#         def init_db(self):
#     conn = sqlite3.connect(DB_PATH)
#     cursor = conn.cursor()

#     cursor.execute("""
#     CREATE TABLE IF NOT EXISTS containers (
#         id TEXT PRIMARY KEY,
#         name TEXT,
#         image TEXT,
#         status TEXT,
#         updated_at TEXT
#     )
#     """)

#     conn.commit()
#     conn.close()
#     # --------------------------------------------------------------------------

#     # ── Containers ─────────────────────────────────────────────────────────────

#     def upsert_container(self, container_id, data):
#         with self._lock:
#             self._containers[container_id] = {
#                 **self._containers.get(container_id, {}),
#                 **data,
#                 "updated_at": datetime.utcnow().isoformat(),
#             }
#         self.save_to_disk()

#     def remove_container(self, container_id):
#         with self._lock:
#             self._containers.pop(container_id, None)
#         self.save_to_disk()

#     def get_all_containers(self):
#         with self._lock:
#             return list(self._containers.values())

#     def get_container(self, container_id):
#         with self._lock:
#             return self._containers.get(container_id)

#     # ── Critical containers ────────────────────────────────────────────────────

#     def mark_critical(self, container_id):
#         with self._lock:
#             self._critical_containers.add(container_id)
#             if container_id in self._containers:
#                 self._containers[container_id]["is_critical"] = True
#         self.save_to_disk()

#     def is_critical(self, container_id):
#         with self._lock:
#             return container_id in self._critical_containers

#     # ── Workers ────────────────────────────────────────────────────────────────

#     def upsert_worker(self, worker_id, data):
#         with self._lock:
#             self._workers[worker_id] = {
#                 **self._workers.get(worker_id, {}),
#                 **data,
#                 "last_seen": datetime.utcnow().isoformat(),
#             }
#         self.save_to_disk()

#     def get_all_workers(self):
#         with self._lock:
#             return list(self._workers.values())

#     # ── Queue depth ────────────────────────────────────────────────────────────

#     def set_queue_depth(self, depth):
#         with self._lock:
#             self._queue_depth = depth
#         self.save_to_disk()

#     def queue_depth(self):
#         with self._lock:
#             return self._queue_depth

#     # ── Cache stats ────────────────────────────────────────────────────────────────

#     def record_cache_event(self, hit: bool):
#         """Track cache hits and misses for dashboard Cache Performance panel."""
#         with self._lock:
#             if hit:
#                 self._cache_hits += 1
#             else:
#                 self._cache_misses += 1
#         self.save_to_disk()

#     def get_cache_stats(self):
#         with self._lock:
#             hits   = self._cache_hits
#             misses = self._cache_misses
#             total  = hits + misses
#             return {
#                 "hits":      hits,
#                 "misses":    misses,
#                 "hit_rate":  round(hits / total * 100) if total > 0 else 0,
#             }
#     # ── Audit log ──────────────────────────────────────────────────────────────

#     def append_audit(self, event):
#         with self._lock:
#             self._audit_log.append({
#                 **event,
#                 "logged_at": datetime.utcnow().isoformat(),
#             })
#             # Keep only last 200 entries in memory
#             if len(self._audit_log) > 200:
#                 self._audit_log = self._audit_log[-200:]
#         self.save_to_disk()

#     def get_audit_log(self):
#         with self._lock:
#             return list(self._audit_log[-200:])

#     # ── Persistence ────────────────────────────────────────────────────────────

#     def save_to_disk(self):
#         """
#         Write current state to disk as JSON.
#         Called after every mutation so state always reflects latest.
#         Standby node reads this file to mirror state.
#         """
#         try:
#             with self._lock:
#                 snapshot = {
#                     "containers":          dict(self._containers),
#                     "workers":             dict(self._workers),
#                     "critical_containers": list(self._critical_containers),
#                     "audit_log":           list(self._audit_log[-200:]),
#                     "queue_depth":         self._queue_depth,
#                     "cache_hits":          self._cache_hits,
#                     "cache_misses":        self._cache_misses,
#                     "saved_at":            datetime.utcnow().isoformat(),
#                 }
#             with open(PERSIST_PATH, "w") as f:
#                 json.dump(snapshot, f, default=str, indent=2)
#         except Exception as exc:
#             logger.warning(f"StateStore: could not save to disk: {exc}")

#     def load_from_disk(self):
#         """
#         Restore state from disk snapshot on startup.
#         Called once in __init__ — silently skips if no file exists.
#         """
#         if not os.path.exists(PERSIST_PATH):
#             logger.info("StateStore: no snapshot found — starting fresh.")
#             return
#         try:
#             with open(PERSIST_PATH) as f:
#                 snapshot = json.load(f)
#             with self._lock:
#                 self._containers         = snapshot.get("containers", {})
#                 self._workers            = snapshot.get("workers", {})
#                 self._critical_containers = set(snapshot.get("critical_containers", []))
#                 self._audit_log          = snapshot.get("audit_log", [])
#                 self._queue_depth        = snapshot.get("queue_depth", 0)
#                 self._cache_hits         = snapshot.get("cache_hits", 0)
#                 self._cache_misses       = snapshot.get("cache_misses", 0)
#             saved_at = snapshot.get("saved_at", "unknown")
#             logger.info(
#                 f"StateStore: restored from disk snapshot "
#                 f"({len(self._containers)} containers, "
#                 f"{len(self._audit_log)} audit entries, "
#                 f"saved at {saved_at})"
#             )
#         except Exception as exc:
#             logger.warning(f"StateStore: could not restore from disk: {exc}")

#     def clear_disk_snapshot(self):
#         """Delete the snapshot file — useful for clean test runs."""
#         try:
#             if os.path.exists(PERSIST_PATH):
#                 os.remove(PERSIST_PATH)
#                 logger.info("StateStore: disk snapshot cleared.")
#         except Exception as exc:
#             logger.warning(f"StateStore: could not clear snapshot: {exc}")






import json
import os
import threading
import sqlite3
from datetime import datetime
from typing import Any, Dict, List

from shared.utils.logger import get_logger

logger = get_logger("control_plane.state_store")

PERSIST_PATH = "/tmp/rcsce_state.json"
DB_PATH = "rcsce.db"


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

        self.init_db()
        self.load_from_disk()

    # ── SQLite Database ───────────────────────────────────────────────────────

    def init_db(self):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS containers (
            id TEXT PRIMARY KEY,
            name TEXT,
            image TEXT,
            status TEXT,
            is_critical INTEGER DEFAULT 0,
            updated_at TEXT
        )
        """)

        conn.commit()
        conn.close()

    def save_container_to_db(self, container_id: str, container_data: Dict[str, Any]):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
        INSERT OR REPLACE INTO containers
        (id, name, image, status, is_critical, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (
            container_id,
            container_data.get("name"),
            container_data.get("image"),
            container_data.get("status"),
            1 if container_data.get("is_critical") else 0,
            container_data.get("updated_at"),
        ))

        conn.commit()
        conn.close()

    def delete_container_from_db(self, container_id: str):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("DELETE FROM containers WHERE id = ?", (container_id,))

        conn.commit()
        conn.close()

    # ── Containers ─────────────────────────────────────────────────────────────

    def upsert_container(self, container_id, data):
        with self._lock:
            updated_data = {
                **self._containers.get(container_id, {}),
                **data,
                "updated_at": datetime.utcnow().isoformat(),
            }

            self._containers[container_id] = updated_data

        self.save_to_disk()
        self.save_container_to_db(container_id, updated_data)

    def remove_container(self, container_id):
        with self._lock:
            self._containers.pop(container_id, None)

        self.save_to_disk()
        self.delete_container_from_db(container_id)

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
                updated_data = self._containers[container_id]
            else:
                updated_data = None

        self.save_to_disk()

        if updated_data:
            self.save_container_to_db(container_id, updated_data)

    def is_critical(self, container_id):
        with self._lock:
            return container_id in self._critical_containers

    # ── Workers ────────────────────────────────────────────────────────────────

    def upsert_worker(self, worker_id, data):
        with self._lock:
            self._workers[worker_id] = {
                **self._workers.get(worker_id, {}),
                **data,
                "last_seen": datetime.utcnow().isoformat(),
            }

        self.save_to_disk()

    def get_all_workers(self):
        with self._lock:
            return list(self._workers.values())

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

            for container_id, container_data in self._containers.items():
                self.save_container_to_db(container_id, container_data)

            saved_at = snapshot.get("saved_at", "unknown")
            logger.info(
                f"StateStore: restored from disk snapshot "
                f"({len(self._containers)} containers, "
                f"{len(self._audit_log)} audit entries, "
                f"saved at {saved_at})"
            )

        except Exception as exc:
            logger.warning(f"StateStore: could not restore from disk: {exc}")

    def clear_disk_snapshot(self):
        try:
            if os.path.exists(PERSIST_PATH):
                os.remove(PERSIST_PATH)
                logger.info("StateStore: disk snapshot cleared.")

        except Exception as exc:
            logger.warning(f"StateStore: could not clear snapshot: {exc}")