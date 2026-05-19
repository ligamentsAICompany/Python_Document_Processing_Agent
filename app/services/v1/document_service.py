"""Orchestrate /v1/documents/index and /v1/documents/process."""

from __future__ import annotations

import asyncio
import logging
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.schemas.v1 import (
    AnswerOut,
    AttachmentIn,
    AttachmentResultOut,
    IndexRequest,
    ProcessRequest,
    SuccessEnvelope,
    TimingMsOut,
    UsageOut,
)
from app.services.convert import assert_supported
from app.services.retriever import DocumentRetriever
from app.services.v1.attachment_fetch import (
    fetch_pageindex_json,
    fetch_source_to_file,
)
from app.services.v1.errors import V1Error
from app.services.v1.pageindex_pipeline import build_pageindex_from_file
from app.services.v1.pageindex_wrap import (
    suggested_path_for,
    structure_for_retriever,
    wrap_pageindex,
    write_retriever_file,
)

logger = logging.getLogger(__name__)


def _safe_unlink(path: Path) -> None:
    """Remove a temp file; retry on Windows when PageIndex still holds the handle."""
    if not path.is_file():
        return
    for delay in (0, 0.2, 0.5, 1.0, 2.0, 3.0):
        if delay:
            time.sleep(delay)
        try:
            path.unlink()
            return
        except PermissionError:
            continue
        except OSError as e:
            logger.debug("Could not delete temp file %s: %s", path, e)
            return
    logger.debug("Temp file left on disk (still locked): %s", path)


async def index_documents(
    body: IndexRequest,
    *,
    request_id: str,
) -> SuccessEnvelope:
    t0 = time.perf_counter()
    timing = TimingMsOut()
    results: list[AttachmentResultOut] = []
    pages_parsed = 0

    for att in body.attachments:
        t_fetch = time.perf_counter()
        try:
            result, parse_ms, pages, _tree = await _index_one_attachment(att, warm=False)
        except FileNotFoundError as e:
            raise V1Error(
                404,
                "ATTACHMENT_NOT_FOUND",
                str(e),
                request_id=request_id,
            ) from e
        except ValueError as e:
            raise V1Error(
                400,
                "INVALID_ATTACHMENT",
                str(e),
                request_id=request_id,
            ) from e
        except RuntimeError as e:
            raise V1Error(
                502,
                "INDEX_FAILED",
                str(e),
                request_id=request_id,
                retryable=True,
            ) from e

        timing.fetch += int((time.perf_counter() - t_fetch) * 1000)
        timing.parse += parse_ms
        pages_parsed += pages
        results.append(result)

    timing.total = int((time.perf_counter() - t0) * 1000)
    return SuccessEnvelope(
        request_id=request_id,
        attachments=results,
        usage=UsageOut(pages_parsed=pages_parsed, model=_model_label()),
        timing_ms=timing,
    )


async def process_documents(
    body: ProcessRequest,
    *,
    request_id: str,
) -> SuccessEnvelope:
    t0 = time.perf_counter()
    timing = TimingMsOut()
    results: list[AttachmentResultOut] = []
    pages_parsed = 0
    retriever_path: Path | None = None

    for i, att in enumerate(body.attachments):
        warm = att.pageindex is not None
        t_fetch = time.perf_counter()
        try:
            result, parse_ms, pages, tree_path = await _index_one_attachment(
                att,
                warm=warm,
                return_pageindex=body.options.return_pageindex,
            )
        except FileNotFoundError as e:
            raise V1Error(
                404,
                "ATTACHMENT_NOT_FOUND",
                str(e),
                request_id=request_id,
            ) from e
        except ValueError as e:
            raise V1Error(
                400,
                "INVALID_ATTACHMENT",
                str(e),
                request_id=request_id,
            ) from e
        except RuntimeError as e:
            raise V1Error(
                502,
                "INDEX_FAILED",
                str(e),
                request_id=request_id,
                retryable=True,
            ) from e

        timing.fetch += int((time.perf_counter() - t_fetch) * 1000)
        timing.parse += parse_ms
        pages_parsed += pages
        results.append(result)
        if i == 0 and tree_path is not None:
            retriever_path = tree_path

    answer_text = ""
    if retriever_path is None and results and results[0].pageindex:
        retriever_path = _write_temp_tree(results[0].pageindex)

    if retriever_path:
        t_ret = time.perf_counter()
        retriever = DocumentRetriever(retriever_path)
        timing.retrieve = int((time.perf_counter() - t_ret) * 1000)
        t_gen = time.perf_counter()
        answer_text = await retriever.ask(body.prompt)
        timing.generate = int((time.perf_counter() - t_gen) * 1000)
    else:
        raise V1Error(
            500,
            "RETRIEVER_UNAVAILABLE",
            "Could not load pageindex for answering.",
            request_id=request_id,
        )

    timing.total = int((time.perf_counter() - t0) * 1000)
    return SuccessEnvelope(
        request_id=request_id,
        answer=AnswerOut(text=answer_text),
        attachments=results,
        usage=UsageOut(pages_parsed=pages_parsed, model=_model_label()),
        timing_ms=timing,
    )


async def _index_one_attachment(
    att: AttachmentIn,
    *,
    warm: bool,
    return_pageindex: bool = True,
) -> tuple[AttachmentResultOut, int, int, Path | None]:
    """Returns (result, parse_ms, pages_parsed, optional retriever tree path)."""
    parse_ms = 0
    pages = 0
    tree_path: Path | None = None
    source = att.source
    obj = source.get("object") or ""

    if warm and att.pageindex:
        wrapped = await asyncio.to_thread(fetch_pageindex_json, att.pageindex)
        if wrapped.get("schema_version") != "pageindex/1.0":
            wrapped = wrap_pageindex(
                structure_for_retriever(wrapped),
                filename=att.filename,
                mime_type=att.mime_type,
                byte_size=0,
                checksum="sha256:reused",
            )
        tree_path = _write_temp_tree(wrapped)
        pageindex_out = wrapped if return_pageindex else None
        return (
            AttachmentResultOut(
                id=att.id,
                pageindex_used="reused",
                pageindex=pageindex_out,
                suggested_path=suggested_path_for(obj) if obj else None,
                checksum=(wrapped.get("source") or {}).get("checksum"),
            ),
            parse_ms,
            pages,
            tree_path,
        )

    assert_supported(att.filename)
    local_path, checksum = await asyncio.to_thread(
        fetch_source_to_file, source, att.filename
    )
    staged_path: Path | None = None
    try:
        byte_size = local_path.stat().st_size
        _check_size(byte_size)

        # Copy so GCS download temp can be released before PageIndex (Windows file locks).
        staged_path = Path(tempfile.mkstemp(suffix=local_path.suffix)[1])
        await asyncio.to_thread(shutil.copy2, local_path, staged_path)
        _safe_unlink(local_path)
        local_path = staged_path

        t_parse = time.perf_counter()
        raw = await asyncio.to_thread(
            build_pageindex_from_file, staged_path, att.filename
        )
        parse_ms = int((time.perf_counter() - t_parse) * 1000)
        pages = _count_pages(raw)

        wrapped = wrap_pageindex(
            raw,
            filename=att.filename,
            mime_type=att.mime_type,
            byte_size=byte_size,
            checksum=checksum,
        )
        tree_path = _write_temp_tree(wrapped)
        pageindex_out = wrapped if return_pageindex else None
        return (
            AttachmentResultOut(
                id=att.id,
                pageindex_used="generated",
                pageindex=pageindex_out,
                suggested_path=suggested_path_for(obj) if obj else f"{att.filename}.pageindex.json",
                checksum=checksum,
            ),
            parse_ms,
            pages,
            tree_path,
        )
    finally:
        if staged_path is not None:
            _safe_unlink(staged_path)
        elif local_path.is_file():
            _safe_unlink(local_path)


def _write_temp_tree(pageindex: dict[str, Any]) -> Path:
    path = Path(tempfile.mkstemp(suffix="_structure.json")[1])
    write_retriever_file(pageindex, path)
    return path


def _check_size(byte_size: int) -> None:
    limit = get_settings().max_upload_bytes
    if byte_size > limit:
        raise ValueError(
            f"Attachment exceeds max size ({get_settings().max_upload_mb} MB)"
        )


def _count_pages(raw: dict[str, Any]) -> int:
    structure = raw.get("structure") if isinstance(raw, dict) else raw
    if not structure:
        return 0
    max_idx = 0

    def walk(nodes: list | dict) -> None:
        nonlocal max_idx
        if isinstance(nodes, dict):
            nodes = [nodes]
        for n in nodes:
            if not isinstance(n, dict):
                continue
            idx = n.get("end_index") or n.get("start_index") or 0
            if isinstance(idx, int):
                max_idx = max(max_idx, idx)
            for c in n.get("nodes") or []:
                walk(c)

    if isinstance(structure, list):
        walk(structure)
    else:
        walk([structure])
    return max_idx or 1


def _model_label() -> str:
    s = get_settings()
    return s.chat_model_name if s.provider == "gemini" else s.openai_model
