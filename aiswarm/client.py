import os
import json
import uuid
import time
import redis

class SwarmClient:
    def __init__(self, redis_host="localhost", redis_port=6379):
        self.redis = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
        self.queue_name = "swarm_jobs"

    def analyze_code(self, file_name: str, code: str, timeout: int = 60) -> dict:
        """
        Sends code to the swarm and waits for the analysis result.
        Returns a dict with 'summary', 'dependencies', 'exports'.
        """
        job_id = str(uuid.uuid4())
        job_payload = {
            "id": job_id,
            "file_name": file_name,
            "code": code
        }
        
        # Push Job
        try:
            self.redis.rpush(self.queue_name, json.dumps(job_payload))
        except Exception as e:
            return {"summary": f"Redis Error: {str(e)}", "dependencies": [], "exports": []}

        # Wait for Reply
        reply_key = f"reply:{job_id}"
        start_time = time.time()
        
        while (time.time() - start_time) < timeout:
            result = self.redis.blpop(reply_key, timeout=1)
            if result:
                _, response_data = result
                try:
                    return json.loads(response_data)
                except:
                    return {"summary": "Invalid JSON response", "dependencies": [], "exports": []}
        
        return {"summary": "Timeout waiting for swarm", "dependencies": [], "exports": []}

# Example Usage
if __name__ == "__main__":
    client = SwarmClient()
    print("Sending test job...")
    result = client.analyze_code("test.py", "import os\nprint('Hello World')")
    print("Result:", json.dumps(result, indent=2))
