import os
import time
import json
import redis
import requests
import sys

# Configuration
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
QUEUE_NAME = os.getenv("QUEUE_NAME", "swarm_jobs")
OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
MODEL_NAME = "qwen2.5-coder:3b"

def process_task(task_data):
    """
    Process a single task in RPC style.
    task_data: JSON string containing 'id', 'file_name', 'code'
    """
    try:
        job = json.loads(task_data)
        job_id = job.get("id")
        file_name = job.get("file_name")
        code = job.get("code")
        
        if not job_id:
            print("[!] Received job without ID, skipping.")
            return

        print(f"[*] Processing Job {job_id} for {file_name}")

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
        r_conn = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        r_conn.lpush(reply_key, json.dumps(result_data))
        # Set expiry for the reply to avoid clutter
        r_conn.expire(reply_key, 600) 
        
        print(f"[+] Reply sent to {reply_key}")
        return True

    except Exception as e:
        print(f"[!] Critical Worker Error: {e}")
        return False

def main():
    print(f"[*] Starting Swarm Worker (RPC Mode)...")
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
            # Blocking pop - waits until an item is available
            # Returns tuple (queue_name, value)
            task = r.blpop(QUEUE_NAME, timeout=5)
            
            if task:
                print(f"[!] Got task: {task[0]}")
                _, task_data = task
                process_task(task_data)
            else:
                print("[.] Waiting...", flush=True)
                
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
