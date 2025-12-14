
import threading
from indexer_robust import ingest_repo
import traceback

def worker():
    print("🧵 Thread started...")
    try:
        repo_id = ingest_repo("vazovski37", "sheukvete-frontend", "main")
        print(f"✅ Ingestion successful in thread: {repo_id}")
    except Exception as e:
        print(f"❌ Thread failed: {e}")
        traceback.print_exc()

def test_threading():
    print("🧪 Testing Ingestion in separate thread (FastAPI simulation)...")
    t = threading.Thread(target=worker)
    t.start()
    t.join()
    print("🧪 Test complete.")

if __name__ == "__main__":
    test_threading()
