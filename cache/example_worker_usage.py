from cache.worker_cache_client import DistributedCacheClient, build_layer_hash


def mock_trivy_scan(layer_hash: str) -> dict:
    return {
        "layer_hash": layer_hash,
        "scanner": "trivy",
        "critical": 1,
        "high": 2,
        "medium": 4,
        "low": 3,
        "status": "completed",
    }


def main():
    cache_nodes = [
        "http://localhost:9001",
        "http://localhost:9002",
    ]

    cache_client = DistributedCacheClient(cache_nodes)

    image_name = "nginx:1.18"
    layer_digest = "sha256:sample-layer-abc123"

    layer_hash = build_layer_hash(image_name, layer_digest)

    cache_response = cache_client.get_layer_scan(layer_hash)

    if cache_response.get("hit"):
        print("Cache hit")
        print("Using cached scan result:", cache_response["scan_result"])
    else:
        print("Cache miss")
        scan_result = mock_trivy_scan(layer_hash)
        store_response = cache_client.put_layer_scan(layer_hash, scan_result)
        print("Stored scan result:", store_response)


if __name__ == "__main__":
    main()