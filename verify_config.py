
import sys
from unittest.mock import MagicMock

# Mock external dependencies to avoid API calls during config verification
sys.modules["llama_index.llms.gemini"] = MagicMock()
sys.modules["llama_index.embeddings.gemini"] = MagicMock()

# We need to ensure we can import indexer and that it uses our mocks
# But indexer imports FROM these modules.
# So we need to set up the mocks such that:
# from llama_index.llms.gemini import Gemini -> Gemini is a Mock class

mock_gemini_module = MagicMock()
mock_gemini_class = MagicMock()
mock_gemini_module.Gemini = mock_gemini_class
sys.modules["llama_index.llms.gemini"] = mock_gemini_module

mock_embed_module = MagicMock()
mock_embed_class = MagicMock()
mock_embed_module.GeminiEmbedding = mock_embed_class
sys.modules["llama_index.embeddings.gemini"] = mock_embed_module

# Now import indexer
import os
# Ensure no env vars interfere
if "LLM_MODEL" in os.environ: del os.environ["LLM_MODEL"]
if "EMBEDDING_MODEL" in os.environ: del os.environ["EMBEDDING_MODEL"]

try:
    import indexer
    print("Imported indexer successfully with mocks.")
    
    # Verify Gemini was initialized with default
    # indexer.py: Settings.llm = Gemini(model=os.getenv("LLM_MODEL", "models/gemini-1.5-pro"))
    mock_gemini_class.assert_called_with(model="models/gemini-1.5-pro")
    print("Verified default LLM model name.")
    
    # Verify Embedding was initialized with default
    # indexer.py: Settings.embed_model = GeminiEmbedding(model=os.getenv("EMBEDDING_MODEL", "models/embedding-001"))
    mock_embed_class.assert_called_with(model="models/gemini-1.5-pro") # Wait, checking the previous code...
    # Ah, I need to check what I wrote in indexer.py for embedding model default
    
except AssertionError as e:
    print(f"Assertion failed: {e}")
    # Print what it was actually called with
    print(f"Gemini call args: {mock_gemini_class.call_args}")
    print(f"Embedding call args: {mock_embed_class.call_args}")
except Exception as e:
    print(f"An error occurred: {e}")
