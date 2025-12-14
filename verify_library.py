
import os
import requests
import time
import subprocess
import sys

def verify_library():
    print("🧪 Testing Repository Library API...")
    
    # 1. Start Server in Background
    print("🚀 Starting API Server...")
    server_process = subprocess.Popen(
        [sys.executable, "main.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=os.getcwd(),
        env={**os.environ, "PYTHONIOENCODING": "utf-8"}
    )
    
    try:
        # Give it time to start (increased)
        print("⏳ Waiting 10s for server startup...")
        time.sleep(10)
        
        # 1.5. Health Check
        try:
             root_resp = requests.get("http://localhost:8000/")
             print(f"🏥 Health Check: {root_resp.status_code} - {root_resp.text}")
        except Exception as e:
             print(f"🏥 Health Check Failed: {e}")
        
        # 2. Call GET /api/repos
        url = "http://localhost:8000/api/repos"
        print(f"📞 Calling {url}...")
        
        try:
            resp = requests.get(url)
            if resp.status_code == 200:
                data = resp.json()
                print(f"✅ Status 200 OK. Received {len(data)} repos.")
                
                # Check structure
                if isinstance(data, list):
                    for repo in data:
                        if "id" in repo and "meta" in repo:
                            print(f"   - Found Repo: {repo['id']}")
                            print(f"     Meta: {repo['meta'].get('project_name', 'Unknown')}")
                        else:
                            print(f"   ⚠️ Invalid Repo Object: {repo}")
                            
                    if len(data) > 0:
                        print("✅ Verification Successful: Library is populated.")
                    else:
                        print("⚠️ Verification Warning: Library is empty (make sure you have architectures).")
                else:
                    print(f"❌ Error: Expected list, got {type(data)}")
            else:
                print(f"❌ Error: Status {resp.status_code} - {resp.text}")
                
        except Exception as e:
            print(f"❌ Connection Failed: {e}")
            
    finally:
        # 3. Cleanup
        print("🛑 Stopping Server...")
        server_process.terminate()
        try:
            outs, errs = server_process.communicate(timeout=5)
            print(f"--- Server STDOUT ---\n{outs.decode('utf-8', errors='ignore') if outs else ''}")
            print(f"--- Server STDERR ---\n{errs.decode('utf-8', errors='ignore') if errs else ''}")
        except:
             server_process.kill()
             
if __name__ == "__main__":
    verify_library()
