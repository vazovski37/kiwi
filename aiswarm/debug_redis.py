import redis

def check_redis():
    print("[*] Checking Redis State...")
    try:
        r = redis.Redis(host="localhost", port=6379, decode_responses=True)
        r.ping()
        print("[+] Connected to Redis")
        
        keys = r.keys("*")
        print(f"[i] Keys found: {keys}")
        
        if "swarm_jobs" in keys:
            length = r.llen("swarm_jobs")
            print(f"[i] 'swarm_jobs' length: {length}")
            if length > 0:
                print("   [!] Jobs are STUCK in queue - Workers not picking them up.")
            else:
                print("   [i] Queue is empty.")
        else:
            print("[i] 'swarm_jobs' key does not exist.")
            
    except Exception as e:
        print(f"[!] Redis Error: {e}")

if __name__ == "__main__":
    check_redis()
