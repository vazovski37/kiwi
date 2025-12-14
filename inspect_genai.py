
try:
    import llama_index.llms.google_genai as llm_genai
    import llama_index.embeddings.google_genai as embed_genai
    print("LLM Exports:", dir(llm_genai))
    print("Embed Exports:", dir(embed_genai))
except ImportError as e:
    print(e)
