import os
import time
import json
import redis
import requests
import sys

import uuid

# Configuration
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
QUEUE_NAME = os.getenv("QUEUE_NAME", "swarm_jobs")
OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
MODEL_NAME = "qwen2.5-coder:3b"
WORKER_ID = str(uuid.uuid4())[:8]

def report_status(r_conn, status, current_file=None, duration=0):
    """
    Broadcasts worker status to Redis.
    Key: worker:{WORKER_ID}
    Value: JSON dictionary
    TTL: 5 seconds
    """
    try:
        data = {
            "id": WORKER_ID,
            "status": status,
            "file": current_file,
            "last_updated": time.time(),
            "duration": duration
        }
        key = f"worker:{WORKER_ID}"
        r_conn.setex(key, 5, json.dumps(data))
    except Exception as e:
        print(f"[!] Status broadcast failed: {e}")

def process_task(task_data, r_conn):
    """
    Process a single task in RPC style.
    task_data: JSON string containing 'id', 'file_name', 'code'
    """
    start_time = time.time()
    try:
        job = json.loads(task_data)
        job_id = job.get("id")
        file_name = job.get("file_name")
        code = job.get("code")
        
        if not job_id:
            print("[!] Received job without ID, skipping.")
            return

        print(f"[*] Processing Job {job_id} for {file_name}")
        report_status(r_conn, "BUSY", file_name)

        # Construct the strict JSON prompt
        prompt = (
            f"Analyze this code file: '{file_name}'\n\n"
            f"```\n{code[:4000]}\n```\n\n"
            "Return a JSON object with EXACTLY these keys:\n"
            '{"summary": "1 sentence description", '
            '"dependencies": ["list", "of", "imports"], '
            '"exports": ["list", "of", "exported", "items"]}\n'
            "Respond with JSON ONLY, no markdown."
        )
        
        # Call Ollama
        try:
            response = requests.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": MODEL_NAME,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "num_predict": 512
                    }
                },
                headers={"Origin": "http://localhost"},
                timeout=300
            )
            response.raise_for_status()
            raw_text = response.json().get("response", "").strip()
            
            # Simple cleanup for Markdown code blocks
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:]
            if raw_text.startswith("```"):
                raw_text = raw_text[3:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]
            
            result_data = json.loads(raw_text.strip())
            
        except Exception as e:
            print(f"[!] Inference/Parse Error: {e}")
            result_data = {
                "summary": f"Analysis failed: {str(e)}",
                "dependencies": [],
                "exports": []
            }

        # Send Reply to Redis
        reply_key = f"reply:{job_id}"
        # Use a new connection for replies if needed, or reuse. 
        # Here we reuse the passed connection but `lpush` is thread/process safe enough for this simple usage.
        r_conn.lpush(reply_key, json.dumps(result_data))
        r_conn.expire(reply_key, 600) 
        
        duration = time.time() - start_time
        print(f"[+] Reply sent to {reply_key} ({duration:.2f}s)")
        report_status(r_conn, "IDLE", duration=duration)
        return True

    except Exception as e:
        print(f"[!] Critical Worker Error: {e}")
        report_status(r_conn, "ERROR")
        return False

def main():
    print(f"[*] Starting Swarm Worker {WORKER_ID} (RPC Mode)...")
    print(f"[*] Redis: {REDIS_HOST}:{REDIS_PORT}")
    print(f"[*] Ollama: {OLLAMA_URL}")

    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        r.ping()
        print("[*] Connected to Redis")
    except Exception as e:
        print(f"[!] Failed to connect to Redis: {e}")
        sys.exit(1)

    print("[*] Entering main loop...")
    while True:
        try:
            # Heartbeat (IDLE)
            report_status(r, "IDLE")
            
            # Blocking pop - waits until an item is available
            # Returns tuple (queue_name, value)
            task = r.blpop(QUEUE_NAME, timeout=2) # Reduced timeout to send heatbeats more often
            
            if task:
                print(f"[!] Got task: {task[0]}")
                _, task_data = task
                process_task(task_data, r)
            else:
                # print("[.] Waiting...", flush=True)
                pass
                
        except redis.exceptions.ConnectionError:
            print("[!] Redis connection lost, retrying...")
            time.sleep(5)
        except KeyboardInterrupt:
            print("[*] Worker stopping...")
            break
        except Exception as e:
            print(f"[!] Unexpected error: {e}")
            time.sleep(1)

if __name__ == "__main__":
    main()
