import time
import random
import sys

print("Starting Mock Authentication Service...", flush=True)

while True:
    time.sleep(3)
    chance = random.random()
    
    if chance < 0.2:
        print("[FATAL] Database connection lost on port 5432!", file=sys.stderr, flush=True)
    elif chance < 0.4:
        print("[WARN] failed password attempt for user: admin_root", flush=True)
    else:
        print(f"[INFO] Successful health check ping. ms={random.randint(10, 50)}", flush=True)