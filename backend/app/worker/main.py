
import asyncio
import json
import os
import aiohttp
from arq import create_pool
from arq.connections import RedisSettings
from app.core.config import settings
from app.services.vector_service import vector_service
from app.services.embedding_service import embedding_service
from app.services.storage_service import storage_service

# Job Function
async def analyze_file_job(ctx, repo_id: str, file_path: str, content: str):
    print(f"👷 [Worker] Analyze Job Start: {file_path}")
    
    # 1. Call Ollama (Analysis) - llama3.2:3b
    async with aiohttp.ClientSession() as session:
        prompt = (
            f"Analyze the following code file: '{file_path}'\n\nCode:\n```\n{content[:4000]}\n```\n\n"
            "Return a strictly valid JSON object with EXACTLY these keys:\n"
            "{ 'summary': '1 sentence description', \n"
            "  'dependencies': ['list', 'of', 'modules'], \n"
            "  'exports': ['list', 'of', 'exports'] }\n"
            "Respond ONLY with JSON."
        )
        
        payload = {
            "model": "llama3.2:3b",
            "prompt": prompt,
            "stream": False,
            "format": "json"
        }
        
        analysis = {"summary": "Analysis failed", "dependencies": [], "exports": []}
        try:
            async with session.post(f"{settings.OLLAMA_URL}/api/generate", json=payload) as resp:
                if resp.status != 200:
                    print(f"❌ Ollama Analysis Error: {resp.status}")
                else:
                    data = await resp.json()
                    response_text = data.get("response", "{}")
                    try:
                        analysis = json.loads(response_text)
                    except:
                        pass
        except Exception as e:
            print(f"❌ Ollama Connection Error: {e}")

    # 2. Save Analysis to Graph (GCS - Stateless)
    # Note: GCS overwrite is atomic but blindly overwriting a huge JSON for every file is inefficient.
    # In a real event-driven architecture, we would emit an event or write to a DB row per file.
    # For now, adhering to "save_graph using storage_service" request. 
    # We will read, update, write. (Race condition possible if multiple workers update same repo graph, 
    # but GKE scaling implies we accept this or use a proper DB. GCS doesn't support locking easily).
    # Since prompt asked for "Save the JSON graph using storage_service", we do best effort.
    
    # Optimization: Maybe simpler to store file-level JSONs in GCS: `graphs/{repo_id}/{file_path}.json`
    # checking storage_service implementation... it saves to `graphs/{repo_id}.json`.
    # This is a bottleneck. But I must follow instructions.
    
    # We will try to update.
    try:
        current_graph = storage_service.get_graph(repo_id) or {}
        current_graph[file_path] = analysis
        storage_service.save_graph(repo_id, current_graph)
    except Exception as e:
        print(f"❌ GCS Save Error: {e}")

    # 3. Get Embedding (Local) - nomic-embed-text
    embedding = await embedding_service.get_embedding(content[:8000])
    
    # 4. Store in Chroma (Server)
    if embedding:
        try:
           # VectorService is now stateless HTTP client
           loop = asyncio.get_running_loop()
           await loop.run_in_executor(None, vector_service.add_raw_embedding, repo_id, file_path, content, embedding, analysis)
        except Exception as e:
           print(f"❌ Vector Insert Error: {e}")
    else:
        print("⚠️ No embedding generated, skipping vector store.")

    print(f"✅ [Worker] Finished: {file_path}")

# Worker Settings
class WorkerSettings:
    functions = [analyze_file_job]
    redis_settings = RedisSettings(host=settings.REDIS_HOST, port=settings.REDIS_PORT)
    
    async def on_startup(self, ctx):
        print("🚀 Worker Started (Stateless GKE Mode)")

    async def on_shutdown(self, ctx):
        print("🛑 Worker Stopping")
