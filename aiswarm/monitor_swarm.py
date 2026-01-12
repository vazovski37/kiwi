import os
import sys
import time
import json
import redis
from datetime import datetime

# Configuration
REDIS_HOST = "localhost"
REDIS_PORT = 6380 # Using the forwarded port

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def get_swarm_status(r):
    try:
        # Queue Depth
        queue_len = r.llen("swarm_jobs")
        
        # Worker Status
        worker_keys = r.keys("worker:*")
        workers = []
        for key in worker_keys:
            try:
                data = json.loads(r.get(key))
                workers.append(data)
            except:
                continue
                
        # Sort by ID for stability
        workers.sort(key=lambda x: x.get("id"))
        return queue_len, workers
    except Exception as e:
        return -1, []

def print_dashboard(queue_len, workers):
    clear_screen()
    print("🤖 AI Swarm Live Monitor")
    print("==================================================")
    print(f"Time: {datetime.now().strftime('%H:%M:%S')}")
    print(f"Queue Depth: {queue_len} pending jobs")
    print("--------------------------------------------------")
    print(f"{'Worker ID':<10} | {'Status':<8} | {'Duration':<6} | {'Last File'}")
    print("-" * 50)
    
    active_count = 0
    for w in workers:
        status = w.get("status", "UNKNOWN")
        if status == "BUSY":
            status_display = "🔴 BUSY"
            active_count += 1
        elif status == "IDLE":
            status_display = "🟢 IDLE"
        else:
            status_display = f"⚪ {status}"
            
        duration = f"{w.get('duration', 0):.2f}s"
        file_name = w.get("file", "-") or "-"
        if len(file_name) > 30:
            file_name = "..." + file_name[-27:]
            
        print(f"{w.get('id'):<10} | {status_display:<8} | {duration:<6} | {file_name}")
        
    print("==================================================")
    print(f"Utilization: {active_count}/{len(workers)} workers active")
    print("Press Ctrl+C to exit.")

def main():
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        r.ping()
    except Exception as e:
        print(f"[!] Cannot connect to Redis at {REDIS_HOST}:{REDIS_PORT}")
        print("    Did you run 'kubectl port-forward svc/redis-service 6380:6379 -n aiswarm'?")
        return

    while True:
        try:
            q_len, workers = get_swarm_status(r)
            if q_len == -1:
                print("[!] Redis connection error.")
                time.sleep(1)
                continue
                
            print_dashboard(q_len, workers)
            
            # Test mode exit
            if len(sys.argv) > 1 and sys.argv[1] == "--test":
                print("\n[TEST] Dashboard rendered successfully.")
                break
                
            time.sleep(0.5)
            
        except KeyboardInterrupt:
            print("\nStopped.")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(1)

if __name__ == "__main__":
    main()
