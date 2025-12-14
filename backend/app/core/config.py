
import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "Kiwi Backend"
    
    # Paths
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    DB_PATH: str = os.path.join(BASE_DIR, "db", "repos.json")
    
    # Redis
    REDIS_HOST: str = "localhost" # 'redis' in docker
    REDIS_PORT: int = 6379
    
    # AI - Gemini
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "models/gemini-1.5-pro-latest")
    
    # AI - Ollama
    OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
    
    # GitHub
    GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")

    # Storage (GCS)
    GCS_BUCKET_NAME: str = os.getenv("GCS_BUCKET_NAME", "kiwi-graphs")
    
    # Vector DB (Chroma Server)
    CHROMA_HOST: str = os.getenv("CHROMA_HOST", "chroma")
    CHROMA_PORT: int = 8000

    class Config:
        env_file = ".env"

settings = Settings()
