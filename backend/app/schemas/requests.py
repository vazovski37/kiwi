
from pydantic import BaseModel
from typing import Optional

class IngestRequest(BaseModel):
    url: str
    branch: str = "main"

class ChatRequest(BaseModel):
    repo_id: str
    message: str

class AuditRequest(BaseModel):
    # If explicit request is needed, otherwise generic trigger
    pass
