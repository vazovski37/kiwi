# AI Swarm

Local AI Processing Swarm.
Uses **Kubernetes** workers to process code analysis requests in parallel via **Ollama** (running on host) and returns structured JSON results.

## Architecture
- **Clients**: Use `SwarmClient` to send Python code for analysis.
- **Queue**: Redis (running in K8s).
- **Workers**: Python scripts (in K8s pods) that consume jobs and call Ollama.
- **Ollama**: Running on Windows Host (RTX 5070 Local).

## Prerequisites
1.  **Ollama**: `ollama serve` running on Windows.
1.  **Ollama**: `ollama serve` running on Windows.
    - **Important**: Must accept external origins. Run commands:
      ```powershell
      set OLLAMA_HOST=0.0.0.0
      set OLLAMA_ORIGINS="*"
      ollama serve
      ```
    - Model: `ollama pull qwen2.5-coder:3b`
2.  **Kubernetes**: Docker Desktop enabled.
3.  **Python 3.11+**: For the client.

## Quick Start

### 1. Setup Swarm (One-time)
```powershell
cd aiswarm
# Build Worker Image
docker build -t aiswarm-worker:latest .

# Deploy to K8s
kubectl apply -f k8s/
```
Wait for pods to be ready:
```powershell
kubectl get pods -n aiswarm -w
```

### 2. Run Client / Test
To run a client script from your host machine (Windows), you need to reach the Redis inside K8s.
**Option A: Port Forward (Simplest for Dev)**
Open a new terminal and run:
```powershell
kubectl port-forward svc/redis-service 6379:6379 -n aiswarm
```
Then run the test script:
```powershell
pip install redis
python test_rpc.py
```

**Option B: In-Cluster**
Deploy your application into the same K8s cluster and communicate with `redis-service:6379`.

## Code Example
```python
from client import SwarmClient

client = SwarmClient(redis_host="localhost", redis_port=6379)
result = client.analyze_code(
    file_name="example.py", 
    code="import os..."
)
print(result)
# Output: {'summary': '...', 'dependencies': ['os'], 'exports': []}
```
