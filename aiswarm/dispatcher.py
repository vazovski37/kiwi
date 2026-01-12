import os
import json
import redis
import argparse
import glob

# Configuration
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
QUEUE_NAME = os.getenv("QUEUE_NAME", "swarm_jobs")

def dispatch(directory):
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        r.ping()
    except Exception as e:
        print(f"[!] Failed to connect to Redis: {e}")
        return

    files = glob.glob(os.path.join(directory, "**/*"), recursive=True)
    count = 0
    
    for file_path in files:
        if os.path.isfile(file_path):
            try:
                # Read content locally since we need to send it to the worker
                # (Worker might not have access to local Host filesystem unless using HostPath volumes)
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()

                job = {
                    "file_path": file_path,
                    "content": content
                }
                
                r.rpush(QUEUE_NAME, json.dumps(job))
                print(f"[+] Queued: {file_path}")
                count += 1
            except Exception as e:
                print(f"[!] Skipped {file_path}: {e}")

    print(f"[*] Successfully dispatched {count} jobs to '{QUEUE_NAME}'")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Swarm Dispatcher")
    parser.add_argument("directory", help="Directory to scan for files")
    args = parser.parse_args()

    dispatch(args.directory)
