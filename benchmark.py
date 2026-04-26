#!/usr/bin/env python3
"""
RCSCE Benchmark — Scan Latency & CPU Savings from Distributed Caching
======================================================================
Runs two back-to-back experiments and prints a comparison table.

  Experiment A — Cold Scans (guaranteed MISS every time)
    Each container start has no cached data → simulates full Trivy scan.
    Uses unique per-run hash keys so live cache data never interferes.

  Experiment B — Cached Scans (guaranteed HIT every time)
    Cache pre-seeded with same keys → lookup returns instantly, no scan.

This mirrors exactly what the RCSCE dispatcher does:
    MISS → worker.process_job() → Trivy runs → 3-8s CPU burn → cache write
    HIT  → cache.get() → result returned → 0 scan overhead

Usage:
    python benchmark.py                          # 10 containers, nginx
    python benchmark.py --count 20 --image alpine
    python benchmark.py --count 10 --output results.csv

Requirements:
    pip install requests psutil
    Cache node running: NODE_ID=cache-node-1 uvicorn cache.cache_node:app --port 9001
"""

import argparse
import csv
import hashlib
import random
import statistics
import sys
import time
import uuid
from datetime import datetime, timezone

import psutil
import requests

CACHE_NODE   = "http://localhost:9001"
SCAN_MIN_S   = 2.5     # simulated Trivy min scan time (seconds)
SCAN_MAX_S   = 5.5     # simulated Trivy max scan time


# ── Cache helpers ─────────────────────────────────────────────────────────────

def check_cache_node():
    try:
        r = requests.get(f"{CACHE_NODE}/health", timeout=3)
        d = r.json()
        entries = d.get("cache_stats", {}).get("entries", "?")
        print(f"  Cache node OK — node_id={d.get('node_id')}  live_entries={entries}")
        return True
    except Exception as exc:
        print(f"  ERROR: Cache node not reachable at {CACHE_NODE}: {exc}")
        return False


def seed_cache(keys_and_results: dict):
    """Write pre-computed scan results into the cache node."""
    ok = 0
    for layer_hash, result in keys_and_results.items():
        try:
            r = requests.post(
                f"{CACHE_NODE}/cache",
                json={"layer_hash": layer_hash, "scan_result": result},
                timeout=3,
            )
            if r.status_code == 200:
                ok += 1
        except Exception:
            pass
    return ok


def cache_get(layer_hash: str) -> dict:
    try:
        r = requests.get(f"{CACHE_NODE}/cache/{layer_hash}", timeout=3)
        return r.json()
    except Exception:
        return {"hit": False}


def delete_bench_keys(layer_hashes: list):
    """Clean up only the keys this benchmark wrote — leaves live data alone."""
    for lh in layer_hashes:
        try:
            requests.delete(f"{CACHE_NODE}/cache/{lh}", timeout=3)
        except Exception:
            pass


# ── Key generation ────────────────────────────────────────────────────────────

def make_layer_hash(image_name: str, run_id: str, container_index: int) -> str:
    """
    Generate a benchmark-unique hash that will NEVER collide with live cache data.
    Mirrors the real build_layer_hash(image_name, layer_digest) logic exactly —
    just uses a run-specific digest so each experiment starts cold.
    """
    digest = f"bench-run-{run_id}-container-{container_index}"
    return hashlib.sha256(f"{image_name}:{digest}".encode()).hexdigest()


def make_mock_result(image_name: str) -> dict:
    return {
        "vulnerabilities": {
            "CRITICAL": random.randint(0, 3),
            "HIGH":     random.randint(1, 8),
            "MEDIUM":   random.randint(2, 15),
            "LOW":      random.randint(5, 30),
        },
        "status":     "mock_scan_complete",
        "image_name": image_name,
        "cached_at":  datetime.now(timezone.utc).isoformat(),
    }


# ── Core scan simulation ──────────────────────────────────────────────────────

def simulate_cold_scan(image_name: str, layer_hash: str) -> dict:
    """
    MISS path — guaranteed no cache entry exists for this hash.
    Simulates what a worker does: check cache → miss → run Trivy → write back.
    CPU measured via process cpu_times() diff (accurate, not noisy jitter).
    """
    proc = psutil.Process()

    cpu_before = sum(proc.cpu_times()[:2])   # user + system seconds
    t_start    = time.perf_counter()

    # 1. Cache lookup — will always MISS (unique key per run)
    cache_data = cache_get(layer_hash)
    hit = cache_data.get("hit", False)
    if hit:
        print(f"  WARNING: Expected MISS but got HIT for {layer_hash[:12]} — stale data?")

    # 2. Simulate Trivy scan: CPU-bound work + real sleep (mirrors actual scan)
    scan_s = random.uniform(SCAN_MIN_S, SCAN_MAX_S)
    _burn_cpu(scan_s)

    # 3. Write result back to cache (mirrors dispatcher cache write-back)
    result = make_mock_result(image_name)
    try:
        requests.post(
            f"{CACHE_NODE}/cache",
            json={"layer_hash": layer_hash, "scan_result": result},
            timeout=3,
        )
    except Exception:
        pass

    elapsed_ms = (time.perf_counter() - t_start) * 1000
    cpu_after  = sum(proc.cpu_times()[:2])
    cpu_s      = round(cpu_after - cpu_before, 3)

    return {
        "image":      image_name,
        "scan_type":  "miss",
        "elapsed_ms": round(elapsed_ms, 1),
        "cpu_s":      cpu_s,
    }


def simulate_cached_scan(image_name: str, layer_hash: str) -> dict:
    """
    HIT path — cache pre-seeded, returns instantly.
    Simulates what docker_listener does on a HIT: lookup → return → done.
    No Trivy invocation, no CPU burn.
    """
    proc = psutil.Process()

    cpu_before = sum(proc.cpu_times()[:2])
    t_start    = time.perf_counter()

    # 1. Cache lookup — will always HIT (pre-seeded above)
    cache_data = cache_get(layer_hash)
    hit = cache_data.get("hit", False)
    if not hit:
        print(f"  WARNING: Expected HIT but got MISS for {layer_hash[:12]} — seed failed?")

    # 2. No scan — result used directly from cache response
    _ = cache_data.get("scan_result", {})

    elapsed_ms = (time.perf_counter() - t_start) * 1000
    cpu_after  = sum(proc.cpu_times()[:2])
    cpu_s      = round(cpu_after - cpu_before, 3)

    return {
        "image":      image_name,
        "scan_type":  "hit",
        "elapsed_ms": round(elapsed_ms, 1),
        "cpu_s":      cpu_s,
    }


def _burn_cpu(duration_s: float):
    """
    Actually consume CPU for ~duration_s seconds.
    Mixes tight compute bursts with short sleeps to simulate Trivy's
    mixed workload (image layer decompression + CVE database matching).
    """
    deadline = time.perf_counter() + duration_s
    while time.perf_counter() < deadline:
        # 0.1s tight compute burst
        burst_end = time.perf_counter() + 0.1
        x = 1.0
        while time.perf_counter() < burst_end:
            x = (x * 1.0000001) % 1e9
        # 0.05s sleep (like Trivy's I/O waits between layers)
        time.sleep(0.05)


# ── Experiment runners ────────────────────────────────────────────────────────

def run_experiment_a(images: list, run_id: str) -> tuple:
    """Cold scans — guaranteed MISS for every container."""
    print(f"\n{'─'*62}")
    print(f"  Experiment A — Cold Scans  (MISS → Trivy → cache write-back)")
    print(f"  Every container start triggers a full vulnerability scan.")
    print(f"{'─'*62}")

    results    = []
    all_hashes = []

    for i, img in enumerate(images, 1):
        lh = make_layer_hash(img, run_id, i)
        all_hashes.append(lh)
        r   = simulate_cold_scan(img, lh)
        cpu = f"+{r['cpu_s']:.3f}s CPU"
        print(f"  [{i:>2}/{len(images)}] MISS | {img:<26} | {r['elapsed_ms']:>8.1f}ms | {cpu}")
        results.append(r)

    return results, all_hashes


def run_experiment_b(images: list, run_id: str) -> tuple:
    """Cached scans — pre-seed cache then guaranteed HIT for every container."""
    print(f"\n{'─'*62}")
    print(f"  Experiment B — Cached Scans  (HIT → instant return, no Trivy)")
    print(f"  Same images already seen — cache returns result in milliseconds.")
    print(f"{'─'*62}")

    # Use a different run_id suffix so B keys are distinct from A keys
    all_hashes = [make_layer_hash(img, run_id + "-b", i) for i, img in enumerate(images, 1)]
    seed_data  = {lh: make_mock_result(img) for lh, img in zip(all_hashes, images)}

    print(f"  Seeding cache with {len(seed_data)} key(s)...", end=" ")
    seeded = seed_cache(seed_data)
    print(f"{seeded} written.")

    results = []
    for i, (img, lh) in enumerate(zip(images, all_hashes), 1):
        r   = simulate_cached_scan(img, lh)
        cpu = f"+{r['cpu_s']:.3f}s CPU"
        print(f"  [{i:>2}/{len(images)}] HIT  | {img:<26} | {r['elapsed_ms']:>8.1f}ms | {cpu}")
        results.append(r)

    return results, all_hashes


# ── Stats ─────────────────────────────────────────────────────────────────────

def summarise(results: list) -> dict:
    times = [r["elapsed_ms"] for r in results]
    cpus  = [r["cpu_s"]      for r in results]
    hits  = sum(1 for r in results if r["scan_type"] == "hit")
    return {
        "count":       len(results),
        "hits":        hits,
        "misses":      len(results) - hits,
        "hit_rate":    round(hits / len(results) * 100) if results else 0,
        "total_ms":    round(sum(times), 1),
        "mean_ms":     round(statistics.mean(times), 1),
        "median_ms":   round(statistics.median(times), 1),
        "p95_ms":      round(sorted(times)[max(0, int(len(times) * 0.95) - 1)], 1),
        "total_cpu_s": round(sum(cpus), 3),
        "mean_cpu_s":  round(statistics.mean(cpus), 3),
    }


def print_comparison(cold: dict, cached: dict, count: int):
    time_saved_pct = round((1 - cached["total_ms"]   / cold["total_ms"])    * 100, 1) if cold["total_ms"]    > 0 else 0
    cpu_saved_pct  = round((1 - cached["total_cpu_s"] / cold["total_cpu_s"]) * 100, 1) if cold["total_cpu_s"] > 0 else 100
    time_saved_s   = round((cold["total_ms"] - cached["total_ms"]) / 1000, 1)

    print(f"\n{'═'*62}")
    print("  BENCHMARK RESULTS — RCSCE Distributed Cache")
    print(f"  {count} containers × nginx image")
    print(f"{'═'*62}")
    print(f"  {'Metric':<34} {'Cold (MISS)':>12} {'Cached (HIT)':>12}")
    print(f"  {'─'*58}")
    print(f"  {'Containers processed':<34} {cold['count']:>12} {cached['count']:>12}")
    print(f"  {'Cache outcome':<34} {'100% MISS':>12} {'100% HIT':>12}")
    print(f"  {'Total wall-clock time':<34} {str(cold['total_ms'])+'ms':>12} {str(cached['total_ms'])+'ms':>12}")
    print(f"  {'Mean latency / container':<34} {str(cold['mean_ms'])+'ms':>12} {str(cached['mean_ms'])+'ms':>12}")
    print(f"  {'Median latency':<34} {str(cold['median_ms'])+'ms':>12} {str(cached['median_ms'])+'ms':>12}")
    print(f"  {'P95 latency':<34} {str(cold['p95_ms'])+'ms':>12} {str(cached['p95_ms'])+'ms':>12}")
    print(f"  {'Total CPU time consumed':<34} {str(cold['total_cpu_s'])+'s':>12} {str(cached['total_cpu_s'])+'s':>12}")
    print(f"  {'Mean CPU / container':<34} {str(cold['mean_cpu_s'])+'s':>12} {str(cached['mean_cpu_s'])+'s':>12}")
    print(f"  {'─'*58}")
    print(f"  ✅ Wall-clock time saved : {time_saved_s}s  ({abs(time_saved_pct)}% faster)")
    print(f"  ✅ CPU time saved        : {cpu_saved_pct}% reduction")
    print(f"  ✅ Trivy scans skipped   : {cold['misses']} of {count} ({round(cold['misses']/count*100)}%)")
    print(f"{'═'*62}\n")


# ── CSV export ────────────────────────────────────────────────────────────────

def export_csv(cold_rows: list, cached_rows: list, path: str):
    fieldnames = ["experiment", "image", "scan_type", "elapsed_ms", "cpu_s"]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in cold_rows:
            w.writerow({"experiment": "cold_miss", **r})
        for r in cached_rows:
            w.writerow({"experiment": "cached_hit", **r})
    print(f"  Raw data exported → {path}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="RCSCE Cache Benchmark")
    parser.add_argument("--count",  type=int, default=10,      help="Containers to simulate (default: 10)")
    parser.add_argument("--image",  type=str, default="nginx",  help="Image name (default: nginx)")
    parser.add_argument("--output", type=str, default=None,     help="Optional CSV output path")
    args = parser.parse_args()

    print(f"\n{'═'*62}")
    print("  RCSCE Benchmark — Cache vs Cold Scan Performance")
    print(f"  Image: {args.image} × {args.count} containers")
    print(f"  Cache node: {CACHE_NODE}")
    print(f"{'═'*62}")

    if not check_cache_node():
        print("\n  Start the cache node first:")
        print("  NODE_ID=cache-node-1 uvicorn cache.cache_node:app --port 9001")
        sys.exit(1)

    images = [args.image] * args.count
    run_id = str(uuid.uuid4())[:8]
    print(f"  Run ID: {run_id}  (keys isolated from live system — no interference)")

    # Experiment A: Cold
    cold_rows, cold_hashes     = run_experiment_a(images, run_id)
    cold_summary               = summarise(cold_rows)

    # Experiment B: Cached
    cached_rows, cached_hashes = run_experiment_b(images, run_id)
    cached_summary             = summarise(cached_rows)

    # Clean up benchmark keys
    delete_bench_keys(cold_hashes + cached_hashes)
    print(f"\n  Benchmark keys removed from cache node.")

    print_comparison(cold_summary, cached_summary, args.count)

    if args.output:
        export_csv(cold_rows, cached_rows, args.output)

    print(f"  Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Tip: use --output results.csv to save raw data for your final report.\n")


if __name__ == "__main__":
    main()