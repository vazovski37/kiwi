try:
    import chromadb
    import llama_index.core
    import nest_asyncio
    from llama_index.readers.github import GithubRepositoryReader
    from llama_index.llms.google_genai import GoogleGenAI
    from llama_index.embeddings.google_genai import GoogleGenAIEmbedding
    from llama_index.vector_stores.chroma import ChromaVectorStore
    from dotenv import load_dotenv
    nest_asyncio.apply()
    print("Imports successful!")
except ImportError as e:
    print(f"Import failed: {e}")
except Exception as e:
    print(f"An error occurred: {e}")
