
from database import db
import os

def test_db():
    print("Testing RepoDB...")
    # Clean
    if os.path.exists("db/test.json"):
        os.remove("db/test.json")
    
    # Use a custom path or just test the singleton
    db.db_path = "db/test_repos.json"
    db._ensure_db()
    
    # 1. Upsert
    data = {"repo_id": "test-1", "url": "http://foo", "branch": "main", "meta": {"a": 1}}
    db.upsert(data)
    
    # 2. Get
    item = db.get("test-1")
    assert item["repo_id"] == "test-1"
    assert item["meta"]["a"] == 1
    print("✅ Upsert & Get passed")
    
    # 3. Get All
    all_items = db.get_all()
    assert len(all_items) == 1
    print("✅ Get All passed")
    
    # 4. Update
    data["meta"]["b"] = 2
    db.upsert(data)
    item = db.get("test-1")
    assert item["meta"]["b"] == 2
    assert item["meta"]["a"] == 1
    print("✅ Update passed")
    
    # Cleanup
    if os.path.exists("db/test_repos.json"):
        os.remove("db/test_repos.json")

if __name__ == "__main__":
    test_db()
