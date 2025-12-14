
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
