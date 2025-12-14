
import sys
import os
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Ensure we can import our modules
try:
    from main import app
    from indexer_robust import ingest_repo, generate_architecture, load_index_for_repo
    print("✅ Imports successful.")
except ImportError as e:
    print(f"❌ Import failed: {e}")
    sys.exit(1)

client = TestClient(app)

def test_startup():
    print("🧪 Testing Server Startup...")
    response = client.get("/")
    if response.status_code == 200:
        print("✅ Health Check Passed:", response.json())
    else:
        print("❌ Health Check Failed:", response.status_code)

if __name__ == "__main__":
    test_startup()
