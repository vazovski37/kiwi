
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.endpoints import ingest, chat, audit

app = FastAPI(title=settings.APP_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def health_check():
    return {"status": "online", "service": "Kiwi API"}

app.include_router(ingest.router, prefix="/api", tags=["Ingest"])
app.include_router(chat.router, prefix="/api", tags=["Chat"])
app.include_router(audit.router, prefix="/api/updates", tags=["Audit"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
