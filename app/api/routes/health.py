from fastapi import APIRouter

from app.config import get_settings
from app.models import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health():
    s = get_settings()
    repo = s.pageindex_path
    repo_ok = (repo / "run_pageindex.py").is_file()
    litellm_ok = False
    try:
        import litellm  # noqa: F401

        litellm_ok = True
    except ImportError:
        pass
    gcs_ok = False
    try:
        from app.services.gcs_store import get_storage_client

        client = get_storage_client()
        bucket = client.bucket(s.gcs_bucket)
        gcs_ok = bucket.exists()
    except Exception:
        gcs_ok = False
    ready = repo_ok and litellm_ok
    return HealthResponse(
        status="ok" if ready and gcs_ok else "degraded",
        pageindex_ready=ready,
        gcs_ready=gcs_ok,
        gcs_bucket=s.gcs_bucket or None,
    )
