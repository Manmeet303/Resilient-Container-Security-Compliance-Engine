import time
from shared.utils.logger import get_logger

logger = get_logger("scheduler.worker_registry")


class WorkerRegistry:

    def __init__(self):
        self.workers = {}

    def register(self, worker_id, node=None):
        self.workers[worker_id] = {
            "last_heartbeat": time.time(),
            "status": "alive",
            "load": 0,
            "node": node,
        }
        logger.info(f"Worker registered: {worker_id}")

    def heartbeat(self, worker_id):
        if worker_id in self.workers:
            self.workers[worker_id]["last_heartbeat"] = time.time()

    def update_load(self, worker_id, load):
        if worker_id in self.workers:
            self.workers[worker_id]["load"] = load

    def available_workers(self):
        alive = []

        for worker_id, info in self.workers.items():
            if info["status"] == "alive" and info.get("node") is not None:
                alive.append((worker_id, info["load"]))

        alive.sort(key=lambda x: x[1])
        return [worker_id for worker_id, _ in alive]

    def get_worker(self, worker_id):
        if worker_id in self.workers:
            return self.workers[worker_id].get("node")
        return None

    def mark_dead(self, worker_id):
        if worker_id in self.workers:
            self.workers[worker_id]["status"] = "dead"
            logger.warning(f"Worker marked dead: {worker_id}")