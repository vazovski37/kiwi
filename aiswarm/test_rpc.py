import time
import json
from client import SwarmClient

def test_swarm():
    print("[*] Initializing Swarm Client...")
    # Ensure Redis port matches your local port-forward if running from host
    # Assuming user will port-forward Redis or run this inside cluster.
    # For local host usage, we need to port-forward redis-service first.
    client = SwarmClient(redis_host="127.0.0.1", redis_port=6379)
    
    sample_code = """
import os
import requests

def fetch_data():
    return requests.get("https://google.com")

export_list = [fetch_data]
"""
    
    print("[*] Sending test job (code analysis)...")
    start = time.time()
    
    # We call it strict like a function
    result = client.analyze_code(
        file_name="test_script.py",
        code=sample_code,
        timeout=120
    )
    
    end = time.time()
    print(f"\n[+] Analysis Complete in {end - start:.2f}s")
    print("-" * 40)
    print(json.dumps(result, indent=2))
    print("-" * 40)

    if "summary" in result and result["summary"] != "Timeout waiting for swarm":
        print("✅ RPC Pattern Test Passed!")
    else:
        print("❌ Test Failed or Timed Out.")

if __name__ == "__main__":
    test_swarm()
