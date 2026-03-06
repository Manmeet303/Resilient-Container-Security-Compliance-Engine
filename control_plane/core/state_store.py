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
