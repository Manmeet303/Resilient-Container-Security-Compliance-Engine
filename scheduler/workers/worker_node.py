import asyncio
import json
import uuid
from datetime import datetime

import httpx

from shared.utils.logger import get_logger

logger = get_logger("scheduler.worker")

CONTROL_PLANE_URL = "http://localhost:9000"


class WorkerNode:

    def __init__(self, registry):
        self.registry = registry
        self.worker_id = str(uuid.uuid4())
        self.jobs_completed = 0

        self.registry.register(self.worker_id, self)

        logger.info(f"WorkerNode created: {self.worker_id[:8]}...")

    async def heartbeat_loop(self):
        ipc_counter = 0

        async with httpx.AsyncClient() as client:
            while True:
                self.registry.heartbeat(self.worker_id)

                ipc_counter += 1
                if ipc_counter >= 3:
                    ipc_counter = 0
                    await self._report_to_control_plane(client)

                await asyncio.sleep(2)

    async def _report_to_control_plane(self, client: httpx.AsyncClient = None):
        close_client = False

        if client is None:
            client = httpx.AsyncClient()
            close_client = True

        try:
            info = self.registry.workers.get(self.worker_id, {})

            await client.post(
                f"{CONTROL_PLANE_URL}/internal/workers/heartbeat",
                json={
                    "worker_id": self.worker_id,
                    "status": info.get("status", "alive"),
                    "load": info.get("load", 0),

                    # NEW METRICS SENT TO DASHBOARD
                    "jobs_assigned": info.get("jobs_assigned", 0),
                    "jobs_completed": info.get("jobs_completed", 0),
                    "events_assigned": info.get("events_assigned", 0),
                    "events_completed": info.get("events_completed", 0),
                },
                timeout=2.0,
            )

            logger.info(
                f"Worker {self.worker_id[:8]} → control plane "
                f"(load={info.get('load', 0)}, "
                f"assigned={info.get('jobs_assigned', 0)}, "
                f"completed={info.get('jobs_completed', 0)})"
            )

        except Exception as exc:
            logger.warning(f"Worker {self.worker_id[:8]} IPC failed: {exc}")

        finally:
            if close_client:
                await client.aclose()

    async def process_job(self, job):
        image_name = job.get("image_name", "unknown")

        logger.info(
            f"Worker {self.worker_id[:8]} scanning "
            f"job {job['job_id'][:8]} | image={image_name}"
        )

        vuln_counts = {
            "CRITICAL": 0,
            "HIGH": 0,
            "MEDIUM": 0,
            "LOW": 0,
        }

        scan_status = "scan_complete"

        try:
            process = await asyncio.create_subprocess_exec(
                "trivy",
                "image",
                "-q",
                "-f",
                "json",
                "--timeout",
                "60s",
                image_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=90,
            )

            if process.returncode == 0 and stdout:
                scan_data = json.loads(stdout.decode())

                for result in scan_data.get("Results", []):
                    for vuln in result.get("Vulnerabilities") or []:
                        sev = vuln.get("Severity", "UNKNOWN")

                        if sev in vuln_counts:
                            vuln_counts[sev] += 1

                logger.info(
                    f"Trivy scan complete for {image_name}: "
                    f"C={vuln_counts['CRITICAL']} "
                    f"H={vuln_counts['HIGH']}"
                )

            else:
                raise RuntimeError(f"Trivy exit={process.returncode}")

        except FileNotFoundError:
            logger.warning(f"Trivy not found — using mock scan for {image_name}")

            import random

            vuln_counts = {
                "CRITICAL": random.randint(0, 3),
                "HIGH": random.randint(1, 8),
                "MEDIUM": random.randint(2, 15),
                "LOW": random.randint(5, 30),
            }

            scan_status = "mock_scan_complete"

            # This delay helps you show the task actually running.
            await asyncio.sleep(2)

        except asyncio.TimeoutError:
            logger.error(f"Trivy scan timed out for {image_name}")
            scan_status = "scan_timeout"
            await asyncio.sleep(1)

        except Exception as exc:
            logger.error(f"Scan error for {image_name}: {exc}")
            scan_status = "scan_failed"

        return {
            "status": scan_status,
            "worker_id": self.worker_id,
            "job_id": job["job_id"],
            "image_name": image_name,
            "vulnerabilities": vuln_counts,
            "timestamp": datetime.utcnow().isoformat(),
        }