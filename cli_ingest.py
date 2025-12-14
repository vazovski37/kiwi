
import sys
import nest_asyncio
import traceback
from indexer_robust import ingest_repo, generate_architecture_json

# Apply nest_asyncio here, safely in a standalone process
nest_asyncio.apply()

def main():
    if len(sys.argv) < 4:
        print("Usage: python cli_ingest.py <owner> <repo> <branch>")
        sys.exit(1)
        
    owner = sys.argv[1]
    repo = sys.argv[2]
    branch = sys.argv[3]
    
    print(f"🚀 CLI Ingestion starting for {owner}/{repo}/{branch}...")
    
    try:
        repo_id = ingest_repo(owner, repo, branch)
        print(f"✅ CLI Ingestion success. Repo ID: {repo_id}")
        
        # Generate architecture JSON
        generate_architecture_json(repo_id)
        print("✅ CLI Architecture JSON generation success.")
        
    except Exception as e:
        print(f"❌ CLI Ingestion Failed: {e}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
