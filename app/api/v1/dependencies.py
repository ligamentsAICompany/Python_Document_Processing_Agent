"""V1 auth and request context."""

import uuid
from typing import Annotated

from fastapi import Depends, Header, Request

from app.config import get_settings
from app.services.v1.errors import V1Error


def resolve_request_id(
    x_request_id: Annotated[str | None, Header(alias="X-Request-Id")] = None,
) -> str:
    if x_request_id and x_request_id.strip():
        return x_request_id.strip()
    return str(uuid.uuid4())


def require_v1_auth(
    request: Request,
    request_id: Annotated[str, Depends(resolve_request_id)],
    authorization: Annotated[str | None, Header()] = None,
    x_project_id: Annotated[str | None, Header(alias="X-Project-Id")] = None,
) -> str:
    request.state.request_id = request_id
    if not x_project_id or not x_project_id.strip():
        raise V1Error(
            400,
            "MISSING_PROJECT_ID",
            "Header X-Project-Id is required.",
            request_id=request_id,
        )

    key = get_settings().service_api_key.strip()
    if key:
        if not authorization or not authorization.startswith("Bearer "):
            raise V1Error(
                401,
                "UNAUTHORIZED",
                "Authorization: Bearer <SERVICE_API_KEY> required.",
                request_id=request_id,
            )
        token = authorization.removeprefix("Bearer ").strip()
        if token != key:
            raise V1Error(
                401,
                "UNAUTHORIZED",
                "Invalid API key.",
                request_id=request_id,
            )

    return x_project_id.strip()
