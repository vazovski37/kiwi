# Backend Codebase Dump

## File: `backend/.env`
```
GITHUB_TOKEN=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
GOOGLE_API_KEY=AIzaSyBYKQwFow2h8EMJb6O5gLLrJnWJTEHtmfQ
LLM_MODEL=gemini-2.0-flash-lite
EMBEDDING_MODEL=gemini-embedding-001
GCS_BUCKET_NAME=kiwi-hackathon-graphs
SWARM_MODEL=llama3.2:3b
EMBEDDING_MODEL=nomic-embed-text
```

## File: `backend/docker-compose.yml`
```

version: '3.8'

services:
  redis:
    image: redis:alpine
    ports:
      - "6379:6379"

  chroma:
    image: chromadb/chroma:latest
    ports:
      - "8000:8000"
    volumes:
      - chroma_data:/chroma/chroma
    environment:
      - CHROMA_SERVER_HOST=0.0.0.0
      - CHROMA_SERVER_HTTP_PORT=8000

  ollama:
    image: ollama/ollama
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    healthcheck:
      test: ["CMD", "ollama", "list"]
      interval: 5s
      timeout: 3s
      retries: 5

  init-ollama:
    image: curlimages/curl
    depends_on:
      ollama:
        condition: service_healthy
    entrypoint: >
      /bin/sh -c "
      echo 'Waiting for Ollama...';
      sleep 5;
      echo 'Pulling llama3.2:3b...';
      curl -X POST http://ollama:11434/api/pull -d '{\"name\": \"llama3.2:3b\"}';
      echo 'Pulling nomic-embed-text...';
      curl -X POST http://ollama:11434/api/pull -d '{\"name\": \"nomic-embed-text\"}';
      echo 'Done!';
      "

  api:
    build:
      context: .
      dockerfile: Dockerfile.api
    ports:
      - "8080:8000" # Expose on 8080 to avoid conflict with Chroma
    environment:
      - REDIS_HOST=redis
      - CHROMA_HOST=chroma
      - CHROMA_PORT=8000
      - OLLAMA_URL=http://ollama:11434
      - GOOGLE_API_KEY=${GOOGLE_API_KEY}
      - GCS_BUCKET_NAME=${GCS_BUCKET_NAME}
      - GOOGLE_APPLICATION_CREDENTIALS=/app/gcp-key.json # Mock/Mount if needed
    depends_on:
      - redis
      - ollama
      - chroma
    volumes:
      - ./db:/backend/db 
      # GCS Warning: without real creds, storage_service will fail locally unless mocked or creds provided.
      
  worker:
    build:
      context: .
      dockerfile: Dockerfile.worker
    deploy:
      replicas: 2
    environment:
      - REDIS_HOST=redis
      - CHROMA_HOST=chroma
      - CHROMA_PORT=8000
      - OLLAMA_URL=http://ollama:11434
      - GOOGLE_API_KEY=${GOOGLE_API_KEY}
      - GCS_BUCKET_NAME=${GCS_BUCKET_NAME}
    depends_on:
      - redis
      - ollama
      - chroma

volumes:
  ollama_data:
  chroma_data:

```

## File: `backend/Dockerfile.api`
```

FROM python:3.11-slim

WORKDIR /backend

# Install system dependencies (git for optional clone, build tools)
RUN apt-get update && apt-get install -y git build-essential && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Environment
ENV PYTHONPATH=/backend

CMD ["uvicorn", "app.api.server:app", "--host", "0.0.0.0", "--port", "8000"]

```

## File: `backend/Dockerfile.worker`
```

FROM python:3.11-slim

WORKDIR /backend

RUN apt-get update && apt-get install -y git build-essential && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONPATH=/backend

# ARQ worker startup
CMD ["arq", "app.worker.main.WorkerSettings"]

```

## File: `backend/requirements.txt`
```

fastapi
uvicorn
requests
python-dotenv
chromadb
llama-index
llama-index-readers-github
llama-index-llms-gemini
llama-index-embeddings-gemini
llama-index-vector-stores-chroma
google-generativeai
arq
aiohttp
pydantic-settings
isort
pytest

```

## File: `backend/app/api/server.py`
```

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.endpoints import ingest, chat, audit

app = FastAPI(title=settings.APP_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def health_check():
    return {"status": "online", "service": "Kiwi API"}

app.include_router(ingest.router, prefix="/api", tags=["Ingest"])
app.include_router(chat.router, prefix="/api", tags=["Chat"])
app.include_router(audit.router, prefix="/api/updates", tags=["Audit"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

```

## File: `backend/app/api/endpoints/audit.py`
```

from fastapi import APIRouter, HTTPException
from app.core.database import db
from app.services.github_service import GithubService
from app.services.audit_service import AuditService
from app.core.config import settings
import json
import os

router = APIRouter()

@router.get("/check/{repo_id}")
def check_updates(repo_id: str):
    repo = db.get(repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repo not found")
        
    local_sha = repo.get("current_sha")
    # Parse URL 
    parts = repo["url"].rstrip("/").split("/")
    repo_name = parts[-1]
    owner = parts[-2]
    
    gh = GithubService()
    remote_sha = gh.get_current_sha(owner, repo_name, repo["branch"])
    
    return {
        "local_sha": local_sha,
        "remote_sha": remote_sha,
        "has_updates": local_sha != remote_sha
    }

@router.post("/audit/{repo_id}")
def audit_updates(repo_id: str):
    repo = db.get(repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repo not found")
    
    parts = repo["url"].rstrip("/").split("/")
    repo_name = parts[-1]
    owner = parts[-2]
    
    gh = GithubService()
    remote_sha = gh.get_current_sha(owner, repo_name, repo["branch"])
    local_sha = repo.get("current_sha")
    
    if local_sha == remote_sha:
        return {"status": "UP_TO_DATE"}
        
    diffs = gh.compare_commits(owner, repo_name, local_sha, remote_sha)
    if diffs.get("status") == "error":
        raise HTTPException(status_code=500, detail=diffs.get("error"))
        
    # Get Arch context (from wherever it is stored)
    # Since we are in microservices, we assume existing arch files are in `backend/architectures` or similar.
    # Worker writes to `graphs`, API might need to generate architecture later?
    # For now, minimal context.
    
    auditor = AuditService()
    report = auditor.run_architecture_audit(diffs.get("files", []), "Project Architecture", "Unknown Stack")
    
    return report

```

## File: `backend/app/api/endpoints/chat.py`
```

from fastapi import APIRouter, HTTPException
from app.schemas.requests import ChatRequest
from app.services.vector_service import vector_service
from app.services.embedding_service import embedding_service
from app.core.config import settings
from llama_index.llms.google_genai import GoogleGenAI
from llama_index.core.llms import ChatMessage

router = APIRouter()

@router.post("/chat")
async def chat(request: ChatRequest):
    repo_id = request.repo_id
    
    # 1. Get Embedding for Question (Ollama)
    query_embedding = await embedding_service.get_embedding(request.message)
    if not query_embedding:
        raise HTTPException(status_code=500, detail="Failed to generate query embedding.")
    
    # 2. Query ChromaDB directly (Hybrid RAG approach)
    try:
        # Access raw client to query with embedding
        collection_name = f"kiwi_{repo_id.replace('-', '_')}"
        collection = vector_service.chroma_client.get_collection(collection_name)
        
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=5
        )
        
        # Parse results
        docs = results['documents'][0]
        metadatas = results['metadatas'][0]
        
        context_str = ""
        for i, doc in enumerate(docs):
            path = metadatas[i].get('file_path', 'unknown')
            context_str += f"\n--- File: {path} ---\n{doc}\n"
            
    except Exception as e:
        print(f"❌ Retrieval Error: {e}")
        # Proceed with empty context if fail?
        context_str = "No context retrieved due to error."

    # 3. Generate Answer (Gemini 1.5 Pro)
    # Using LlamaIndex LLM wrapper convenient for completion
    try:
        llm = GoogleGenAI(model=settings.LLM_MODEL, api_key=settings.GOOGLE_API_KEY)
        
        system_prompt = (
            "You are a Senior Software Architect.\n"
            "Answer the user's question based on the provided Code Context.\n"
            "If the context doesn't contain the answer, say so.\n"
        )
        
        prompt = f"Context:\n{context_str}\n\nQuestion: {request.message}"
        
        messages = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=prompt)
        ]
        
        response = llm.chat(messages)
        return {"response": response.message.content}
        
    except Exception as e:
        print(f"❌ Generation Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

```

## File: `backend/app/api/endpoints/ingest.py`
```

import os
import shutil
import zipfile
import requests
import io
import asyncio
from fastapi import APIRouter, HTTPException
from arq import create_pool
from arq.connections import RedisSettings

from app.schemas.requests import IngestRequest
from app.core.config import settings
from app.core.database importdb
from app.services.github_service import GithubService

router = APIRouter()

@router.post("/ingest")
async def ingest_repo(request: IngestRequest):
    """
    Ingests a repo by downloading the zip, extracting, and enqueuing analysis jobs.
    """
    try:
        parts = request.url.rstrip("/").split("/")
        repo_name = parts[-1]
        owner = parts[-2]
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid GitHub URL.")

    # 1. Register in DB (Living Twin)
    gh = GithubService()
    current_sha = gh.get_current_sha(owner, repo_name, request.branch) or "unknown"
    repo_id = f"{owner}-{repo_name}-{request.branch}".replace("/", "-") # normalize
    
    db.upsert({
        "repo_id": repo_id,
        "url": request.url,
        "branch": request.branch,
        "current_sha": current_sha,
        "meta": {"status": "ingesting"}
    })

    # 2. Download ZIP
    zip_url = f"https://github.com/{owner}/{repo_name}/archive/refs/heads/{request.branch}.zip"
    print(f"⬇️ Downloading {zip_url}...")
    try:
        resp = requests.get(zip_url, headers=gh.headers) # Reuse auth if possible?
        # gh.headers includes token? Yes.
        if resp.status_code != 200:
             raise Exception(f"GitHub Zip Download Failed: {resp.status_code}")
        
        # 3. Unzip
        # Temp dir
        temp_dir = os.path.join(settings.BASE_DIR, "temp", repo_id)
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        os.makedirs(temp_dir, exist_ok=True)
        
        with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
            z.extractall(temp_dir)
            
        print(f"📂 Extracted to {temp_dir}")
        
    except Exception as e:
        print(f"❌ Ingest Failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    # 4. Enqueue Jobs
    # Connect to Redis
    redis = await create_pool(RedisSettings(host=settings.REDIS_HOST, port=settings.REDIS_PORT))
    
    jobs_enqueued = 0
    
    # Walk directory
    # Structure is usually temp_dir/repo-branch/files...
    # Find root inside temp
    extracted_root = next(os.path.join(temp_dir, d) for d in os.listdir(temp_dir) if os.path.isdir(os.path.join(temp_dir, d)))
    
    allowed_exts = (".py", ".js", ".ts", ".tsx", ".java", ".go", ".md", ".json")
    
    for root, dirs, files in os.walk(extracted_root):
        for file in files:
            if file.endswith(allowed_exts):
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, extracted_root)
                
                # Check exclusion
                if any(x in rel_path for x in ["node_modules", ".git", "venv", "__pycache__"]):
                    continue
                    
                try:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    
                    # Enqueue
                    await redis.enqueue_job('analyze_file_job', repo_id, rel_path, content)
                    jobs_enqueued += 1
                except Exception as e:
                    print(f"⚠️ Skipped {rel_path}: {e}")
    
    await redis.close()
    
    return {
        "status": "ingest_queued",
        "repo_id": repo_id,
        "jobs": jobs_enqueued
    }

```

## File: `backend/app/core/config.py`
```

import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "Kiwi Backend"
    
    # Paths
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    DB_PATH: str = os.path.join(BASE_DIR, "db", "repos.json")
    
    # Redis
    REDIS_HOST: str = "localhost" # 'redis' in docker
    REDIS_PORT: int = 6379
    
    # AI - Gemini
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "models/gemini-1.5-pro-latest")
    
    # AI - Ollama
    OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
    
    # GitHub
    GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")

    # Storage (GCS)
    GCS_BUCKET_NAME: str = os.getenv("GCS_BUCKET_NAME", "kiwi-graphs")
    
    # Vector DB (Chroma Server)
    CHROMA_HOST: str = os.getenv("CHROMA_HOST", "chroma")
    CHROMA_PORT: int = 8000

    class Config:
        env_file = ".env"

settings = Settings()

```

## File: `backend/app/core/database.py`
```

import os
import json
from datetime import datetime
from app.core.config import settings

class RepoDB:
    def __init__(self, db_path=None):
        self.db_path = db_path or settings.DB_PATH
        self._ensure_db()

    def _ensure_db(self):
        """Ensures the database directory and file exist."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        if not os.path.exists(self.db_path):
            with open(self.db_path, "w", encoding="utf-8") as f:
                json.dump({}, f, indent=2)

    def _load(self):
        """Loads the database from disk."""
        try:
            with open(self.db_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save(self, data):
        """Saves the database to disk."""
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def get_all(self):
        """Returns all repositories as a list of values."""
        data = self._load()
        return list(data.values())

    def get(self, repo_id):
        """Returns a specific repository by ID, or None."""
        data = self._load()
        return data.get(repo_id)

    def upsert(self, repo_data):
        """
        Inserts or updates a repository record.
        repo_data must have 'repo_id'.
        """
        if "repo_id" not in repo_data:
            raise ValueError("repo_data must contain 'repo_id'")
            
        data = self._load()
        repo_id = repo_data["repo_id"]
        
        # Merge if exists, or create new
        if repo_id in data:
            data[repo_id].update(repo_data)
        else:
            data[repo_id] = repo_data
            
        # Update timestamp
        data[repo_id]["last_updated"] = datetime.utcnow().isoformat() + "Z"
        
        self._save(data)
        return data[repo_id]

# Singleton instance
db = RepoDB()

```

## File: `backend/app/schemas/requests.py`
```

from pydantic import BaseModel
from typing import Optional

class IngestRequest(BaseModel):
    url: str
    branch: str = "main"

class ChatRequest(BaseModel):
    repo_id: str
    message: str

class AuditRequest(BaseModel):
    # If explicit request is needed, otherwise generic trigger
    pass

```

## File: `backend/app/services/audit_service.py`
```

import json
import traceback
from llama_index.core import Settings

class AuditService:
    def __init__(self):
        # We assume Settings.llm is already configured in the app startup
        pass

    def run_architecture_audit(self, diffs, architecture_summary, tech_stack):
        """
        Audits the provided diffs against the project architecture and tech stack.
        """
        print("🕵️ AuditService: Analyzing changes...")
        
        diff_str = json.dumps(diffs, indent=2)
        
        prompt = (
            "You are the Gatekeeper Architect for this project.\n"
            f"Project Rules / Architecture: {architecture_summary}\n"
            f"Tech Stack: {tech_stack}\n\n"
            "Incoming Changes (Git Diffs):\n"
            f"{diff_str}\n\n"
            "Mission:\n"
            "1. Analyze IF these specific changes violate the project structure (e.g., direct DB calls in UI, wrong file placement, spaghetti code).\n"
            "2. Check for security risks or bad practices in the new code (hardcoded secrets, SQL injection, etc).\n"
            "3. Ignore huge refactors or deleted files unless critical; focus on the logic changes provided.\n\n"
            "Output JSON ONLY:\n"
            "{\n"
            "  \"score\": 0-100 (Integer representation of code quality/compliance),\n"
            "  \"status\": \"APPROVED\" | \"WARNING\" | \"CRITICAL\",\n"
            "  \"summary\": \"Brief executive summary of the changes.\",\n"
            "  \"issues\": [\n"
            "    { \"file\": \"src/auth.ts\", \"severity\": \"high\", \"message\": \"Hardcoded secret detected.\" }\n"
            "  ]\n"
            "}\n"
            "Respond ONLY with valid JSON."
        )
        
        try:
            response = Settings.llm.complete(prompt)
            text = response.text.strip()
            
            # Clean md blocks
            if text.startswith("```json"):
                text = text[7:-3]
            elif text.startswith("```"):
                text = text[3:-3]
                
            return json.loads(text)
            
        except Exception as e:
            print(f"❌ AuditService Failed: {e}")
            traceback.print_exc()
            return {
                "score": 0,
                "status": "ERROR",
                "summary": "AI Audit failed to execute.",
                "issues": [{"file": "N/A", "severity": "critical", "message": str(e)}]
            }

```

## File: `backend/app/services/embedding_service.py`
```

import aiohttp
import asyncio
from typing import List
from app.core.config import settings

class EmbeddingService:
    def __init__(self):
        self.base_url = settings.OLLAMA_URL
        self.model = "nomic-embed-text"

    async def get_embedding(self, text: str) -> List[float]:
        """
        Generates embedding for a single string using Ollama.
        """
        async with aiohttp.ClientSession() as session:
            payload = {
                "model": self.model,
                "prompt": text
            }
            
            try:
                async with session.post(f"{self.base_url}/api/embeddings", json=payload) as resp:
                    if resp.status != 200:
                        print(f"❌ Embedding Error: {resp.status} - {await resp.text()}")
                        return []
                    
                    data = await resp.json()
                    return data.get("embedding", [])
            except Exception as e:
                print(f"❌ Embedding Connection Error: {e}")
                return []

# Singleton
embedding_service = EmbeddingService()

```

## File: `backend/app/services/github_service.py`
```

import os
import requests
from app.core.config import settings

class GithubService:
    def __init__(self):
        self.token = settings.GITHUB_TOKEN
        
        self.headers = {
            "Authorization": f"Bearer {self.token}" if self.token else "",
            "Accept": "application/vnd.github.v3+json"
        }
        # Remove empty auth if no token
        if not self.token:
            if "Authorization" in self.headers:
                del self.headers["Authorization"]

    def get_branches(self, owner, repo):
        """
        Returns a list of branch names for the repository.
        """
        url = f"https://api.github.com/repos/{owner}/{repo}/branches"
        print(f"🔍 Fetching branches for {owner}/{repo}...")
        
        try:
            resp = requests.get(url, headers=self.headers)
            if resp.status_code == 200:
                data = resp.json()
                return [b["name"] for b in data]
            else:
                print(f"❌ Failed to fetch branches: {resp.status_code} - {resp.text}")
                return []
        except Exception as e:
            print(f"❌ GithubService Error: {e}")
            return []

    def get_current_sha(self, owner, repo, branch="main"):
        """
        Returns the SHA of the HEAD commit for the specified branch.
        """
        url = f"https://api.github.com/repos/{owner}/{repo}/commits/{branch}"
        print(f"🔍 Fetching SHA for {owner}/{repo} on {branch}...")
        
        try:
            resp = requests.get(url, headers=self.headers)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("sha")
            else:
                print(f"❌ Failed to fetch SHA: {resp.status_code} - {resp.text}")
                return None
        except Exception as e:
            print(f"❌ GithubService Error: {e}")
            return None

    def compare_commits(self, owner, repo, base_sha, head_sha):
        """
        Compares two commits and extracts diffs for relevant source files.
        """
        url = f"https://api.github.com/repos/{owner}/{repo}/compare/{base_sha}...{head_sha}"
        print(f"🔍 Comparing {base_sha[:7]}...{head_sha[:7]} for {owner}/{repo}...")
        
        try:
            resp = requests.get(url, headers=self.headers)
            if resp.status_code == 200:
                data = resp.json()
                files = []
                
                # Filter useful files
                ALLOWED_EXTENSIONS = {'.ts', '.tsx', '.js', '.jsx', '.py', '.go', '.java', '.rb', '.php'}
                
                for f in data.get("files", []):
                    filename = f.get("filename", "")
                    status = f.get("status") # added, modified, removed
                    
                    ext = os.path.splitext(filename)[1]
                    if ext in ALLOWED_EXTENSIONS or filename == "package.json":
                        patch = f.get("patch", "")
                        
                        # Truncate if too long
                        if len(patch) > 2000:
                            patch = patch[:2000] + "\n...(truncated)..."
                            
                        files.append({
                            "filename": filename,
                            "status": status,
                            "patch": patch
                        })
                        
                return {
                    "status": "success",
                    "total_commits": data.get("total_commits", 0),
                    "files": files
                }
            else:
                print(f"❌ Compare failed: {resp.status_code} - {resp.text}")
                return {"status": "error", "error": resp.text}
                
        except Exception as e:
            print(f"❌ GithubService Compare Error: {e}")
            return {"status": "error", "error": str(e)}

```

## File: `backend/app/services/storage_service.py`
```

import json
import logging
from google.cloud import storage
from app.core.config import settings

logger = logging.getLogger(__name__)

class StorageService:
    def __init__(self):
        # In GKE, auth is handled by Workload Identity or node service account
        # Locally, requires GOOGLE_APPLICATION_CREDENTIALS
        try:
            self.client = storage.Client()
            self.bucket_name = settings.GCS_BUCKET_NAME
            self.bucket = self.client.bucket(self.bucket_name)
        except Exception as e:
            logger.warning(f"⚠️ StorageService init failed (GCS might not be reachable locally): {e}")
            self.client = None
            self.bucket = None

    def save_graph(self, repo_id: str, data: dict):
        """Saves graph data to GCS as JSON."""
        if not self.bucket:
            logger.error("❌ GCS Bucket not configured.")
            return

        blob_name = f"graphs/{repo_id}.json"
        blob = self.bucket.blob(blob_name)
        
        try:
            blob.upload_from_string(
                data=json.dumps(data, indent=2),
                content_type='application/json'
            )
            logger.info(f"💾 [GCS] Saved graph: {blob_name}")
        except Exception as e:
            logger.error(f"❌ [GCS] Save failed: {e}")

    def get_graph(self, repo_id: str) -> dict:
        """Retrieves graph data from GCS."""
        if not self.bucket:
            return {}

        blob_name = f"graphs/{repo_id}.json"
        blob = self.bucket.blob(blob_name)
        
        try:
            if blob.exists():
                content = blob.download_as_text()
                return json.loads(content)
        except Exception as e:
            logger.error(f"❌ [GCS] Load failed: {e}")
        
        return {}

storage_service = StorageService()

```

## File: `backend/app/services/vector_service.py`
```

import os
import chromadb
from llama_index.core import VectorStoreIndex, StorageContext, Document, Settings
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.embeddings.google_genai import GoogleGenAIEmbedding
from app.core.config import settings

# Setup Embed Model Global
# We use Gemini for embeddings as per original design, even if Worker uses Ollama for analysis text generation.
# If Worker needs to be fully local, we should switch embedding to Ollama too, but request says "Call Ollama ... to analyze".
# It doesn't explicitly say "Embed with Ollama". I will keep Gemini Embedding for quality/consistency with API.
Settings.embed_model = GoogleGenAIEmbedding(model="models/embedding-001", api_key=settings.GOOGLE_API_KEY)

class VectorService:
    def __init__(self):
        # Connect to Chroma Server (Stateless)
        self.chroma_client = chromadb.HttpClient(
            host=settings.CHROMA_HOST, 
            port=settings.CHROMA_PORT
        )

    def get_index(self, repo_id):
        collection_name = f"kiwi_{repo_id.replace('-', '_')}"
        chroma_collection = self.chroma_client.get_or_create_collection(collection_name)
        vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        
        # Load index
        index = VectorStoreIndex.from_vector_store(
            vector_store,
            storage_context=storage_context,
        )
        return index

    def add_document(self, repo_id, file_path, content, metadata=None):
        if metadata is None:
            metadata = {}
        
        metadata["file_path"] = file_path
        metadata["repo_id"] = repo_id
        
        doc = Document(text=content, metadata=metadata)
        
        index = self.get_index(repo_id)
        index.insert(doc)
        print(f"📦 [Vector] Indexed: {file_path}")

    def add_raw_embedding(self, repo_id, file_path, content, embedding, metadata=None):
        """
        Inserts a document with a pre-computed embedding directly into Chroma.
        """
        collection_name = f"kiwi_{repo_id.replace('-', '_')}"
        collection = self.chroma_client.get_or_create_collection(collection_name)
        
        if metadata is None:
            metadata = {}
        metadata["file_path"] = file_path
        metadata["repo_id"] = repo_id
        
        collection.upsert(
            documents=[content],
            embeddings=[embedding],
            metadatas=[metadata],
            ids=[file_path] # Use file path as ID for dedupe
        )
        print(f"📦 [Vector] Raw Indexed: {file_path}")

vector_service = VectorService()

```

## File: `backend/app/worker/main.py`
```

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

```

## File: `backend/k8s/01-redis.yaml`
```

apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
spec:
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
      - name: redis
        image: redis:alpine
        ports:
        - containerPort: 6379
---
apiVersion: v1
kind: Service
metadata:
  name: redis
spec:
  selector:
    app: redis
  ports:
  - port: 6379
    targetPort: 6379

```

## File: `backend/k8s/02-chroma.yaml`
```

apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: chroma
spec:
  serviceName: "chroma"
  replicas: 1
  selector:
    matchLabels:
      app: chroma
  template:
    metadata:
      labels:
        app: chroma
    spec:
      containers:
      - name: chroma
        image: chromadb/chroma:latest
        ports:
        - containerPort: 8000
        volumeMounts:
        - name: chroma-storage
          mountPath: /chroma/chroma
  volumeClaimTemplates:
  - metadata:
      name: chroma-storage
    spec:
      accessModes: [ "ReadWriteOnce" ]
      storageClassName: "standard-rwo"
      resources:
        requests:
          storage: 10Gi
---
apiVersion: v1
kind: Service
metadata:
  name: chroma
spec:
  selector:
    app: chroma
  ports:
  - port: 8000
    targetPort: 8000

```

## File: `backend/k8s/03-ollama-gpu.yaml`
```
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ollama
spec:
  replicas: 1
  selector:
    matchLabels:
      app: ollama
  template:
    metadata:
      labels:
        app: ollama
    spec:
      containers:
      - name: ollama
        image: ollama/ollama:latest
        resources:
          requests:
            memory: "4Gi"
            cpu: "2"
        ports:
        - containerPort: 11434
        # CPU Start Script
        command: ["/bin/sh", "-c"]
        args:
          - |
            ollama serve & 
            PID=$!
            sleep 10
            echo "Pulling models..."
            ollama pull llama3.2:3b
            ollama pull nomic-embed-text
            wait $PID
        volumeMounts:
        - name: ollama-data
          mountPath: /root/.ollama
      volumes:
      - name: ollama-data
        emptyDir: {} 
---
apiVersion: v1
kind: Service
metadata:
  name: ollama
spec:
  selector:
    app: ollama
  ports:
  - port: 11434
    targetPort: 11434
```

## File: `backend/k8s/04-app.yaml`
```

apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
spec:
  replicas: 2
  selector:
    matchLabels:
      app: api
  template:
    metadata:
      labels:
        app: api
    spec:
      containers:
      - name: api
        image: gcr.io/PROJECT_ID/kiwi-api:latest
        ports:
        - containerPort: 8000
        env:
        - name: REDIS_HOST
          value: "redis"
        - name: CHROMA_HOST
          value: "chroma"
        - name: OLLAMA_URL
          value: "http://ollama:11434"
        - name: GOOGLE_API_KEY
          valueFrom:
            secretKeyRef:
              name: kiwi-secrets
              key: google-api-key
        - name: GCS_BUCKET_NAME
          value: "kiwi-graphs-prod"
---
apiVersion: v1
kind: Service
metadata:
  name: api
spec:
  selector:
    app: api
  type: LoadBalancer
  ports:
  - port: 80
    targetPort: 8000
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: worker
spec:
  replicas: 5 # The Swarm!
  selector:
    matchLabels:
      app: worker
  template:
    metadata:
      labels:
        app: worker
    spec:
      containers:
      - name: worker
        image: gcr.io/PROJECT_ID/kiwi-worker:latest
        env:
        - name: REDIS_HOST
          value: "redis"
        - name: CHROMA_HOST
          value: "chroma"
        - name: OLLAMA_URL
          value: "http://ollama:11434"
        - name: GOOGLE_API_KEY
          valueFrom:
            secretKeyRef:
              name: kiwi-secrets
              key: google-api-key
        - name: GCS_BUCKET_NAME
          value: "kiwi-graphs-prod"

```

