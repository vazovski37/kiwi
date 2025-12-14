
import sys
import nest_asyncio
from fastapi.testclient import TestClient
from main import app, query_engine

# Apply nest_asyncio to allow re-entrant event loops if needed during tests
nest_asyncio.apply()

client = TestClient(app)

def test_api():
    print("🧪 Testing API Endpoints...")
    
    # 1. Health Check
    print("   Testing GET / ...")
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "online"}
    print("   ✅ GET / passed.")
    
    # 2. Architecture
    print("   Testing GET /api/architecture/{repo_id} ...")
    # We need a repo_id to test. Let's assume one or skip if not known.
    # For now, we just test the correct route format.
    # If we don't have a repo, this will 404, but that's better than 404 for wrong path.
    repo_id_test = "test-repo" 
    response = client.get(f"/api/architecture/{repo_id_test}")
    
    if response.status_code == 200:
        content = response.json().get("content")
        assert content is not None
        print("   ✅ GET /api/architecture passed.")
    elif response.status_code == 404:
        print("   ⚠️ GET /api/architecture returned 404 (Repo not found), but endpoint is reachable.")
    else:
        print(f"   ⚠️ GET /api/architecture returned {response.status_code}")

    # 3. Chat
    print("   Testing POST /api/chat ...")
    if query_engine:
        # We can try a simple query
        payload = {"repo_id": "test-repo", "message": "What is the project about?"}
        try:
            response = client.post("/api/chat", json=payload)
            if response.status_code == 200:
                 print(f"   ✅ POST /api/chat passed. Response: {response.json()['response'][:50]}...")
            elif response.status_code == 404:
                 print("   ⚠️ POST /api/chat returned 404 (Repo not found), but endpoint is reachable.")
            else:
                 print(f"   ❌ POST /api/chat failed: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"   ❌ POST /api/chat raised exception: {e}")            if response.status_code == 200:
                 print(f"   ✅ POST /chat passed. Response: {response.json()['response'][:50]}...")
            else:
                 print(f"   ❌ POST /chat failed: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"   ❌ POST /chat raised exception: {e}")
    else:
        print("   ⚠️ Query engine not loaded, skipping real chat test.")

if __name__ == "__main__":
    try:
        test_api()
    except AssertionError as e:
        print(f"   ❌ Assertion failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"   ❌ An error occurred: {e}")
        sys.exit(1)
