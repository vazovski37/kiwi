
import os
import sys
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import subprocess
import json

# Import only retrieval basics
from indexer_robust import load_index_for_repo
from llama_index.core import Settings, PromptTemplate
from llama_index.core.retrievers import AutoMergingRetriever
from llama_index.core.query_engine import RetrieverQueryEngine

from database import db
from github_service import GithubService

app = FastAPI(title="CodeAtlas Multi-Tenant API")

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory cache for query engines
QUERY_ENGINE_CACHE = {}

class IngestRequest(BaseModel):
    url: str
    branch: str = "main"

class BranchRequest(BaseModel):
    url: str

class ChatRequest(BaseModel):
    repo_id: str
    message: str

@app.get("/")
def home():
    return {"status": "online", "system": "Multi-Tenant CodeAtlas"}

@app.post("/api/github/branches")
def get_branches(request: BranchRequest):
    """
    Fetches available branches for a given repository URL.
    """
    try:
        parts = request.url.rstrip("/").split("/")
        repo = parts[-1]
        owner = parts[-2]
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid GitHub URL format.")
    
    gh = GithubService()
    branches = gh.get_branches(owner, repo)
    return branches

@app.post("/api/ingest")
def api_ingest(request: IngestRequest):
    """
    Spawns a subprocess to handle ingestion robustly, avoiding async conflicts.
    Updates RepoDB with the new state.
    """
    try:
        parts = request.url.rstrip("/").split("/")
        repo = parts[-1]
        owner = parts[-2]
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid GitHub URL format.")
    
    # 1. Fetch Current SHA (Living Twin)
    gh = GithubService()
    current_sha = gh.get_current_sha(owner, repo, request.branch)
    if not current_sha:
        print(f"⚠️ Warning: Could not fetch SHA for {owner}/{repo}/{request.branch}")
        current_sha = "unknown"

    print(f"🔄 Spawning ingestion subprocess for {owner}/{repo} (SHA: {current_sha})...")
    
    # Construct command
    cmd = [sys.executable, "cli_ingest.py", owner, repo, request.branch]
    
    # Ensure subprocess can print emojis regardless of Windows console encoding
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    
    try:
        # Run blocking
        result = subprocess.run(cmd, capture_output=True, text=True, env=env, encoding="utf-8")
        
        print("📜 Subprocess Output:", result.stdout)
        if result.stderr:
            print("⚠️ Subprocess Error Output:", result.stderr)
            
        if result.returncode != 0:
            raise Exception(f"Subprocess failed with code {result.returncode}. check server logs.")
            
        # Parse Repo ID from output
        repo_id = f"{owner}-{repo}-{request.branch}" # Fallback guess
        for line in result.stdout.splitlines():
            if "Repo ID:" in line:
                repo_id = line.split("Repo ID:")[1].strip()
        
        # 2. Update RepoDB (State Management)
        # Load the generated architecture to get metadata
        meta = {}
        arch_path = f"./architectures/{repo_id}.json"
        if os.path.exists(arch_path):
            try:
                with open(arch_path, "r", encoding="utf-8") as f:
                    arch_data = json.load(f)
                    meta = arch_data.get("meta", {})
            except Exception as e:
                print(f"⚠️ Failed to load metadata for DB update: {e}")
        
        repo_data = {
            "repo_id": repo_id,
            "url": request.url,
            "branch": request.branch,
            "current_sha": current_sha,
            "meta": meta
        }
        db.upsert(repo_data)
        print(f"💾 Repo State Saved: {repo_id} (SHA: {current_sha})")
        
        return {"status": "success", "repo_id": repo_id}
        
    except Exception as e:
        print(f"❌ Ingestion Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def load_repo_context(repo_id):
    """
    Loads the standard artifacts (Repo Map and Dependency Graph) for the Dual-Layer Engine.
    """
    map_file = f"./maps/{repo_id}.txt"
    graph_file = f"./graphs/{repo_id}.json"
    
    repo_map = "(No Repo Map found)"
    if os.path.exists(map_file):
        with open(map_file, "r", encoding="utf-8") as f:
            repo_map = f.read()

    dependency_graph = "(No Dependency Graph found)"
    if os.path.exists(graph_file):
        with open(graph_file, "r", encoding="utf-8") as f:
            dependency_graph = f.read()
            
    # Truncate graph if excessively large to avoid blowing context (simple safety)
    if len(dependency_graph) > 50000:
         dependency_graph = dependency_graph[:50000] + "\n...(truncated)..."
            
    return repo_map, dependency_graph

@app.post("/api/chat")
def api_chat(request: ChatRequest):
    repo_id = request.repo_id
    
    query_engine = QUERY_ENGINE_CACHE.get(repo_id)
    
    if not query_engine:
        print(f"📦 Cache miss for {repo_id}. Loading index and contexts...")
        try:
            index = load_index_for_repo(repo_id)
            
            # --- DUAL-LAYER CONTEXT LOADING ---
            repo_map, dependency_graph = load_repo_context(repo_id)
            
            # Create Custom Prompt Template
            # We hardcode the map/graph into the template string so LlamaIndex only sees {context_str} and {query_str}
            # Note: We escape curly braces in the map/graph if any? Ideally yes, but rare in these formats.
            # Safe approach: replace double braces if needed, but simple string injection is usually ok.
            
            qa_template_str = (
                "You are an AI Architect. \n"
                "I have provided the Repo Map and Dependency Graph below to give you global understanding.\n\n"
                "=== REPO MAP ===\n"
                f"{repo_map}\n\n"
                "=== DEPENDENCY GRAPH ===\n"
                f"{dependency_graph}\n\n"
                "---------------------\n"
                "Context information from specific files is below.\n"
                "{context_str}\n"
                "---------------------\n"
                "Given the global map, graph, and specific context, answer the user question: {query_str}\n\n"
                "CRITICAL INSTRUCTIONS:\n"
                "1. TECH STACK: Look at the top of the Repo Map for '--- TECH STACK ---'. Use this to determine the exact frameworks (e.g., Next.js, Tailwind).\n"
                "2. MERMAID: If asked for diagrams, you MUST use `graph TD` or `graph LR`. Enclose ALL labels in double quotes (e.g., A[\"Login Page\"]). No special chars in Node IDs.\n"
            )
            
            # Create Template Object
            text_qa_template = PromptTemplate(qa_template_str)
            
            # Setup Engine
            base_retriever = index.as_retriever(similarity_top_k=10)
            retriever = AutoMergingRetriever(
                base_retriever, index.storage_context, verbose=False
            )
            
            # Create Engine and UPDATE PROMPT
            query_engine = RetrieverQueryEngine.from_args(
                retriever, 
                text_qa_template=text_qa_template
            )
            
            query_engine.fallback_index = index 
            QUERY_ENGINE_CACHE[repo_id] = query_engine
            
        except Exception as e:
            raise HTTPException(status_code=404, detail=f"Repo {repo_id} not found or load failed: {e}")
    
    try:
        response = query_engine.query(request.message)
        return {"response": str(response)}
    except Exception as e:
        print(f"⚠️ Primary engine failed: {e}")
        if hasattr(query_engine, 'fallback_index'):
             try:
                 # Fallback logic (simple engine, likely no custom prompt, or same prompt?)
                 # Let's use simple prompt for fallback to be safe
                 fallback_engine = query_engine.fallback_index.as_query_engine(similarity_top_k=10)
                 response = fallback_engine.query(request.message)
                 return {"response": str(response)}
             except Exception as fe:
                 raise HTTPException(status_code=500, detail=f"Fallback failed: {fe}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/architecture/{repo_id}")
def get_architecture(repo_id: str):
    file_path = f"./architectures/{repo_id}.json"
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Architecture JSON not found.")
    
    with open(file_path, "r", encoding="utf-8") as f:
        # Load as JSON to ensure we return application/json content type correctly if needed
        # Or just read and return. FastAPI will separate if we return dict/list.
        content = json.load(f)
    
    return content



@app.get("/api/repos")
def get_repos():
    """
    Returns a list of all ingested repositories from the RepoDB (Source of Truth).
    """
    return db.get_all()

from audit_service import AuditService

@app.get("/api/updates/check/{repo_id}")
def check_updates(repo_id: str):
    """
    Checks if the local twin is behind the remote repo.
    """
    repo = db.get(repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repo not found in Living Twin DB.")
    
    local_sha = repo.get("current_sha")
    owner_str, repo_name, branch = repo_id.rsplit("-", 2)
    # Reconstruct owner/repo from ID isn't always safe if dash in name. 
    # Use stored URL if possible.
    
    # Better to parse from URL if available in DB
    url = repo.get("url", "")
    try:
        parts = url.rstrip("/").split("/")
        repo_name = parts[-1]
        owner_str = parts[-2]
    except:
        # Fallback to ID parse (risky but okay for now)
        pass 
        
    gh = GithubService()
    remote_sha = gh.get_current_sha(owner_str, repo_name, branch)
    
    if not remote_sha:
         raise HTTPException(status_code=500, detail="Failed to fetch remote SHA.")
         
    is_up_to_date = (local_sha == remote_sha)
    
    # Calculate "behind by" ? That requires commit counting which is heavy. 
    # For Check, just SHA comparison is usually enough for "Update Available".
    
    return {
        "repo_id": repo_id,
        "local_sha": local_sha,
        "remote_sha": remote_sha,
        "has_updates": not is_up_to_date
    }

@app.post("/api/updates/audit/{repo_id}")
def audit_updates(repo_id: str):
    """
    Compares Local vs Remote, gets diffs, and runs AI Audit.
    """
    # 1. Get Repo Context
    repo = db.get(repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repo not found.")
        
    local_sha = repo.get("current_sha")
    
    # Parse info
    url = repo.get("url", "")
    try:
        parts = url.rstrip("/").split("/")
        repo_name = parts[-1]
        owner_str = parts[-2]
    except:
        raise HTTPException(status_code=400, detail="Invalid Repo URL in DB.")
        
    # 2. Get Remote SHA
    gh = GithubService()
    remote_sha = gh.get_current_sha(owner_str, repo_name, repo.get("branch"))
    
    if local_sha == remote_sha:
        return {"status": "UP_TO_DATE", "message": "No new changes to audit."}
        
    # 3. Get Diffs
    diff_data = gh.compare_commits(owner_str, repo_name, local_sha, remote_sha)
    if diff_data.get("status") == "error":
        raise HTTPException(status_code=500, detail=diff_data.get("error"))
        
    # 4. Prepare Context for AI
    arch_meta = repo.get("meta", {})
    project_name = arch_meta.get("project_name", "Unknown Project")
    # We could load the full architecture text for better rules?
    # For now, let's use the DB meta which might be sparse, 
    # OR lets load the Architecture JSON file to get "stack" and "modules".
    
    tech_stack = "Unknown"
    arch_summary = f"Project: {project_name}"
    
    try:
        with open(f"./architectures/{repo_id}.json", "r", encoding="utf-8") as f:
            full_arch = json.load(f)
            stack_list = full_arch.get("stack", [])
            tech_stack = ", ".join([s["name"] for s in stack_list])
            # Maybe use modules descriptions as rules
            modules = full_arch.get("modules", [])
            arch_summary += ". Modules: " + ", ".join([m["title"] for m in modules])
    except:
        pass

    # 5. Run Audit
    auditor = AuditService()
    report = auditor.run_architecture_audit(diff_data.get("files", []), arch_summary, tech_stack)
    
    return {
        "local_sha": local_sha,
        "remote_sha": remote_sha,
        "diff_stats": {
            "total_commits": diff_data.get("total_commits"),
            "changed_files": len(diff_data.get("files", []))
        },
        "audit_report": report
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
