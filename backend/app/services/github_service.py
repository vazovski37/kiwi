
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
