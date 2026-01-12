import time
import threading
import random
from client import SwarmClient

# Configuration
CONCURRENT_JOBS = 5  # Number of jobs to dump at once
CLIENT = SwarmClient(redis_host="127.0.0.1", redis_port=6379)

SAMPLE_CODE_VARIANTS = [
    "import os\ndef test(): print('hello world')",
    "import sys\ndef scan(): return sys.argv",
    "import json\ndef parse(s): return json.loads(s)",
    "import requests\ndef fetch(url): return requests.get(url).text",
    "class User:\n    def __init__(self, name): self.name = name"
]

def submit_job(idx):
    code = random.choice(SAMPLE_CODE_VARIANTS)
    print(f"[{idx}] Submitting Job...")
    start = time.time()
    
    # RPC Call (Blocks until response)
    result = CLIENT.analyze_code(f"test_file_{idx}.py", code)
    
    duration = time.time() - start
    print(f"[{idx}] ✅ Finished in {duration:.2f}s | Summary: {result.get('summary', 'Error')[:50]}...")

def main():
    print(f"🚀 Starting Swarm Stress Test ({CONCURRENT_JOBS} jobs)...")
    threads = []
    
    # Launch threads to simulate concurrent clients
    for i in range(CONCURRENT_JOBS):
        t = threading.Thread(target=submit_job, args=(i,))
        threads.append(t)
        t.start()
        
    # Wait for all
    for t in threads:
        t.join()
        
    print("\n🏁 All jobs completed.")

if __name__ == "__main__":
    main()
