"""Pydantic models for /v1/documents/* (document-processing-agent.txt)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

SchemaVersion = Literal["pageindex/1.0"]


class GcsAuth(BaseModel):
    mode: Literal["signed_url", "service_account", "adc"] = "service_account"
    signed_url: str | None = None
    service_account: dict[str, Any] | None = None


class GcsSource(BaseModel):
    type: Literal["gcs"] = "gcs"
    bucket: str
    object: str
    auth: GcsAuth = Field(default_factory=GcsAuth)


class UrlSource(BaseModel):
    type: Literal["url"] = "url"
    url: str
    headers: dict[str, str] | None = None


class InlinePageindexSource(BaseModel):
    type: Literal["inline"] = "inline"
    data: dict[str, Any]


class AttachmentSource(BaseModel):
    """Discriminated union via validation in service layer."""

    type: str
    bucket: str | None = None
    object: str | None = None
    url: str | None = None
    auth: GcsAuth | None = None
    headers: dict[str, str] | None = None


class PageindexRef(BaseModel):
    type: Literal["inline", "gcs", "url"] = "inline"
    data: dict[str, Any] | None = None
    bucket: str | None = None
    object: str | None = None
    url: str | None = None
    auth: GcsAuth | None = None
    headers: dict[str, str] | None = None


class AttachmentIn(BaseModel):
    id: str
    filename: str
    mime_type: str | None = None
    source: dict[str, Any]
    pageindex: dict[str, Any] | None = None


class RetrievalOptions(BaseModel):
    top_k: int = 8
    rerank: bool = True


class ProcessOptions(BaseModel):
    return_pageindex: bool = True
    model: str = "default"
    max_output_tokens: int = 2048
    temperature: float = 0.2
    language: str = "auto"
    retrieval: RetrievalOptions = Field(default_factory=RetrievalOptions)


class IndexOptions(BaseModel):
    model: str = "default"
    language: str = "auto"


_GLOSSARY_SOURCE = {
    "type": "gcs",
    "bucket": "rocket_uploaded_files",
    "object": "Glossary_3HH12916AAAATCZZA23/source.pdf",
    "auth": {"mode": "service_account"},
}
_GLOSSARY_PAGEINDEX = {
    "type": "gcs",
    "bucket": "rocket_uploaded_files",
    "object": "Glossary_3HH12916AAAATCZZA23/index_structure.json",
    "auth": {"mode": "service_account"},
}

# Swagger / OpenAPI examples (copy as-is; do not paste only `pageindex` at root).
PROCESS_WARM_EXAMPLE: dict[str, Any] = {
    "prompt": "What is this document about? Give 3 bullet points.",
    "attachments": [
        {
            "id": "att_1",
            "filename": "Glossary_3HH12916AAAATCZZA23.pdf",
            "source": _GLOSSARY_SOURCE,
            "pageindex": _GLOSSARY_PAGEINDEX,
        }
    ],
    "options": {"return_pageindex": False},
}

PROCESS_COLD_EXAMPLE: dict[str, Any] = {
    "prompt": "What is this document about? Give 3 bullet points.",
    "attachments": [
        {
            "id": "att_1",
            "filename": "Glossary_3HH12916AAAATCZZA23.pdf",
            "source": _GLOSSARY_SOURCE,
        }
    ],
    "options": {"return_pageindex": True},
}


class ProcessRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    attachments: list[AttachmentIn] = Field(..., min_length=1)
    options: ProcessOptions = Field(default_factory=ProcessOptions)
    metadata: dict[str, Any] | None = None

    model_config = {
        "json_schema_extra": {
            "examples": [PROCESS_WARM_EXAMPLE, PROCESS_COLD_EXAMPLE],
        }
    }


class IndexRequest(BaseModel):
    attachments: list[AttachmentIn] = Field(..., min_length=1)
    options: IndexOptions = Field(default_factory=IndexOptions)
    metadata: dict[str, Any] | None = None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "attachments": [
                        {
                            "id": "att_1",
                            "filename": "Glossary_3HH12916AAAATCZZA23.pdf",
                            "mime_type": "application/pdf",
                            "source": _GLOSSARY_SOURCE,
                        }
                    ]
                }
            ]
        }
    }


class CitationOut(BaseModel):
    attachment_id: str
    page: int | None = None
    span: list[int] | None = None
    snippet: str | None = None


class AnswerOut(BaseModel):
    text: str
    citations: list[CitationOut] = Field(default_factory=list)


class AttachmentResultOut(BaseModel):
    id: str
    pageindex_used: Literal["generated", "reused"]
    pageindex: dict[str, Any] | None = None
    suggested_path: str | None = None
    checksum: str | None = None
    schema_version: SchemaVersion = "pageindex/1.0"


class UsageOut(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    pages_parsed: int = 0
    model: str = ""


class TimingMsOut(BaseModel):
    fetch: int = 0
    parse: int = 0
    retrieve: int = 0
    generate: int = 0
    total: int = 0


class SuccessEnvelope(BaseModel):
    request_id: str
    status: Literal["success"] = "success"
    answer: AnswerOut | None = None
    attachments: list[AttachmentResultOut] = Field(default_factory=list)
    usage: UsageOut = Field(default_factory=UsageOut)
    timing_ms: TimingMsOut = Field(default_factory=TimingMsOut)


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None
    retryable: bool = False


class ErrorEnvelope(BaseModel):
    request_id: str
    status: Literal["error"] = "error"
    error: ErrorDetail
