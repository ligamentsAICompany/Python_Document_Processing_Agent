"""GET /v1/health and /v1/capabilities."""

from __future__ import annotations

from fastapi import APIRouter

from app.config import get_settings
from app.core.llm import smoke_test_chat_model
from app.services.convert import SUPPORTED

router = APIRouter(tags=["v1-meta"])


@router.get("/health")
def v1_health():
    s = get_settings()
    llm_ok = False
    try:
        s.validate_llm_config()
        llm_ok = True
    except RuntimeError:
        pass
    model_ok, model_error = smoke_test_chat_model()
    repo = s.pageindex_path
    pageindex_ok = (repo / "run_pageindex.py").is_file()
    return {
        "status": "ok" if llm_ok and model_ok and pageindex_ok else "degraded",
        "llm_provider": s.provider,
        "llm_model": s.chat_model_name,
        "model_smoke": {
            "ok": model_ok,
            "error": model_error,
        },
        "pageindex": {"available": pageindex_ok, "path": str(repo)},
        "gcs_bucket": s.gcs_bucket,
    }


@router.get("/capabilities")
def v1_capabilities():
    s = get_settings()
    exts = sorted(SUPPORTED)
    return {
        "pageindex_schema_version": "pageindex/1.0",
        "supported_extensions": exts,
        "max_attachment_mb": s.max_upload_mb,
        "models": [s.chat_model_name],
        "attachment_sources": ["gcs", "url"],
        "pageindex_sources": ["inline", "gcs", "url"],
        "endpoints": [
            "POST /v1/documents/index",
            "POST /v1/documents/process",
        ],
    }
