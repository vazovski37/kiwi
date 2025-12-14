import requests
import json
import time

API_URL = "http://localhost:8000/chat"

def test_question(question, description):
    print(f"\n🧪 TESTING: {description}")
    print(f"❓ Asking: '{question}'")
    
    start = time.time()
    try:
        response = requests.post(API_URL, json={"message": question})
        response.raise_for_status()
        
        answer = response.json()["response"]
        duration = time.time() - start
        
        print(f"🤖 AI Answer ({duration:.2f}s):")
        print("-" * 40)
        print(answer)
        print("-" * 40)
        
        # simple check to see if it's generic or specific
        if "function" in answer or "hook" in answer or "import" in answer:
            print("✅ VERDICT: REAL INTELLIGENCE DETECTED (It found specific code details)")
        else:
            print("⚠️ VERDICT: RESPONSE SEEMS GENERIC (Check code indexing)")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    # Question 1: Specific Code Implementation (Brain Test)
    # The Architecture.md won't know the exact lines of code or hooks used inside the file.
    test_question(
        "How is the 'useLogin' hook implemented? What arguments does the login function take?",
        "Deep Code Retrieval Test"
    )

    # Question 2: Specific UI Component (Brain Test)
    test_question(
        "Look at 'OrderCard.tsx'. How does it handle the 'toggle' action? specific function names.",
        "Component Logic Test"
    )