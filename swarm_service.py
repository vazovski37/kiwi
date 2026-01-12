
import os
import json
import asyncio
import aiohttp
from dotenv import load_dotenv

load_dotenv()


class SwarmService:
    """
    Swarm analysis service using local Ollama LLM for file analysis.
    Uses qwen2.5-coder:3b by default for fast, code-aware analysis.
    """
    
    def __init__(self):
        self.ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
        self.model = os.getenv("SWARM_MODEL", "qwen2.5-coder:3b")
        self.timeout = aiohttp.ClientTimeout(total=60)
        
    async def _call_ollama(self, prompt: str) -> str:
        """
        Calls Ollama API directly for completion.
        """
        url = f"{self.ollama_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,  # Low temp for consistent JSON output
                "num_predict": 512   # Limit response length
            }
        }
        
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(url, json=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("response", "")
                    else:
                        error_text = await resp.text()
                        print(f"❌ Ollama error {resp.status}: {error_text}")
                        return ""
        except asyncio.TimeoutError:
            print(f"⚠️ Ollama timeout for request")
            return ""
        except aiohttp.ClientError as e:
            print(f"❌ Ollama connection error: {e}")
            return ""
    
    async def analyze_file(self, sem: asyncio.Semaphore, file_name: str, code: str) -> tuple:
        """
        Analyzes a single file using the local LLM.
        Returns (file_name, analysis_dict).
        """
        async with sem:
            # Truncate code if too long (3b model has limited context)
            code_snippet = code[:4000] if len(code) > 4000 else code
            
            prompt = (
                f"Analyze this code file: '{file_name}'\n\n"
                f"```\n{code_snippet}\n```\n\n"
                "Return a JSON object with EXACTLY these keys:\n"
                '{"summary": "1 sentence description", '
                '"dependencies": ["list", "of", "imports"], '
                '"exports": ["list", "of", "exported", "items"]}\n'
                "Respond with JSON ONLY, no markdown."
            )
            
            try:
                response = await self._call_ollama(prompt)
                
                if not response:
                    return file_name, {"summary": "Analysis failed - no response", "dependencies": [], "exports": []}
                
                # Clean response (remove markdown if present)
                text = response.strip()
                if text.startswith("```json"):
                    text = text[7:]
                if text.startswith("```"):
                    text = text[3:]
                if text.endswith("```"):
                    text = text[:-3]
                text = text.strip()
                
                # Find JSON object in response
                start = text.find("{")
                end = text.rfind("}") + 1
                if start != -1 and end > start:
                    text = text[start:end]
                
                data = json.loads(text)
                print(f"  ✅ Analyzed: {file_name}")
                return file_name, data
                
            except json.JSONDecodeError as e:
                print(f"  ⚠️ JSON parse failed for {file_name}: {e}")
                return file_name, {"summary": "JSON parse failed", "dependencies": [], "exports": [], "raw": response[:200] if response else ""}
            except Exception as e:
                print(f"  ❌ Analysis failed for {file_name}: {e}")
                return file_name, {"summary": f"Error: {str(e)}", "dependencies": [], "exports": []}
    
    async def run_swarm_analysis(self, documents: list) -> dict:
        """
        Runs concurrent analysis on all documents.
        Returns a dependency graph dict.
        """
        print(f"🐝 Starting Swarm Analysis with {self.model}...")
        print(f"   Ollama URL: {self.ollama_url}")
        print(f"   Files to analyze: {len(documents)}")
        
        # Check if Ollama is available
        if not await self._check_ollama():
            print("❌ Ollama is not available. Skipping swarm analysis.")
            return {}
        
        # Concurrency limit (5 parallel requests)
        sem = asyncio.Semaphore(5)
        
        tasks = []
        for doc in documents:
            file_name = doc.metadata.get("file_path", "unknown")
            code = doc.text
            tasks.append(self.analyze_file(sem, file_name, code))
        
        results = await asyncio.gather(*tasks)
        
        graph = {}
        for fname, data in results:
            graph[fname] = data
        
        print(f"✅ Swarm analysis complete. Analyzed {len(graph)} files.")
        return graph
    
    async def _check_ollama(self) -> bool:
        """
        Checks if Ollama server is running and model is available.
        """
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                async with session.get(f"{self.ollama_url}/api/tags") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        models = [m.get("name", "") for m in data.get("models", [])]
                        
                        # Check if our model is available
                        model_base = self.model.split(":")[0]
                        available = any(model_base in m for m in models)
                        
                        if available:
                            print(f"✅ Ollama ready with {self.model}")
                            return True
                        else:
                            print(f"⚠️ Model {self.model} not found. Available: {models}")
                            print(f"   Run: ollama pull {self.model}")
                            return False
                    return False
        except Exception as e:
            print(f"❌ Cannot connect to Ollama at {self.ollama_url}: {e}")
            return False


# Singleton instance
swarm_service = SwarmService()
