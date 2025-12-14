
import os
import chromadb
from llama_index.core import VectorStoreIndex, StorageContext, Document, Settings
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.embeddings.google_genai import GoogleGenAIEmbedding
from app.core.config import settings

# Setup Embed Model Global
# We use Gemini for embeddings as per original design, even if Worker uses Ollama for analysis text generation.
# If Worker needs to be fully local, we should switch embedding to Ollama too, but request says "Call Ollama ... to analyze".
# It doesn't explicitly say "Embed with Ollama". I will keep Gemini Embedding for quality/consistency with API.
Settings.embed_model = GoogleGenAIEmbedding(model="models/embedding-001", api_key=settings.GOOGLE_API_KEY)

class VectorService:
    def __init__(self):
        # Connect to Chroma Server (Stateless)
        self.chroma_client = chromadb.HttpClient(
            host=settings.CHROMA_HOST, 
            port=settings.CHROMA_PORT
        )

    def get_index(self, repo_id):
        collection_name = f"kiwi_{repo_id.replace('-', '_')}"
        chroma_collection = self.chroma_client.get_or_create_collection(collection_name)
        vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        
        # Load index
        index = VectorStoreIndex.from_vector_store(
            vector_store,
            storage_context=storage_context,
        )
        return index

    def add_document(self, repo_id, file_path, content, metadata=None):
        if metadata is None:
            metadata = {}
        
        metadata["file_path"] = file_path
        metadata["repo_id"] = repo_id
        
        doc = Document(text=content, metadata=metadata)
        
        index = self.get_index(repo_id)
        index.insert(doc)
        print(f"📦 [Vector] Indexed: {file_path}")

    def add_raw_embedding(self, repo_id, file_path, content, embedding, metadata=None):
        """
        Inserts a document with a pre-computed embedding directly into Chroma.
        """
        collection_name = f"kiwi_{repo_id.replace('-', '_')}"
        collection = self.chroma_client.get_or_create_collection(collection_name)
        
        if metadata is None:
            metadata = {}
        metadata["file_path"] = file_path
        metadata["repo_id"] = repo_id
        
        collection.upsert(
            documents=[content],
            embeddings=[embedding],
            metadatas=[metadata],
            ids=[file_path] # Use file path as ID for dedupe
        )
        print(f"📦 [Vector] Raw Indexed: {file_path}")

vector_service = VectorService()
