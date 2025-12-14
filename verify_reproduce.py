
from indexer_robust import ingest_repo
import traceback

def reproduce_error():
    print("🧪 Attempting to reproduce ingestion error for sheukvete-frontend...")
    
    try:
        # This repo caused the 500 error
        repo_id = ingest_repo("vazovski37", "sheukvete-frontend", "main")
        print(f"✅ Ingestion successful: {repo_id}")
    except Exception as e:
        print(f"❌ Reproduction successful (Error caught): {e}")
        traceback.print_exc()

if __name__ == "__main__":
    reproduce_error()
