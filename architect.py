import os
import sys
import asyncio
from dotenv import load_dotenv
import chromadb
import nest_asyncio

from llama_index.core import (
    VectorStoreIndex,
    StorageContext,
    Settings,
)
from llama_index.llms.google_genai import GoogleGenAI
from llama_index.embeddings.google_genai import GoogleGenAIEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core.retrievers import AutoMergingRetriever
from llama_index.core.query_engine import RetrieverQueryEngine

# Apply nest_asyncio
nest_asyncio.apply()

# Load environment variables
load_dotenv()

# --- CONFIGURATION ---
Settings.llm = GoogleGenAI(model=os.getenv("LLM_MODEL", "models/gemini-1.5-pro"))
Settings.embed_model = GoogleGenAIEmbedding(model=os.getenv("EMBEDDING_MODEL", "models/embedding-001"))


def get_vector_index(persist_dir="./chroma_db"):
    """
    Load the existing ChromaDB index.
    """
    if not os.path.exists(persist_dir):
        print(f"❌ Error: Database not found at {persist_dir}. Please run indexer.py first.")
        sys.exit(1)

    print(f"📂 Loading database from {persist_dir}...")
    db = chromadb.PersistentClient(path=persist_dir)
    chroma_collection = db.get_or_create_collection("kiwi_collection")
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    storage_context = StorageContext.from_defaults(
        vector_store=vector_store, persist_dir=persist_dir
    )
    print(f"   📊 Docstore loaded with {len(storage_context.docstore.docs)} documents.", flush=True)
    
    return VectorStoreIndex.from_vector_store(
        vector_store, storage_context=storage_context
    )


def query_module(index, module_name):
    """
    Sub-Agent: Queries the specific module topic.
    """
    print(f"🕵️ Agent dispatch: Investigating '{module_name}'...", flush=True)
    prompt = (
        f"Analyze the codebase specifically for the '{module_name}' module. "
        "Describe its key files, logic flows, UI components (if any), and data interactions. "
        "Be technical and specific."
    )
    
    # Try AutoMergingRetriever first
    try:
        base_retriever = index.as_retriever(similarity_top_k=10)
        retriever = AutoMergingRetriever(
            base_retriever, index.storage_context, verbose=False
        )
        query_engine = RetrieverQueryEngine.from_args(retriever)
        response = query_engine.query(prompt)
        return str(response)
    except Exception as e:
        print(f"   ⚠️ AutoMergingRetriever failed for '{module_name}': {e}")
        print("   🔄 Falling back to standard query engine...", flush=True)
        query_engine = index.as_query_engine(similarity_top_k=10)
        response = query_engine.query(prompt)
        return str(response)

# async def main(): ... -> update setup logic



async def main():
    # 1. Initialize
    index = get_vector_index()
    
    # 2. Define Sub-Agents (The "Swarm")
    modules_to_investigate = [
        "Authentication",
        "Admin Dashboard",
        "Waiter System",
        "Kitchen Display",
        "Database Schemas",
    ]

    module_reports = {}

    # 3. Dispatch Agents
    print("\n🐝 Swarm initialized. Dispatching agents...\n", flush=True)
    for module in modules_to_investigate:
        # Pass index directly to allow fallback logic inside handler
        report = query_module(index, module)
        module_reports[module] = report
        print(f"✅ Report received for '{module}'.\n", flush=True)

    # 4. The Master Architect (Synthesis)
    print("🏛️  Chief Architect is synthesizing the final architecture...\n")
    
    # Construct the final prompt
    reports_text = ""
    for module, content in module_reports.items():
        reports_text += f"\n--- Report: {module} ---\n{content}\n"

    final_prompt = (
        "You are the Principal AI Architect. You have received detailed reports from your sub-agents "
        "regarding different parts of a software system. "
        "Your goal is to write a comprehensive `ARCHITECTURE.md` file.\n\n"
        f"Here are the Agent Reports:\n{reports_text}\n\n"
        "Instructions:\n"
        "1. Write a professional System Architecture Document using Markdown.\n"
        "2. Include sections for: Introduction, Tech Stack (infer from context of reports), "
        "Module Details (synthesize the reports), and Data Flow.\n"
        "3. CRITICAL: Include a sophisticated Mermaid.js System Diagram (graph TD or classDiagram) "
        "that visualizes the relationships between these modules.\n"
        "4. Output ONLY the markdown content for the file."
    )

    # Use the LLM directly for the final synthesis (bypassing RAG context window limits if we just want synthesis, 
    # but using the query engine might be safer if we want it to 'know' it's answering a query. 
    # However, standard llm.complete is better for pure synthesis of provided text).
    
    response = Settings.llm.complete(final_prompt)
    
    # 5. Output
    output_file = "ARCHITECTURE.md"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(str(response))
        
    print(f"🎉 Success! Architecture document generated at: {output_file}")


if __name__ == "__main__":
    asyncio.run(main())
