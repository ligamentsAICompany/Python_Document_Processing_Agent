"""Document Processing Agent — FastAPI entry (v1 platform API)."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.config import get_settings
from app.core.llm import smoke_test_chat_model
from app.services.v1.errors import V1Error

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    s.uploads_dir.mkdir(parents=True, exist_ok=True)
    s.indexes_dir.mkdir(parents=True, exist_ok=True)
    repo = s.pageindex_path
    if not (repo / "run_pageindex.py").is_file():
        logging.getLogger("uvicorn.error").warning(
            "PageIndex not found at %s — clone before indexing PDFs/MD",
            repo,
        )
    try:
        s.validate_llm_config()
        logging.getLogger("uvicorn.error").info(
            "LLM: %s (%s)", s.provider, s.litellm_model
        )
        model_ok, model_error = smoke_test_chat_model(force=True)
        if model_ok:
            logging.getLogger("uvicorn.error").info(
                "LLM model smoke check passed: %s", s.chat_model_name
            )
        else:
            logging.getLogger("uvicorn.error").warning(
                "LLM model smoke check failed: %s", model_error
            )
    except RuntimeError as e:
        logging.getLogger("uvicorn.error").warning("LLM config: %s", e)
    try:
        from app.services.gcs_store import ensure_bucket

        ensure_bucket()
        logging.getLogger("uvicorn.error").info("GCS bucket ready: %s", s.gcs_bucket)
    except Exception as e:
        logging.getLogger("uvicorn.error").warning("GCS setup: %s", e)
    yield


app = FastAPI(
    title="Document Processing Agent",
    description=(
        "Stateless document index + Q&A API for orchestrator agents. "
        "Use /api/v1/documents/index and /api/v1/documents/process."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")


@app.exception_handler(V1Error)
async def v1_error_handler(_request: Request, exc: V1Error):
    detail = exc.detail if isinstance(exc.detail, dict) else {"error": {"message": str(exc.detail)}}
    return JSONResponse(status_code=exc.status_code, content=detail)


@app.exception_handler(HTTPException)
async def http_error_handler(_request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict) and exc.detail.get("status") == "error":
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.get("/", include_in_schema=False)
def root():
    return {
        "service": "document-processing-agent",
        "docs": "/docs",
        "api": {
            "health": "/api/v1/health",
            "capabilities": "/api/v1/capabilities",
            "index": "POST /api/v1/documents/index",
            "process": "POST /api/v1/documents/process",
        },
    }
