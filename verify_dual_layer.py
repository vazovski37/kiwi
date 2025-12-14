
import subprocess
import sys
import os
import json

def verify_dual_layer():
    print("🧪 Testing Dual-Layer Reasoning Engine...")
    
    # We use a small repo for speed or just re-use one.
    owner = "vazovski37"
    repo = "gynt" # Small enough? Or sheukvete-frontend?
    # Let's use gynt, it triggered the "master" fallback before, good test of robustness too.
    branch = "main" # Will fallback to master
    
    print(f"🔄 Triggering CLI Ingestion for {owner}/{repo}...")
    
    cmd = [sys.executable, "cli_ingest.py", owner, repo, branch]
    
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    
    try:
        # Run ingestion
        result = subprocess.run(cmd, capture_output=True, text=True, env=env, encoding="utf-8")
        
        if result.returncode != 0:
            print("❌ Ingestion failed!")
            print(result.stderr)
            print("📜 STDOUT:", result.stdout)
            return

        print("✅ Ingestion CLI finished.")
        print("📜 CLI OUTPUT LOGS:\n" + result.stdout[-2000:]) # Print last 2000 chars to see Swarm logs

        
        # Parse Repo ID
        repo_id = ""
        for line in result.stdout.splitlines():
            if "Repo ID:" in line:
                repo_id = line.split("Repo ID:")[1].strip()
        
        if not repo_id:
            print("❌ Could not find Repo ID in output.")
            print(result.stdout)
            return
            
        print(f"🆔 Repo ID: {repo_id}")
        
        # CHECK ARTIFACTS
        map_path = f"maps/{repo_id}.txt"
        graph_path = f"graphs/{repo_id}.json"
        
        if os.path.exists(map_path):
            print(f"✅ Repo Map found: {map_path}")
            # Check content
            with open(map_path, "r", encoding="utf-8") as f:
                content = f.read()
                if "File:" in content:
                    print(f"   - Valid content detected ({len(content)} chars).")
                else:
                    print("   ⚠️ Map content looks suspicious.")
                    
                if "--- TECH STACK ---" in content:
                    print("   ✅ Tech Stack header found.")
                else:
                    print("   ❌ Tech Stack header MISSING (Context Loss Bug).")
        else:
            print(f"❌ Repo Map MISSING: {map_path}")
            
        if os.path.exists(graph_path):
            print(f"✅ Dependency Graph found: {graph_path}")
            # Check JSON
            with open(graph_path, "r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                    print(f"   - Valid JSON detected ({len(data)} keys).")
                except json.JSONDecodeError:
                    print("   ❌ Invalid JSON content.")
        else:
            print(f"❌ Dependency Graph MISSING: {graph_path}")

        # CHECK ARCHITECTURE JSON
        arch_path = f"architectures/{repo_id}.json"
        if os.path.exists(arch_path):
            print(f"✅ Architecture JSON found: {arch_path}")
            with open(arch_path, "r", encoding="utf-8") as f:
                try:
                    arch_data = json.load(f)
                    required_keys = ["meta", "stack", "modules", "flow", "mermaid"]
                    missing_keys = [k for k in required_keys if k not in arch_data]
                    
                    if not missing_keys:
                         print("   - ✅ Valid Schema (Meta, Stack, Modules, Flow, Mermaid).")
                    else:
                         print(f"   ❌ Invalid Schema. Missing: {missing_keys}")
                except json.JSONDecodeError:
                    print("   ❌ Invalid JSON content in Architecture file.")
        else:
            print(f"❌ Architecture JSON MISSING: {arch_path}")
            
    except Exception as e:
        print(f"❌ Test Exception: {e}")

if __name__ == "__main__":
    verify_dual_layer()
