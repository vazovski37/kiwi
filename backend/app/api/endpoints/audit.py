
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
