
from indexer_robust import ingest_repo

def test_fallback():
    print("🧪 Testing Ingestion Fallback...")
    # Request 'main', but repo default is 'master' (as per debug output)
    # This should trigger the fallback logic.
    try:
        repo_id = ingest_repo("vazovski37", "gynt", "main")
        print(f"✅ Ingestion successful! Repo ID: {repo_id}")
    except Exception as e:
        print(f"❌ Ingestion failed: {e}")

if __name__ == "__main__":
    test_fallback()
