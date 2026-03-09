import time
from shared.utils.logger import get_logger

logger = get_logger("scheduler.worker_registry")


class WorkerRegistry:

    def __init__(self):

        self.workers = {}

    def register(self, worker_id):

        self.workers[worker_id] = {
            "last_heartbeat": time.time(),
            "status": "alive",
            "load": 0
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

        for w, info in self.workers.items():

            if info["status"] == "alive":
                alive.append((w, info["load"]))

        alive.sort(key=lambda x: x[1])

        return [w[0] for w in alive]

    def mark_dead(self, worker_id):

        if worker_id in self.workers:
            self.workers[worker_id]["status"] = "dead"

            logger.warning(f"Worker marked dead: {worker_id}")