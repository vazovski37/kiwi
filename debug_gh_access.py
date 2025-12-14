
import os
import requests
from dotenv import load_dotenv

load_dotenv()

def check_repo_access(owner, repo, branch="main"):
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print("❌ GITHUB_TOKEN not found in .env")
        return

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json"
    }

    print(f"🕵️ Checking access for {owner}/{repo} on branch '{branch}'...")
    
    # 1. Check Repo Existence / Permissions
    repo_url = f"https://api.github.com/repos/{owner}/{repo}"
    resp = requests.get(repo_url, headers=headers)
    
    if resp.status_code == 200:
        print(f"✅ Repo access confirmed: {owner}/{repo}")
        data = resp.json()
        print(f"   - Private: {data.get('private')}")
        print(f"   - Default Branch: {data.get('default_branch')}")
    else:
        print(f"❌ Repo check failed: {resp.status_code}")
        print(f"   Response: {resp.json()}")
        return

    # 2. Check Branch
    branch_url = f"https://api.github.com/repos/{owner}/{repo}/branches/{branch}"
    resp = requests.get(branch_url, headers=headers)
    
    if resp.status_code == 200:
        print(f"✅ Branch '{branch}' exists.")
    else:
        print(f"❌ Branch '{branch}' not found: {resp.status_code}")
        print(f"   Response: {resp.json()}")

if __name__ == "__main__":
    # Test with the failing repo
    check_repo_access("vazovski37", "gynt", "main")
