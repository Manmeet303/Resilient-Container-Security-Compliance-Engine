from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os

from cache.cache_common import LayerScanCache

app = FastAPI(title="Distributed Cache Node")

CACHE_CAPACITY = int(os.getenv("CACHE_CAPACITY", "1000"))
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "3600"))
NODE_ID = os.getenv("NODE_ID", "cache-node-1")

cache = LayerScanCache(capacity=CACHE_CAPACITY, ttl_seconds=CACHE_TTL_SECONDS)


class CachePutRequest(BaseModel):
    layer_hash: str
    scan_result: dict


class CacheGetResponse(BaseModel):
    hit: bool
    layer_hash: str
    scan_result: dict | None = None
    node_id: str


@app.get("/health")
def health():
    return {
        "status": "ok",
        "node_id": NODE_ID,
        "cache_stats": cache.stats(),
    }


@app.get("/cache/{layer_hash}", response_model=CacheGetResponse)
def get_cache(layer_hash: str):
    result = cache.get(layer_hash)
    if result is None:
        return CacheGetResponse(
            hit=False,
            layer_hash=layer_hash,
            scan_result=None,
            node_id=NODE_ID,
        )

    return CacheGetResponse(
        hit=True,
        layer_hash=layer_hash,
        scan_result=result,
        node_id=NODE_ID,
    )


@app.post("/cache")
def put_cache(request: CachePutRequest):
    cache.put(request.layer_hash, request.scan_result)
    return {
        "status": "stored",
        "layer_hash": request.layer_hash,
        "node_id": NODE_ID,
        "cache_stats": cache.stats(),
    }


@app.delete("/cache/{layer_hash}")
def delete_cache(layer_hash: str):
    cache.lru.delete(layer_hash)
    return {
        "status": "deleted",
        "layer_hash": layer_hash,
        "node_id": NODE_ID,
    }