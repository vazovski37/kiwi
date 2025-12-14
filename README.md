# Kiwi - GitHub Hierarchical Knowledge Graph Ingestion

This tool ingests a GitHub repository into a generic Hierarchical Knowledge Graph using LlamaIndex, without cloning the repository locally.

## Setup

1.  **Initialize Environment**:
    ```bash
    python -m venv venv
    .\venv\Scripts\Activate.ps1
    pip install -r requirements.txt
    ```
    *(Note: dependencies are already installed if you ran the setup command)*

2.  **Environment Variables**:
    Copy `.env.example` to `.env` and fill in your keys:
    ```bash
    cp .env.example .env
    ```
    - `GITHUB_TOKEN`: Your GitHub Personal Access Token.
    - `GOOGLE_API_KEY`: API key for Gemini.

## Usage

Run the indexer script:

```bash
python indexer.py
```

## Features

- **Direct Streaming**: Uses `GithubRepositoryReader` to fetch files via the GitHub API.
- **Hierarchical Indexing**: chunks content into parent-child relationships (1024 -> 512 -> 128 tok).
- **Auto-Merging Retrieval**: `query_system` retrieves leaf nodes and merges them into parent nodes for richer context.
- **Persistent Storage**: Vectors stored in local `chroma_db`.
