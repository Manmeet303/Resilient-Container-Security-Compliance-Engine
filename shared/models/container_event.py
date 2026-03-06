from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

class EventType(str, Enum):
    CONTAINER_START = "container_start"
    CONTAINER_DIE = "container_die"
    CONTAINER_STOP = "container_stop"
    CONTAINER_KILL = "container_kill"

class ContainerEvent(BaseModel):
    event_id: str
    event_type: EventType
    container_id: str
    container_name: str
    image_id: str
    image_name: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    is_critical: bool = False
    metadata: Dict[str, Any] = {}

class ScanJob(BaseModel):
    job_id: str
    container_id: str
    image_id: str
    image_name: str
    submitted_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = "pending"
    worker_id: Optional[str] = None
    result: Optional[Dict[str, Any]] = None

class CacheEntry(BaseModel):
    layer_hash: str
    scan_report: Dict[str, Any]
    cached_at: datetime = Field(default_factory=datetime.utcnow)
    hit_count: int = 0
    ttl_seconds: int = 3600

class NodeInfo(BaseModel):
    node_id: str
    role: str
    host: str
    port: int
    last_heartbeat: Optional[datetime] = None
    is_alive: bool = True
    cpu_load: float = 0.0
