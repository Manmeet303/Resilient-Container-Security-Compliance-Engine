import asyncio
from datetime import datetime

import docker
from shared.utils.logger import get_logger

logger = get_logger("control_plane.log_monitor")

# The trigger words we are looking for in the logs
CRITICAL_KEYWORDS = [
    "error", "fatal", "exception", "traceback", 
    "unauthorized", "failed password", "access denied", 
    "segmentation fault"
]

class LogMonitor:
    def __init__(self, state_store, ws_manager):
        self.state_store = state_store
        self.ws_manager = ws_manager
        self.active_streams = {}
        try:
            self.client = docker.from_env()
        except Exception as exc:
            logger.error(f"LogMonitor Docker client failed: {exc}")
            self.client = None

    async def start_monitoring(self, container_id: str, container_name: str, image_name: str):
        if not self.client:
            return

        # THE EXCLUSION RULE: Do not monitor our own infrastructure
        # Adjust "rcsce-" to whatever prefix your docker-compose uses
        if container_name.startswith("rcsce-") or "master-node" in container_name:
            return

        if container_id in self.active_streams:
            return

        logger.info(f"Attaching log monitor to container: {container_name}")
        task = asyncio.create_task(self._stream_logs(container_id, container_name, image_name))
        self.active_streams[container_id] = task

    async def stop_monitoring(self, container_id: str):
        task = self.active_streams.pop(container_id, None)
        if task:
            task.cancel()
            logger.info(f"Detached log monitor from container: {container_id}")

    async def _stream_logs(self, container_id: str, container_name: str, image_name: str):
        loop = asyncio.get_event_loop()
        try:
            container = self.client.containers.get(container_id)
            log_stream = container.logs(stream=True, follow=True, tail=0)

            while True:
                # Fetch the next log line in a background thread so we don't freeze FastAPI!
                chunk = await loop.run_in_executor(None, next, log_stream, None)
                
                # If chunk is None, the container stopped and the stream ended
                if chunk is None:
                    break

                line = chunk.decode("utf-8", errors="ignore").strip()
                if not line:
                    continue
                
                lower_line = line.lower()
                for keyword in CRITICAL_KEYWORDS:
                    if keyword in lower_line:
                        await self._broadcast_anomaly(
                            container_id, container_name, image_name, keyword, line
                        )
                        break

        except asyncio.CancelledError:
            logger.info(f"Log monitor cancelled for {container_name}")
        except docker.errors.NotFound:
            pass  
        except Exception as exc:
            logger.warning(f"Log stream dropped for {container_name}: {exc}")
        finally:
            self.active_streams.pop(container_id, None)

    async def _broadcast_anomaly(self, container_id, container_name, image_name, keyword, line):
        logger.warning(f"ANOMALY in {container_name}: {keyword.upper()}")
        
        event_payload = {
            "event_type": "anomaly_detected",
            "container_id": container_id,
            "container_name": container_name,
            "image_name": image_name,
            "keyword": keyword,
            "log_line": line[:150],  # Truncate so we don't spam the UI payload
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        # Save to Audit Log
        self.state_store.append_audit({
            **event_payload,
            "action": "anomaly_detected",
        })
        
        # Broadcast live to the dashboard
        await self.ws_manager.broadcast(event_payload)