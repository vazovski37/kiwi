import os
import sys
import requests
import base64
from dotenv import load_dotenv

import chromadb
from llama_index.core import (
    VectorStoreIndex,
    StorageContext,
    Settings,
    Document
)
from llama_index.core.node_parser import HierarchicalNodeParser, get_leaf_nodes
# Using the new Google GenAI classes
from llama_index.llms.google_genai import GoogleGenAI
from llama_index.embeddings.google_genai import GoogleGenAIEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core.retrievers import AutoMergingRetriever
from llama_index.core.query_engine import RetrieverQueryEngine

# Load environment variables
load_dotenv()

# --- CONFIGURATION ---
Settings.llm = GoogleGenAI(model=os.getenv("LLM_MODEL", "models/gemini-1.5-pro"))
Settings.embed_model = GoogleGenAIEmbedding(model=os.getenv("EMBEDDING_MODEL", "models/embedding-001"))

def fetch_github_files_manual(owner, repo, branch="main"):
    """
    Manually fetches files using the GitHub API to avoid library bugs.
    """
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print("❌ ERROR: GITHUB_TOKEN is missing.")
        sys.exit(1)
        
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # 1. Get the Git Tree (Recursive)
    print(f"🚀 Connecting to {owner}/{repo} ({branch})...")
    tree_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
    
    resp = requests.get(tree_url, headers=headers)
    if resp.status_code != 200:
        print(f"❌ Error fetching tree: {resp.status_code} - {resp.text}")
        return []
        
    tree_data = resp.json()
    
    # 2. Filter Files
    allowed_exts = (".py", ".js", ".jsx", ".ts", ".tsx", ".md", ".json", ".css", ".html", ".txt")
    target_files = [
        item for item in tree_data.get("tree", []) 
        if item["type"] == "blob" and item["path"].endswith(allowed_exts)
    ]
    
    print(f"🔍 Found {len(target_files)} relevant files. Downloading...")
    
    documents = []
    
    # 3. Download Content
    for file_info in target_files:
        # Use the 'raw' URL for cleaner text
        raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{file_info['path']}"
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
                print(f"   ok: {file_info['path']}")
            else:
                print(f"   ❌ Failed: {file_info['path']}")
        except Exception as e:
            print(f"   ⚠️ Error processing {file_info['path']}: {e}")
            
    return documents

def create_vector_store(persist_dir="./chroma_db"):
    db = chromadb.PersistentClient(path=persist_dir)
    chroma_collection = db.get_or_create_collection("kiwi_collection")
    return ChromaVectorStore(chroma_collection=chroma_collection)

def query_system(index, query_text):
    base_retriever = index.as_retriever(similarity_top_k=6)
    retriever = AutoMergingRetriever(
        base_retriever, index.storage_context, verbose=True
    )
    query_engine = RetrieverQueryEngine.from_args(retriever)
    return query_engine.query(query_text)

def main():
    GITHUB_OWNER = os.getenv("GITHUB_OWNER", "vazovski37")
    GITHUB_REPO = os.getenv("GITHUB_REPO", "sheukvete-frontend")
    GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main")
    
    # 1. Fetch Data Manually
    docs = fetch_github_files_manual(GITHUB_OWNER, GITHUB_REPO, GITHUB_BRANCH)
    
    if not docs:
        print("❌ No documents loaded. Exiting.")
        return

    print(f"📂 Successfully loaded {len(docs)} documents.")

    # 2. Parse Nodes
    print("🧠 Parsing Code Structure...")
    node_parser = HierarchicalNodeParser.from_defaults(chunk_sizes=[1024, 512, 128])
    nodes = node_parser.get_nodes_from_documents(docs)
    leaf_nodes = get_leaf_nodes(nodes)
    print(f"🌿 Created {len(nodes)} total nodes ({len(leaf_nodes)} leaves).")

    # 3. Vector Store
    vector_store = create_vector_store()
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    storage_context.docstore.add_documents(nodes)

    # 4. Index
    print("💾 Indexing to ChromaDB...")
    index = VectorStoreIndex(leaf_nodes, storage_context=storage_context)
    index.storage_context.persist(persist_dir="./chroma_db")
    
    print("✅ System Ready!")
    
    # 5. Test
    print("\n❓ Testing AI Knowledge...")
    response = query_system(index, "Explain the folder structure and the main purpose of this project.")
    print(f"\n🤖 AI Answer:\n{str(response)}")

if __name__ == "__main__":
    main()