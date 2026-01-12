
import os
import sys
import requests
import asyncio
import re
import json
import traceback
import chromadb
from dotenv import load_dotenv

from llama_index.core import (
    VectorStoreIndex,
    StorageContext,
    Settings,
    Document
)
from llama_index.core.node_parser import HierarchicalNodeParser, get_leaf_nodes
from llama_index.llms.google_genai import GoogleGenAI
from llama_index.embeddings.google_genai import GoogleGenAIEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core.retrievers import AutoMergingRetriever
from llama_index.core.query_engine import RetrieverQueryEngine

# Import SwarmService for local LLM analysis
from swarm_service import swarm_service

# Load environment variables
load_dotenv()

# --- CONFIGURATION ---
# Primary LLM for RAG (Robust/Pro)
Settings.llm = GoogleGenAI(model=os.getenv("LLM_MODEL", "models/gemini-1.5-pro"))
Settings.embed_model = GoogleGenAIEmbedding(model=os.getenv("EMBEDDING_MODEL", "models/embedding-001"))

def fetch_github_files_manual(owner, repo, branch="main"):
    """
    Manually fetches files using the GitHub API to avoid library bugs.
    """
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print("❌ ERROR: GITHUB_TOKEN is missing.")
        raise ValueError("GITHUB_TOKEN is missing")
        
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # 1. Get Repo Info (to find default branch if needed)
    repo_url = f"https://api.github.com/repos/{owner}/{repo}"
    print(f"🚀 Connecting to {owner}/{repo}...")
    repo_resp = requests.get(repo_url, headers=headers)
    
    default_branch = "main"
    if repo_resp.status_code == 200:
        default_branch = repo_resp.json().get("default_branch", "main")
    
    # 2. Get the Git Tree (Recursive)
    target_branch = branch
    tree_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{target_branch}?recursive=1"
    
    print(f"🔍 Fetching tree for branch: {target_branch}...")
    resp = requests.get(tree_url, headers=headers)
    
    if resp.status_code == 404 and target_branch != default_branch:
        print(f"⚠️ Branch '{target_branch}' not found. Falling back to default: '{default_branch}'")
        target_branch = default_branch
        tree_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{target_branch}?recursive=1"
        resp = requests.get(tree_url, headers=headers)

    if resp.status_code != 200:
        print(f"❌ Error fetching tree: {resp.status_code} - {resp.text}")
        return []
        
    tree_data = resp.json()
    
    # 2. Filter Files
    allowed_exts = (".py", ".js", ".jsx", ".ts", ".tsx", ".md", ".json", ".css", ".html", ".txt")
    excluded_files = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "composer.lock", "Cargo.lock"}
    
    target_files = [
        item for item in tree_data.get("tree", []) 
        if item["type"] == "blob" 
        and item["path"].endswith(allowed_exts)
        and item["path"].split("/")[-1] not in excluded_files
    ]
    
    print(f"🔍 Found {len(target_files)} relevant files. Downloading...")
    
    documents = []
    
    # 3. Download Content
    for file_info in target_files:
        # Use the 'raw' URL for cleaner text
        raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{target_branch}/{file_info['path']}"
        try:
            file_resp = requests.get(raw_url, headers=headers)
            if file_resp.status_code == 200:
                text_content = file_resp.text
                
                # Create a LlamaIndex Document
                doc = Document(
                    text=text_content,
                    metadata={
                        "file_path": file_info['path'],
                        "file_name": file_info['path'].split("/")[-1],
                        "url": raw_url
                    }
                )
                documents.append(doc)
            else:
                print(f"   ❌ Failed: {file_info['path']}")
        except Exception as e:
            print(f"   ⚠️ Error processing {file_info['path']}: {e}")
            
    return documents

def get_repo_collection_name(repo_id):
    # Ensure safe collection name (alphanumeric, underscores)
    return f"kiwi_{repo_id.replace('-', '_')}"

# --- FEATURE A: REPO MAP GENERATOR ---
def generate_repo_map(documents):
    print("🗺️ Generating Repo Map using Regex analysis...")
    map_lines = []
    
    # Tech Stack Extraction (package.json)
    tech_stack_header = []
    for doc in documents:
        if doc.metadata.get("file_name") == "package.json":
            try:
                data = json.loads(doc.text)
                tech_stack_header.append("--- TECH STACK ---")
                
                deps = data.get("dependencies", {})
                if deps:
                    tech_stack_header.append("Dependencies:")
                    for pkg, ver in deps.items():
                        tech_stack_header.append(f"  {pkg}: {ver}")
                        
                dev_deps = data.get("devDependencies", {})
                if dev_deps:
                    tech_stack_header.append("DevDependencies:")
                    for pkg, ver in dev_deps.items():
                        tech_stack_header.append(f"  {pkg}: {ver}")
                
                tech_stack_header.append("------------------")
            except Exception as e:
                print(f"⚠️ Failed to parse package.json: {e}")

    # Patterns to capture signatures
    patterns = [
        r'^\s*(import\s+.+)',
        r'^\s*(from\s+.+\s+import\s+.+)',
        r'^\s*(class\s+\w+)',
        r'^\s*(def\s+\w+)',
        r'^\s*(async\s+def\s+\w+)',
        r'^\s*(function\s+\w+)',
        r'^\s*(export\s+.+)',
        r'^\s*(interface\s+\w+)',
    ]
    combined_pattern = re.compile('|'.join(patterns), re.MULTILINE)

    for doc in documents:
        file_path = doc.metadata.get("file_path", "unknown")
        map_lines.append(f"\n📄 File: {file_path}")
        
        # Scan content
        matches = combined_pattern.findall(doc.text)
        if matches:
            for match_tuple in matches:
                # findall returns tuple of groups, filter empty
                signature = next((m for m in match_tuple if m), "")
                if signature:
                    # Truncate if too long
                    if len(signature) > 80:
                        signature = signature[:77] + "..."
                    map_lines.append(f"  └─ {signature.strip()}")
        else:
             map_lines.append("  (No signatures found)")
             
    # Prepend Tech Stack if found
    if tech_stack_header:
        final_map = "\n".join(tech_stack_header) + "\n" + "\n".join(map_lines)
    else:
        final_map = "\n".join(map_lines)
        
    return final_map

# --- FEATURE B: SWARM ANALYSIS (via SwarmService) ---
# Swarm analysis now uses local Ollama LLM via swarm_service.py

# --- MAIN INGESTION ---
def ingest_repo(owner, repo, branch="main"):
    repo_id = f"{owner}-{repo}-{branch}"
    collection_name = get_repo_collection_name(repo_id)
    persist_dir = "./chroma_db"
    
    print(f"📥 Ingesting repo: {repo_id} into collection: {collection_name}")
    
    # 1. Fetch
    docs = fetch_github_files_manual(owner, repo, branch)
    if not docs:
        raise Exception("No documents found or failed to fetch.")
        
    # --- DUAL-LAYER GENERATION ---
    
    # 2A. Generate Repo Map
    repo_map_content = generate_repo_map(docs)
    os.makedirs("./maps", exist_ok=True)
    with open(f"./maps/{repo_id}.txt", "w", encoding="utf-8") as f:
        f.write(repo_map_content)
    print(f"🗺️ Repo Map saved to ./maps/{repo_id}.txt")
    
    # 2B. Run Swarm Analysis (using local Ollama LLM)
    try:
        # Run async loop via SwarmService
        repo_graph = asyncio.run(swarm_service.run_swarm_analysis(docs))
        os.makedirs("./graphs", exist_ok=True)
        with open(f"./graphs/{repo_id}.json", "w", encoding="utf-8") as f:
            json.dump(repo_graph, f, indent=2)
        print(f"🕸️ Dependency Graph saved to ./graphs/{repo_id}.json")
    except Exception as e:
        print(f"⚠️ Swarm Analysis failed: {e}")
        # Continue to indexing logic - robust fallback
        
    # 3. Parse & Index
    print("🧠 Parsing Code Structure for Vector Index...")
    node_parser = HierarchicalNodeParser.from_defaults(chunk_sizes=[1024, 512, 128])
    nodes = node_parser.get_nodes_from_documents(docs)
    leaf_nodes = get_leaf_nodes(nodes)
    print(f"🌿 Created {len(nodes)} total nodes ({len(leaf_nodes)} leaves).")
    
    # 3. Vector Store
    print("🔌 Connecting to ChromaDB PersistentClient...", flush=True)
    db = chromadb.PersistentClient(path=persist_dir)
    
    # --- RESET COLLECTION ---
    try:
        print(f"🗑️ Attempting to delete collection: {collection_name}", flush=True)
        db.delete_collection(collection_name)
        print(f"🗑️ Cleared existing collection: {collection_name}")
    except ValueError:
        print(f"ℹ️ Collection {collection_name} did not exist.", flush=True)
    except Exception as e:
        print(f"⚠️ Error deleting collection: {e}", flush=True)

    print("📦 Creating/Getting collection...", flush=True)
    chroma_collection = db.get_or_create_collection(collection_name)
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    
    print("🛠️ Creating StorageContext...", flush=True)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    print(f"📝 Adding {len(nodes)} nodes to docstore...", flush=True)
    storage_context.docstore.add_documents(nodes)
    print("✅ documents added to docstore.", flush=True)
    
    # 4. Index
    print(f"💾 Indexing to ChromaDB ({collection_name})...")
    index = VectorStoreIndex(leaf_nodes, storage_context=storage_context)
    
    # Important: Persist!
    repo_storage_dir = f"./chroma_db/storage_{repo_id}"
    if os.path.exists(repo_storage_dir):
        import shutil
        shutil.rmtree(repo_storage_dir)
    os.makedirs(repo_storage_dir, exist_ok=True)
    
    index.storage_context.persist(persist_dir=repo_storage_dir)
    
    print("✅ Ingestion Complete.")
    return repo_id

def load_index_for_repo(repo_id):
    # Same as before
    collection_name = get_repo_collection_name(repo_id)
    repo_storage_dir = f"./chroma_db/storage_{repo_id}"
    
    if not os.path.exists(repo_storage_dir):
        raise ValueError(f"Storage for {repo_id} not found. Has it been ingested?")
        
    print(f"📂 Loading index for {repo_id}...")
    
    # Load Chroma
    db = chromadb.PersistentClient(path="./chroma_db")
    chroma_collection = db.get_or_create_collection(collection_name)
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    
    # Load Storage Context (Docstore)
    storage_context = StorageContext.from_defaults(
        vector_store=vector_store, persist_dir=repo_storage_dir
    )
    
    return VectorStoreIndex.from_vector_store(
        vector_store, storage_context=storage_context
    )

def query_module(index, module_name):
    print(f"🕵️ Investigating '{module_name}'...", flush=True)
    prompt = f"Analyze the codebase specifically for '{module_name}'. Describe key files, logic flows, UI, and data interactions. Be technical."
    
    try:
        base_retriever = index.as_retriever(similarity_top_k=10)
        retriever = AutoMergingRetriever(
            base_retriever, index.storage_context, verbose=False
        )
        query_engine = RetrieverQueryEngine.from_args(retriever)
        return str(query_engine.query(prompt))
    except Exception as e:
        print(f"   ⚠️ AMR failed: {e}. Fallback...", flush=True)
        return str(index.as_query_engine(similarity_top_k=10).query(prompt))

def generate_architecture_json(repo_id):
    print(f"🏛️ Generating JSON Architecture for {repo_id}...")
    
    try:
        index = load_index_for_repo(repo_id)
        
        # Gather reports (keep this RAG logic, it's good)
        modules = ["Authentication", "Admin Dashboard", "Waiter System", "Kitchen Display", "Database Schemas", "Folder Structure", "UI Components", "API Routes"]
        reports = {}
        for mod in modules:
            reports[mod] = query_module(index, mod)
            
        reports_text = "\n".join([f"\n--- Report: {m} ---\n{c}\n" for m, c in reports.items()])
        
        # Load Map/Graph for extra context if available
        repo_map_path = f"./maps/{repo_id}.txt"
        repo_map = ""
        if os.path.exists(repo_map_path):
             with open(repo_map_path, "r", encoding="utf-8") as f:
                 repo_map = f.read()

        system_prompt = (
            "You are the Principal AI Architect. Your goal is to generate a system architecture description in STRICT JSON format.\n"
            "Input Context:\n"
            f"=== REPO MAP ===\n{repo_map[:5000]}\n" # limit
            f"=== RAG REPORTS ===\n{reports_text}\n\n"
            "You MUST output a single valid JSON object matching this schema EXACTLY:\n"
            "{\n"
            "  \"meta\": {\n"
            "    \"project_name\": \"Inferred Name\",\n"
            "    \"one_line_summary\": \"Catchy pitch...\",\n"
            "    \"stats\": { \"language\": \"TypeScript\", \"complexity\": \"High\" }\n"
            "  },\n"
            "  \"stack\": [\n"
            "    { \"name\": \"Next.js\", \"category\": \"Framework\" },\n"
            "    { \"name\": \"Tailwind\", \"category\": \"Styling\" }\n"
            "  ],\n"
            "  \"modules\": [\n"
            "    { \"title\": \"Auth\", \"description\": \"...\", \"key_files\": [\"src/auth.ts\"] }\n"
            "  ],\n"
            "  \"flow\": [\n"
            "    { \"step\": 1, \"label\": \"User Login\", \"details\": \"Calls /api/auth\" }\n"
            "  ],\n"
            "  \"mermaid\": \"graph TD...\"\n"
            "}\n\n"
            "MERMAID RULES:\n"
            "1. Use `graph TD` or `graph LR`.\n"
            "2. Enclose ALL node labels in double quotes. Example: A[\"Login (Page)\"].\n"
            "3. Do NOT use special characters in Node IDs. Use CamelCase.\n"
            "4. The JSON string for mermaid must be valid (escape quotes if needed).\n\n"
            "Respond ONLY with the JSON string."
        )
        
        # Re-instantiating to be safe, or just use Settings.llm
        response = Settings.llm.complete(system_prompt)
        text = response.text.strip()
        
        if text.startswith("```json"):
            text = text[7:-3]
        elif text.startswith("```"):
            text = text[3:-3]
            
        # Parse to ensure validity
        json_obj = json.loads(text)
        
        output_dir = "./architectures"
        os.makedirs(output_dir, exist_ok=True)
        # Save as .json now
        output_file = f"{output_dir}/{repo_id}.json"
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(json_obj, f, indent=2)
            
        print(f"🎉 Architecture JSON saved to {output_file}")
        return output_file
        
    except Exception as e:
        print(f"❌ Architecture JSON generation failed: {e}")
        traceback.print_exc()
        raise e
