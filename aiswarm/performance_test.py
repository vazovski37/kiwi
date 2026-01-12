import os
import time
import glob
import concurrent.futures
from client import SwarmClient

# Configuration
CONCURRENT_REQUESTS = 5
SEARCH_PATTERN = "../**/*.py"  # Scan parent directory recursively
REDIS_HOST = "localhost"
REDIS_PORT = 6380

def collect_files(pattern):
    """Collects python files from the codebase."""
    files = []
    print(f"[*] Scanning for files matching: {pattern}")
    for file_path in glob.glob(pattern, recursive=True):
        # Skip venv, .git, and the aiswarm folder itself to avoid self-recursion issues or testing config files
        if "venv" in file_path or ".git" in file_path or "aiswarm" in file_path:
            continue
        if os.path.isfile(file_path):
            files.append(file_path)
    return files

def benchmark_file(client, file_path):
    """Reads a file and sends it to the swarm."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            code = f.read()
        
        if not code.strip():
            return None

        file_name = os.path.basename(file_path)
        start_time = time.time()
        
        # Send to Swarm
        result = client.analyze_code(file_name, code)
        duration = time.time() - start_time

        # Check for error keywords
        summary = result.get("summary", "")
        success = "summary" in result and "Error" not in summary and "Timeout" not in summary
        
        return {
            "file": file_name,
            "duration": duration,
            "success": success,
            "summary": summary[:50]
        }
    except Exception as e:
        return {"file": file_path, "error": str(e), "success": False, "duration": 0}

def main():
    print("🚀 Starting AI Swarm Performance Test")
    print("--------------------------------------")
    
    # 1. Setup
    files = collect_files(SEARCH_PATTERN)
    if not files:
        print("[!] No files found to test.")
        return

    print(f"[*] Found {len(files)} valid Python files to process.")
    
    client = SwarmClient(redis_host=REDIS_HOST, redis_port=REDIS_PORT)
    
    # 2. Execution
    print(f"[*] Starting benchmark with {CONCURRENT_REQUESTS} concurrent threads...")
    start_total = time.time()
    results = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENT_REQUESTS) as executor:
        future_to_file = {executor.submit(benchmark_file, client, f): f for f in files}
        
        completed = 0
        for future in concurrent.futures.as_completed(future_to_file):
            data = future.result()
            if data:
                results.append(data)
                completed += 1
                status = "✅" if data["success"] else "❌"
                reason = data.get("summary", "") or data.get("error", "Unknown Error")
                print(f"[{completed}/{len(files)}] {status} {data['file']} ({data['duration']:.2f}s) - {reason}")

    total_time = time.time() - start_total
    
    # 3. Report
    success_count = sum(1 for r in results if r["success"])
    avg_time = sum(r["duration"] for r in results) / len(results) if results else 0
    
    print("\n📊 Final Report")
    print("--------------------------------------")
    print(f"Total Files Processed: {len(results)}")
    print(f"Successful Analyses:   {success_count}")
    print(f"Failed Analyses:       {len(results) - success_count}")
    print(f"Total Time Taken:      {total_time:.2f}s")
    print(f"Average Time/File:     {avg_time:.2f}s")
    print("--------------------------------------")

if __name__ == "__main__":
    main()
