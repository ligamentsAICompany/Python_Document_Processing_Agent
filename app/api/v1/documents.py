"""POST /v1/documents/index and /v1/documents/process."""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Request

from app.api.v1.dependencies import require_v1_auth
from app.schemas.v1 import (
    PROCESS_COLD_EXAMPLE,
    PROCESS_WARM_EXAMPLE,
    IndexRequest,
    ProcessRequest,
    SuccessEnvelope,
)
from app.services.v1.document_service import index_documents, process_documents

router = APIRouter(prefix="/documents", tags=["v1-documents"])


@router.post("/index", response_model=SuccessEnvelope)
async def documents_index(
    body: IndexRequest,
    request: Request,
    _project_id: Annotated[str, Depends(require_v1_auth)],
) -> SuccessEnvelope:
    return await index_documents(body, request_id=request.state.request_id)


@router.post("/process", response_model=SuccessEnvelope)
async def documents_process(
    request: Request,
    _project_id: Annotated[str, Depends(require_v1_auth)],
    body: Annotated[
        ProcessRequest,
        Body(
            openapi_examples={
                "warm": {
                    "summary": "Warm — reuse index from GCS (fast)",
                    "description": (
                        "`pageindex` must be inside each attachment, not at the root. "
                        "Object path must match GCS exactly (TCZZA23)."
                    ),
                    "value": PROCESS_WARM_EXAMPLE,
                },
                "cold": {
                    "summary": "Cold — build index from source then answer (slow)",
                    "description": "Omit `pageindex` on the attachment.",
                    "value": PROCESS_COLD_EXAMPLE,
                },
            },
        ),
    ],
) -> SuccessEnvelope:
    return await process_documents(body, request_id=request.state.request_id)
