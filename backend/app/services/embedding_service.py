
import aiohttp
import asyncio
from typing import List
from app.core.config import settings

class EmbeddingService:
    def __init__(self):
        self.base_url = settings.OLLAMA_URL
        self.model = "nomic-embed-text"

    async def get_embedding(self, text: str) -> List[float]:
        """
        Generates embedding for a single string using Ollama.
        """
        async with aiohttp.ClientSession() as session:
            payload = {
                "model": self.model,
                "prompt": text
            }
            
            try:
                async with session.post(f"{self.base_url}/api/embeddings", json=payload) as resp:
                    if resp.status != 200:
                        print(f"❌ Embedding Error: {resp.status} - {await resp.text()}")
                        return []
                    
                    data = await resp.json()
                    return data.get("embedding", [])
            except Exception as e:
                print(f"❌ Embedding Connection Error: {e}")
                return []

# Singleton
embedding_service = EmbeddingService()
