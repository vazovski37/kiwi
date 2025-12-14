
from fastapi import APIRouter, HTTPException
from app.schemas.requests import ChatRequest
from app.services.vector_service import vector_service
from app.services.embedding_service import embedding_service
from app.core.config import settings
from llama_index.llms.google_genai import GoogleGenAI
from llama_index.core.llms import ChatMessage

router = APIRouter()

@router.post("/chat")
async def chat(request: ChatRequest):
    repo_id = request.repo_id
    
    # 1. Get Embedding for Question (Ollama)
    query_embedding = await embedding_service.get_embedding(request.message)
    if not query_embedding:
        raise HTTPException(status_code=500, detail="Failed to generate query embedding.")
    
    # 2. Query ChromaDB directly (Hybrid RAG approach)
    try:
        # Access raw client to query with embedding
        collection_name = f"kiwi_{repo_id.replace('-', '_')}"
        collection = vector_service.chroma_client.get_collection(collection_name)
        
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=5
        )
        
        # Parse results
        docs = results['documents'][0]
        metadatas = results['metadatas'][0]
        
        context_str = ""
        for i, doc in enumerate(docs):
            path = metadatas[i].get('file_path', 'unknown')
            context_str += f"\n--- File: {path} ---\n{doc}\n"
            
    except Exception as e:
        print(f"❌ Retrieval Error: {e}")
        # Proceed with empty context if fail?
        context_str = "No context retrieved due to error."

    # 3. Generate Answer (Gemini 1.5 Pro)
    # Using LlamaIndex LLM wrapper convenient for completion
    try:
        llm = GoogleGenAI(model=settings.LLM_MODEL, api_key=settings.GOOGLE_API_KEY)
        
        system_prompt = (
            "You are a Senior Software Architect.\n"
            "Answer the user's question based on the provided Code Context.\n"
            "If the context doesn't contain the answer, say so.\n"
        )
        
        prompt = f"Context:\n{context_str}\n\nQuestion: {request.message}"
        
        messages = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=prompt)
        ]
        
        response = llm.chat(messages)
        return {"response": response.message.content}
        
    except Exception as e:
        print(f"❌ Generation Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
