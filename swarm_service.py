import os
import json
import uuid
import time
import asyncio
import redis.asyncio as redis
from dotenv import load_dotenv

load_dotenv()

class SwarmService:
    """
    Swarm Client Service.
    Instead of processing locally, this service dispatches analysis jobs
    to the Redis Queue ('swarm_jobs'), where K8s workers pick them up.
    """
    
    def __init__(self):
        # Redis Configuration
        self.redis_host = os.getenv("REDIS_HOST", "localhost")
        # Use 6380 if localhost (port-forwarded), else 6379 (internal)
        # For this integration, we assume running from host, so 6380 default
        # Ideally, this should be configurable via env
        self.redis_port = int(os.getenv("REDIS_PORT", 6380)) 
        self.queue_name = "swarm_jobs"
        
    async def get_redis(self):
        """Returns an async Redis connection."""
        return await redis.Redis(
            host=self.redis_host, 
            port=self.redis_port, 
            decode_responses=True
        )

    async def run_swarm_analysis(self, documents: list) -> dict:
        """
        Runs concurrent analysis on all documents via the Swarm.
        Returns a dependency graph dict.
        """
        print(f"🐝[Client] Starting Swarm Analysis for {len(documents)} files...")
        
        r = await self.get_redis()
        try:
            await r.ping()
        except Exception as e:
            print(f"❌[Client] Redis connection failed: {e}")
            print("   Ensure 'kubectl port-forward' is running if on host.")
            return {}

        job_map = {} # job_id -> file_name
        
        # 1. Dispatch Jobs
        print("🚀[Client] Dispatching jobs to Swarm...")
        pipe = r.pipeline()
        for doc in documents:
            file_name = doc.metadata.get("file_path", "unknown")
            code = doc.text
            job_id = str(uuid.uuid4())
            
            payload = {
                "id": job_id,
                "file_name": file_name,
                "code": code
            }
            
            pipe.rpush(self.queue_name, json.dumps(payload))
            job_map[job_id] = file_name
            
        await pipe.execute()
        print(f"✅[Client] Dispatched {len(job_map)} jobs.")

        # 2. Await Results (Scatter-Gather)
        # We poll for results or use blpop on specific reply keys?
        # Workers push to `reply:{job_id}`. 
        # Since we have many jobs, we can poll all reply keys or use a dedicated response queue.
        # For simplicity with current worker logic (worker pushes to unique key), we poll concurrent keys.
        
        results = {}
        pending_jobs = set(job_map.keys())
        
        start_time = time.time()
        timeout = 120 # 2 minutes total timeout
        
        print("⏳[Client] Waiting for results...")
        
        while pending_jobs and (time.time() - start_time) < timeout:
            # Check all pending keys (efficient enough for <100 files)
            # Optimization: could make workers push to a single 'swarm_results' queue with correlation ID.
            # But adhering to current worker logic:
            
            for job_id in list(pending_jobs):
                reply_key = f"reply:{job_id}"
                data_str = await r.lpop(reply_key)
                
                if data_str:
                    try:
                        data = json.loads(data_str)
                        file_name = job_map[job_id]
                        results[file_name] = data
                        pending_jobs.remove(job_id)
                        print(f"  ✨ Recieved: {file_name}")
                    except:
                        print(f"  ⚠️ Error parsing reply for {job_id}")
            
            await asyncio.sleep(0.5)
            
        await r.aclose()
        
        if pending_jobs:
            print(f"⚠️[Client] Timed out waiting for {len(pending_jobs)} files.")
        
        print(f"✅[Client] Swarm analysis complete. Received {len(results)}/{len(documents)}.")
        return results

# Singleton instance
swarm_service = SwarmService()
