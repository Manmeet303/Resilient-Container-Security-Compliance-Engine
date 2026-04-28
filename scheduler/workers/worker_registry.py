import time
from shared.utils.logger import get_logger

logger = get_logger("scheduler.worker_registry")


class WorkerRegistry:

    def __init__(self):
        self.workers = {}

    def register(self, worker_id, node=None):
        old = self.workers.get(worker_id, {})

        self.workers[worker_id] = {
            "last_heartbeat": time.time(),
            "status": "alive",
            "load": old.get("load", 0),

            # NEW METRICS
            "jobs_assigned": old.get("jobs_assigned", 0),
            "jobs_completed": old.get("jobs_completed", 0),
            "events_assigned": old.get("events_assigned", old.get("jobs_assigned", 0)),
            "events_completed": old.get("events_completed", old.get("jobs_completed", 0)),

            "node": node,
        }

        logger.info(f"Worker registered: {worker_id}")

    def heartbeat(self, worker_id):
        if worker_id in self.workers:
            self.workers[worker_id]["last_heartbeat"] = time.time()

    def update_load(self, worker_id, load):
        if worker_id in self.workers:
            self.workers[worker_id]["load"] = max(0, int(load))

    def mark_assigned(self, worker_id):
        """
        Called when dispatcher gives a job to a worker.
        This increases:
        - Current Load
        - Jobs Assigned
        - Events Assigned
        """
        if worker_id in self.workers:
            self.workers[worker_id]["load"] = self.workers[worker_id].get("load", 0) + 1
            self.workers[worker_id]["jobs_assigned"] = self.workers[worker_id].get("jobs_assigned", 0) + 1
            self.workers[worker_id]["events_assigned"] = self.workers[worker_id].get("events_assigned", 0) + 1

    def mark_completed(self, worker_id):
        """
        Called when worker finishes a job.
        This increases:
        - Jobs Completed
        - Events Completed

        And decreases:
        - Current Load
        """
        if worker_id in self.workers:
            self.workers[worker_id]["load"] = max(0, self.workers[worker_id].get("load", 0) - 1)
            self.workers[worker_id]["jobs_completed"] = self.workers[worker_id].get("jobs_completed", 0) + 1
            self.workers[worker_id]["events_completed"] = self.workers[worker_id].get("events_completed", 0) + 1

    def mark_failed_or_requeued(self, worker_id):
        """
        Called when worker dies/fails before completing the task.
        The job is not completed, but load should go down.
        """
        if worker_id in self.workers:
            self.workers[worker_id]["load"] = max(0, self.workers[worker_id].get("load", 0) - 1)

    def available_workers(self):
        alive = []

        for worker_id, info in self.workers.items():
            if info["status"] == "alive" and info.get("node") is not None:
                alive.append((worker_id, info.get("load", 0)))

        alive.sort(key=lambda x: x[1])
        return [worker_id for worker_id, _ in alive]

    def get_worker(self, worker_id):
        if worker_id in self.workers:
            return self.workers[worker_id].get("node")
        return None

    def mark_dead(self, worker_id):
        if worker_id in self.workers:
            self.workers[worker_id]["status"] = "dead"
            self.workers[worker_id]["load"] = 0
            logger.warning(f"Worker marked dead: {worker_id}")