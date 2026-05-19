"""Wrap PageIndex structure JSON as pageindex/1.0 for v1 API responses."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import json


def wrap_pageindex(
    raw: dict[str, Any],
    *,
    filename: str,
    mime_type: str | None,
    byte_size: int,
    checksum: str,
) -> dict[str, Any]:
    """Spec envelope; keeps PageIndex tree in `structure` for our retriever."""
    if isinstance(raw, list):
        structure = raw
    elif isinstance(raw, dict):
        structure = raw.get("structure", raw)
        if structure is raw and "schema_version" in raw:
            structure = raw.get("structure") or []
    else:
        structure = raw

    outline = _structure_to_outline(structure)
    return {
        "schema_version": "pageindex/1.0",
        "source": {
            "filename": filename,
            "mime_type": mime_type or "application/octet-stream",
            "byte_size": byte_size,
            "checksum": checksum,
        },
        "parser": {
            "name": "pageindex",
            "version": "oss",
            "ocr": False,
        },
        "structure": structure,
        "outline": outline,
        "pages": [],
        "chunks": [],
        "metadata": {"doc_name": raw.get("doc_name") if isinstance(raw, dict) else None},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def structure_for_retriever(pageindex: dict[str, Any]) -> dict[str, Any]:
    """Extract retriever-compatible JSON from wrapped or raw pageindex."""
    if pageindex.get("schema_version") == "pageindex/1.0":
        structure = pageindex.get("structure")
        doc_name = (pageindex.get("metadata") or {}).get("doc_name")
        if isinstance(structure, list):
            return {"doc_name": doc_name, "structure": structure}
        return {"doc_name": doc_name, "structure": structure or []}
    if "structure" in pageindex:
        return pageindex
    return {"structure": pageindex}


def write_retriever_file(pageindex: dict[str, Any], path: Path) -> Path:
    data = structure_for_retriever(pageindex)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _structure_to_outline(structure: Any) -> list[dict[str, Any]]:
    if not structure:
        return []

    def walk(nodes: list | dict) -> list[dict[str, Any]]:
        if isinstance(nodes, dict):
            nodes = [nodes]
        out = []
        for n in nodes:
            if not isinstance(n, dict):
                continue
            item: dict[str, Any] = {
                "title": n.get("title", ""),
                "page": n.get("start_index"),
            }
            children = n.get("nodes")
            if children:
                item["children"] = walk(children)
            out.append(item)
        return out

    if isinstance(structure, list):
        return walk(structure)
    return walk([structure])


def suggested_path_for(source_object: str) -> str:
    return f"{source_object}.pageindex.json"
