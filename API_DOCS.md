# API Documentation

Base URL: `http://localhost:8000`

## 1. Health Check
Checks if the API server is online.

- **Endpoint**: `GET /`
- **Response**:
  ```json
  {
    "status": "online",
    "system": "Multi-Tenant CodeAtlas"
  }
  ```

## 2. Ingest Repository
Triggers the indexing process for a GitHub repository. This will fetch files, vectorise them, and generate an architecture document.

- **Endpoint**: `POST /api/ingest`
- **Request Body** (`application/json`):
  ```json
  {
    "url": "https://github.com/owner/repository",
    "branch": "main"  // Optional, defaults to "main"
  }
  ```
- **Response** (`200 OK`):
  ```json
  {
    "status": "success",
    "repo_id": "owner-repository-branch"
  }
  ```
- **Repo ID Format**: The `repo_id` is constructed as `{owner}-{repo}-{branch}`. You will need this ID for subsequent chat and architecture requests.

## 3. Chat with Repo
Ask questions about a specific repository's codebase.

- **Endpoint**: `POST /api/chat`
- **Request Body** (`application/json`):
  ```json
  {
    "repo_id": "owner-repository-branch",
    "message": "How does the authentication module work?"
  }
  ```
- **Response** (`200 OK`):
  ```json
  {
    "response": "The authentication module uses JWT tokens..."
  }
  ```
- **Errors**:
  - `404 Not Found`: If the `repo_id` has not been ingested yet.
  - `500 Server Error`: If retrieval fails (fallback logic is in place to minimize this).

## 4. Get Architecture Document
Retrieve the generated `ARCHITECTURE.md` file for a repository.

- **Endpoint**: `GET /api/architecture/{repo_id}`
- **Path Parameters**:
  - `repo_id`: The ID returned from the ingest step (e.g., `vazovski37-sheukvete-frontend-main`).
- **Response** (`200 OK`):
  ```json
  {
    "meta": { "project_name": "Kiwi" },
    "stack": [...],
    "modules": [...],
    "flow": [...],
    "mermaid": "graph TD..."
  }
  ```
- **Errors**:
  - `404 Not Found`: If the architecture file does not exist (ingestion might still be running or failed).

## 5. Repository Library
List all available repositories.

- **Endpoint**: `GET /api/repos`
- **Response** (`200 OK`):
  ```json
  [
    {
      "id": "vazovski37-gynt-main",
      "meta": { "project_name": "Gynt", "stats": {...} }
    }
  ]
  ```
