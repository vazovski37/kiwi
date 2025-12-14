
import requests
import time
import subprocess
import sys
import os
import json

def verify_phase2():
    print("🧪 Testing Living Twin Phase 2 (Audit)...")
    
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
        
        # 2. Get a valid repo ID from Library
        print("📚 Fetching repos...")
        resp = requests.get(f"{base_url}/api/repos")
        if resp.status_code != 200 or not resp.json():
            print("❌ No repos found. Ingesting 'vazovski37/gynt'...")
            # Ingest to populate DB
            ingest_payload = {"url": "https://github.com/vazovski37/gynt", "branch": "main"}
            requests.post(f"{base_url}/api/ingest", json=ingest_payload)
            time.sleep(5) 
            resp = requests.get(f"{base_url}/api/repos")
            if not resp.json():
                print("❌ Ingestion failed to populate Library.")
                return

        repo_id = resp.json()[0]['id']
        print(f"🎯 using repo: {repo_id}")
        
        # 3. Check Updates
        print(f"🔍 Checking updates for {repo_id}...")
        resp = requests.get(f"{base_url}/api/updates/check/{repo_id}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"✅ Check Result: Updates={data.get('has_updates')}")
            print(f"   Local SHA: {data.get('local_sha')}")
            print(f"   Remote SHA: {data.get('remote_sha')}")
            
            # If SHA match, we cannot test audit fully unless we fake the local SHA.
            # But we can verify the API call works and returns UP_TO_DATE.
        else:
            print(f"❌ Check Failed: {resp.status_code} - {resp.text}")
            
        # 4. Run Audit (Dry run if up to date)
        print(f"🕵️ Running Audit for {repo_id}...")
        resp = requests.post(f"{base_url}/api/updates/audit/{repo_id}")
        if resp.status_code == 200:
            data = resp.json()
            if "status" in data and data["status"] == "UP_TO_DATE":
                print("✅ Audit API Works (Up to date).")
            elif "audit_report" in data:
                print("✅ Audit API Works (Audit ran).")
                print(f"   Score: {data['audit_report'].get('score')}")
                print(f"   Status: {data['audit_report'].get('status')}")
            else:
                print(f"⚠️ Audit Unexpected Response: {data}")
        elif resp.status_code == 404:
            print(f"❌ Audit Failed: Repo not found")
        else:
            print(f"❌ Audit Failed: {resp.status_code} - {resp.text}")

    except Exception as e:
        print(f"❌ verification Failed: {e}")
        
    finally:
        print("🛑 Stopping Server...")
        server_process.terminate()
        try:
             outs, errs = server_process.communicate(timeout=5)
        except:
             server_process.kill()

if __name__ == "__main__":
    verify_phase2()
