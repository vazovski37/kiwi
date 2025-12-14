
import os
import json
from datetime import datetime

class RepoDB:
    def __init__(self, db_path="db/repos.json"):
        self.db_path = db_path
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
