
import requests
import time
import subprocess
import sys
import os
import json

def verify_phase1():
    print("🧪 Testing Living Twin Phase 1...")
    
    # 0. Clean DB for fresh test
    if os.path.exists("db/repos.json"):
        os.remove("db/repos.json")
    
    # 1. Start Server
    print("🚀 Starting API Server...")
    server_process = subprocess.Popen(
        [sys.executable, "main.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=os.getcwd(),
        env={**os.environ, "PYTHONIOENCODING": "utf-8"}
    )
    
    try:
        time.sleep(10) # Wait for startup
        
        base_url = "http://localhost:8000"
        
        # 2. Test Get Branches
        print("🌳 Testing /api/github/branches...")
        payload = {"url": "https://github.com/vazovski37/gynt"}
        resp = requests.post(f"{base_url}/api/github/branches", json=payload)
        
        if resp.status_code == 200:
            branches = resp.json()
            print(f"✅ Branches Fetched: {branches}")
            if "main" in branches:
                print("   - confirmed 'main' branch exists")
        else:
            print(f"❌ Branch Fetch Failed: {resp.status_code} - {resp.text}")

        # 3. Test Ingest (Trigger State Save)
        print("📥 Testing /api/ingest (Triggering DB Upsert)...")
        # We use a real repo that is small or already analyzed
        payload = {"url": "https://github.com/vazovski37/gynt", "branch": "main"}
        resp = requests.post(f"{base_url}/api/ingest", json=payload)
        
        if resp.status_code == 200:
            data = resp.json()
            repo_id = data['repo_id']
            print(f"✅ Ingest Success. Repo ID: {repo_id}")
            
            # Allow time for CLI to finish if synchronous? 
            # api_ingest is blocking in main.py, so it should be done.
        else:
            print(f"❌ Ingest Failed: {resp.status_code} - {resp.text}")
            
        # 4. Verify DB Persistence via /api/repos
        print("💾 Testing /api/repos (Source of Truth)...")
        resp = requests.get(f"{base_url}/api/repos")
        
        if resp.status_code == 200:
            repos = resp.json()
            print(f"✅ Repos Fetched: {len(repos)} found.")
            
            found = False
            for r in repos:
                if r['repo_id'] == "vazovski37-gynt-main":
                    found = True
                    print(f"   - Found {r['repo_id']}")
                    print(f"   - SHA: {r.get('current_sha', 'MISSING')}")
                    print(f"   - Last Updated: {r.get('last_updated')}")
                    
                    if r.get('current_sha') and r.get('current_sha') != "unknown":
                        print("   ✅ SHA Captured!")
                    else:
                        print("   ⚠️ SHA Missing or Unknown")
                        
            if found:
                print("✅ Verification Successful: Phase 1 Complete.")
            else:
                print("❌ Verification Failed: Repo not found in DB list.")
        else:
             print(f"❌ Repos Fetch Failed: {resp.status_code} - {resp.text}")

    except Exception as e:
        print(f"❌ Test Failed: {e}")
        
    finally:
        print("🛑 Stopping Server...")
        server_process.terminate()
        try:
             outs, errs = server_process.communicate(timeout=5)
             # print(outs.decode('utf-8'))
        except:
             server_process.kill()

if __name__ == "__main__":
    verify_phase1()
