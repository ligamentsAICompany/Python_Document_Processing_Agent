"""V1 API errors (document-processing-agent.txt §10)."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from app.schemas.v1 import ErrorDetail, ErrorEnvelope


class V1Error(HTTPException):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        *,
        request_id: str,
        details: dict[str, Any] | None = None,
        retryable: bool = False,
    ):
        body = ErrorEnvelope(
            request_id=request_id,
            error=ErrorDetail(
                code=code,
                message=message,
                details=details,
                retryable=retryable,
            ),
        )
        super().__init__(status_code=status_code, detail=body.model_dump())
