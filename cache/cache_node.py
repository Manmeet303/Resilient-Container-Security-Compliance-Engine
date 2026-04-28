"""
cache/cache_node.py
───────────────────
FastAPI cache node — HTTP interface for a single distributed cache shard.

New endpoints vs original
──────────────────────────
PUT  /cache/{layer_hash}   – update (overwrite) an existing entry's scan
                             result and reset its TTL.
DELETE /cache/{layer_hash} – invalidate (hard-delete from LRU + DB).
GET  /cache/stats          – extended stats: hit/miss ratios, DB counts.
POST /cache/purge          – manually trigger expired-entry cleanup in DB.
"""

import logging
import os
import threading
import time

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Show recovery logs clearly in the terminal
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)

from cache.cache_common import LayerScanCache
from cache.storage.cache_db import CacheDB

app = FastAPI(title="Distributed Cache Node")

CACHE_CAPACITY    = int(os.getenv("CACHE_CAPACITY",    "1000"))
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "3600"))
NODE_ID           = os.getenv("NODE_ID",                "cache-node-1")
DB_PATH           = os.getenv("CACHE_DB_PATH",          "cache_store.db")
PURGE_INTERVAL    = int(os.getenv("CACHE_PURGE_INTERVAL_SECONDS", "300"))

db    = CacheDB(db_path=DB_PATH)
cache = LayerScanCache(capacity=CACHE_CAPACITY, ttl_seconds=CACHE_TTL_SECONDS, db=db)


# ── Background expired-entry purge ──────────────────────────────────── #

def _purge_loop():
    while True:
        time.sleep(PURGE_INTERVAL)
        db.purge_expired()

threading.Thread(target=_purge_loop, daemon=True, name="cache-purge").start()


# ── Request / response models ─────────────────────────────────────────── #

class CachePutRequest(BaseModel):
    layer_hash:  str
    scan_result: dict


class CacheUpdateRequest(BaseModel):
    scan_result: dict


class CacheGetResponse(BaseModel):
    hit:         bool
    layer_hash:  str
    scan_result: dict | None = None
    node_id:     str


# ── Endpoints ─────────────────────────────────────────────────────────── #

@app.get("/health")
def health():
    return {"status": "ok", "node_id": NODE_ID, "cache_stats": cache.stats()}


@app.get("/cache/stats")
def stats():
    """Extended stats: hit/miss ratios, LRU vs DB hits, DB entry counts."""
    return {"node_id": NODE_ID, **cache.stats()}


@app.get("/cache/{layer_hash}", response_model=CacheGetResponse)
def get_cache(layer_hash: str):
    result = cache.get(layer_hash)
    if result is None:
        return CacheGetResponse(hit=False, layer_hash=layer_hash, node_id=NODE_ID)
    return CacheGetResponse(hit=True, layer_hash=layer_hash, scan_result=result, node_id=NODE_ID)


@app.post("/cache")
def put_cache(request: CachePutRequest):
    """Store a new scan result.  Idempotent — silently replaces on key clash."""
    cache.put(request.layer_hash, request.scan_result)
    return {
        "status":      "stored",
        "layer_hash":  request.layer_hash,
        "node_id":     NODE_ID,
        "cache_stats": cache.stats(),
    }


@app.put("/cache/{layer_hash}")
def update_cache(layer_hash: str, request: CacheUpdateRequest):
    """
    Overwrite an existing scan result and reset its TTL.
    Use this when a worker produces a fresher scan report for a layer
    that is already cached (e.g. after a forced re-scan).
    Returns 404 if the key is not found in either LRU or DB.
    """
    updated = cache.update(layer_hash, request.scan_result)
    if not updated:
        raise HTTPException(
            status_code=404,
            detail=f"layer_hash '{layer_hash}' not found in cache"
        )
    return {
        "status":      "updated",
        "layer_hash":  layer_hash,
        "node_id":     NODE_ID,
        "cache_stats": cache.stats(),
    }


@app.delete("/cache/{layer_hash}")
def delete_cache(layer_hash: str):
    """Invalidate an entry from both the in-memory LRU and the DB."""
    cache.invalidate(layer_hash)
    return {"status": "invalidated", "layer_hash": layer_hash, "node_id": NODE_ID}


@app.post("/cache/purge")
def purge_expired():
    """Manually trigger a sweep of expired rows in the DB."""
    deleted = db.purge_expired()
    return {"status": "purged", "expired_entries_removed": deleted, "node_id": NODE_ID}