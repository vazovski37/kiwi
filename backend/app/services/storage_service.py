
import json
import logging
from google.cloud import storage
from app.core.config import settings

logger = logging.getLogger(__name__)

class StorageService:
    def __init__(self):
        # In GKE, auth is handled by Workload Identity or node service account
        # Locally, requires GOOGLE_APPLICATION_CREDENTIALS
        try:
            self.client = storage.Client()
            self.bucket_name = settings.GCS_BUCKET_NAME
            self.bucket = self.client.bucket(self.bucket_name)
        except Exception as e:
            logger.warning(f"⚠️ StorageService init failed (GCS might not be reachable locally): {e}")
            self.client = None
            self.bucket = None

    def save_graph(self, repo_id: str, data: dict):
        """Saves graph data to GCS as JSON."""
        if not self.bucket:
            logger.error("❌ GCS Bucket not configured.")
            return

        blob_name = f"graphs/{repo_id}.json"
        blob = self.bucket.blob(blob_name)
        
        try:
            blob.upload_from_string(
                data=json.dumps(data, indent=2),
                content_type='application/json'
            )
            logger.info(f"💾 [GCS] Saved graph: {blob_name}")
        except Exception as e:
            logger.error(f"❌ [GCS] Save failed: {e}")

    def get_graph(self, repo_id: str) -> dict:
        """Retrieves graph data from GCS."""
        if not self.bucket:
            return {}

        blob_name = f"graphs/{repo_id}.json"
        blob = self.bucket.blob(blob_name)
        
        try:
            if blob.exists():
                content = blob.download_as_text()
                return json.loads(content)
        except Exception as e:
            logger.error(f"❌ [GCS] Load failed: {e}")
        
        return {}

storage_service = StorageService()
