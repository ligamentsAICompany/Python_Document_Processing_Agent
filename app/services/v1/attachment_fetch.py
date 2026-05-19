"""Fetch attachment bytes from GCS or URL into a temp file."""

from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path
from typing import Any

import httpx

from app.services.gcs_store import get_storage_client


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return f"sha256:" + h.hexdigest()


def fetch_source_to_file(source: dict[str, Any], filename: str) -> tuple[Path, str]:
    """
    Download source to a temp file. Returns (path, checksum).
    Raises ValueError / FileNotFoundError on failure.
    """
    stype = (source.get("type") or "").lower()
    suffix = Path(filename).suffix or ".bin"

    if stype == "gcs":
        bucket = source["bucket"]
        obj = source["object"]
        auth = source.get("auth") or {}
        mode = (auth.get("mode") or "service_account").lower()

        if mode == "signed_url":
            url = auth.get("signed_url") or ""
            if not url:
                raise ValueError("gcs auth.mode=signed_url requires signed_url")
            return _fetch_url_to_file(url, suffix, headers=None)

        client = get_storage_client()
        blob = client.bucket(bucket).blob(obj)
        if not blob.exists():
            raise FileNotFoundError(f"GCS object not found: gs://{bucket}/{obj}")
        tmp = Path(tempfile.mkstemp(suffix=suffix)[1])
        blob.download_to_filename(str(tmp))
        return tmp, sha256_file(tmp)

    if stype == "url":
        url = source.get("url") or ""
        headers = source.get("headers")
        return _fetch_url_to_file(url, suffix, headers=headers)

    raise ValueError(f"Unsupported source type: {stype}. Use gcs or url.")


def fetch_pageindex_json(pageindex: dict[str, Any]) -> dict[str, Any]:
    """Load pageindex object from inline, gcs, or url ref."""
    ptype = (pageindex.get("type") or "inline").lower()

    if ptype == "inline":
        data = pageindex.get("data")
        if not isinstance(data, dict):
            raise ValueError("pageindex inline requires data object")
        return data

    if ptype == "gcs":
        bucket = pageindex["bucket"]
        obj = pageindex["object"]
        auth = pageindex.get("auth") or {}
        mode = (auth.get("mode") or "service_account").lower()
        if mode == "signed_url":
            import json

            url = auth.get("signed_url") or ""
            with httpx.Client(timeout=120.0) as client:
                r = client.get(url)
                r.raise_for_status()
                return json.loads(r.text)
        client = get_storage_client()
        blob = client.bucket(bucket).blob(obj)
        if not blob.exists():
            raise FileNotFoundError(f"pageindex not found: gs://{bucket}/{obj}")
        import json

        return json.loads(blob.download_as_text(encoding="utf-8"))

    if ptype == "url":
        import json

        url = pageindex.get("url") or ""
        headers = pageindex.get("headers")
        with httpx.Client(timeout=120.0) as client:
            r = client.get(url, headers=headers or {})
            r.raise_for_status()
            return json.loads(r.text)

    raise ValueError(f"Unsupported pageindex type: {ptype}")


def _fetch_url_to_file(
    url: str,
    suffix: str,
    headers: dict[str, str] | None,
) -> tuple[Path, str]:
    tmp = Path(tempfile.mkstemp(suffix=suffix)[1])
    with httpx.Client(timeout=300.0, follow_redirects=True) as client:
        with client.stream("GET", url, headers=headers or {}) as r:
            r.raise_for_status()
            with tmp.open("wb") as f:
                for chunk in r.iter_bytes():
                    f.write(chunk)
    return tmp, sha256_file(tmp)
