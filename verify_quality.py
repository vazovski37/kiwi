
from indexer_robust import ingest_repo, load_index_for_repo, query_module
import shutil
import os

def check_file_absence(index, filename):
    # This is tricky without raw query of docstore.
    # But we can query for the filename.
    print(f"🔎 Checking if {filename} is present impactfully...")
    response = query_module(index, f"does the file {filename} exist?")
    print(f"Response: {response}")

def test_quality():
    print("🧪 Testing Quality Improvements...")
    
    repo_id = "vazovski37-gynt-main"
    # We expect this ingestion to trigger the 'master' fallback AND exclude package-lock.json
    try:
        new_id = ingest_repo("vazovski37", "gynt", "main")
        print(f"✅ Ingestion successful: {new_id}")
        
        index = load_index_for_repo(new_id)
        
        # Test Query
        print("❓ Querying Architecture...")
        ans = query_module(index, "what architecture is my code base using?")
        print(f"🤖 Answer: {ans}")
        # We want to ensure it DOESN'T talk about arm64/linux from package-lock.json
        
    except Exception as e:
        print(f"❌ Test failed: {e}")

if __name__ == "__main__":
    test_quality()
