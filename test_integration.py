import asyncio
from swarm_service import swarm_service
from llama_index.core import Document

async def main():
    print("🧪 Starting Swarm Integration Test")
    print("----------------------------------")
    
    # 1. Create Dummy Documents
    docs = [
        Document(text="import os\nprint('File 1')", metadata={"file_path": "test_1.py"}),
        Document(text="import sys\ndef test(): pass", metadata={"file_path": "test_2.py"}),
        Document(text="import json\nclass Config: pass", metadata={"file_path": "test_3.py"}),
    ]
    
    # 2. Run Analysis
    print(f"📄 Submitting {len(docs)} docs to SwarmService...")
    start = asyncio.get_event_loop().time()
    
    results = await swarm_service.run_swarm_analysis(docs)
    
    duration = asyncio.get_event_loop().time() - start
    
    # 3. Validate
    print("----------------------------------")
    print(f"⏱️ Duration: {duration:.2f}s")
    print(f"📊 Results Received: {len(results)}")
    
    for fname, data in results.items():
        summary = data.get("summary", "No Summary")[:40]
        status = "✅" if "summary" in data and "Error" not in summary else "❌"
        print(f"{status} {fname}: {summary}...")

    if len(results) == len(docs):
        print("\n✅ INTEGRATION SUCCESSFUL: The Swarm is connected!")
    else:
        print("\n❌ INTEGRATION FAILED: Some results missing.")

if __name__ == "__main__":
    asyncio.run(main())
