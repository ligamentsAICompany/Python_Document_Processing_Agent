"""API request/response models."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    pageindex_ready: bool
    gcs_ready: bool = False
    gcs_bucket: str | None = None
