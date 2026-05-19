"""Google Cloud Storage: bucket setup, upload, stem-based deduplication."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from app.config import get_settings

logger = logging.getLogger(__name__)

INDEX_BLOB = "index_structure.json"
META_BLOB = "meta.json"
REFERENCE_BUCKET_FOR_LOCATION = "ayc-dev-attachments"


def safe_stem(filename: str) -> str:
    """Filesystem-safe stem used as GCS prefix (dedup key, no extension)."""
    stem = Path(filename).stem
    safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in stem)
    return safe.strip("._") or "document"


def _credentials_path() -> str | None:
    s = get_settings()
    raw = (s.google_application_credentials or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") or "").strip()
    if not raw:
        return None
    p = Path(raw)
    if not p.is_absolute():
        p = s.root / p
    return str(p.resolve()) if p.is_file() else raw


def _gcp_project() -> str | None:
    s = get_settings()
    for candidate in (
        s.gcp_project_id,
        os.environ.get("GOOGLE_CLOUD_PROJECT"),
        os.environ.get("GCP_PROJECT"),
    ):
        if candidate and str(candidate).strip():
            return str(candidate).strip()
    return None


def get_storage_client():
    from google.cloud import storage
    from google.oauth2 import service_account

    cred_path = _credentials_path()
    if cred_path and Path(cred_path).is_file():
        creds = service_account.Credentials.from_service_account_file(
            cred_path,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        logger.debug("GCS client: service account file %s", cred_path)
        return storage.Client(credentials=creds, project=creds.project_id)

    project = _gcp_project()
    logger.debug("GCS client: application default credentials (project=%s)", project)
    return storage.Client(project=project) if project else storage.Client()


def _detect_bucket_location(client) -> str:
    """Match region of an existing project bucket."""
    try:
        ref = client.get_bucket(REFERENCE_BUCKET_FOR_LOCATION)
        loc = (ref.location or "US").upper()
        logger.info("Using GCS location %s (from %s)", loc, REFERENCE_BUCKET_FOR_LOCATION)
        return loc
    except Exception as e:
        logger.warning("Could not read reference bucket location: %s; default US", e)
        return "US"


def ensure_bucket() -> str:
    """Create rocket_uploaded_files if missing. Returns bucket name."""
    s = get_settings()
    bucket_name = s.gcs_bucket.strip()
    if not bucket_name:
        raise RuntimeError("GCS_BUCKET is not set")

    client = get_storage_client()
    bucket = client.bucket(bucket_name)
    if bucket.exists():
        logger.info("GCS bucket exists: %s", bucket_name)
        return bucket_name

    location = (s.gcs_location or "").strip() or _detect_bucket_location(client)
    bucket.location = location
    bucket.storage_class = "STANDARD"
    client.create_bucket(bucket)
    logger.info("Created GCS bucket %s in %s", bucket_name, location)
    return bucket_name


def _stem_prefix(stem: str) -> str:
    return f"{stem}/"


def document_is_indexed(stem: str) -> bool:
    """True if index_structure.json exists for this stem (any prior extension)."""
    s = get_settings()
    client = get_storage_client()
    blob = client.bucket(s.gcs_bucket).blob(f"{stem}/{INDEX_BLOB}")
    return blob.exists()


def get_indexed_meta(stem: str) -> dict | None:
    s = get_settings()
    client = get_storage_client()
    blob = client.bucket(s.gcs_bucket).blob(f"{stem}/{META_BLOB}")
    if not blob.exists():
        return None
    return json.loads(blob.download_as_text(encoding="utf-8"))


def upload_source_file(stem: str, local_path: Path, original_filename: str) -> str:
    """Upload to {stem}/source{ext}. Returns GCS blob path."""
    s = get_settings()
    ext = Path(original_filename).suffix.lower() or ""
    blob_name = f"{stem}/source{ext}"
    client = get_storage_client()
    bucket = client.bucket(s.gcs_bucket)
    blob = bucket.blob(blob_name)
    content_type = _guess_content_type(ext)
    blob.upload_from_filename(str(local_path), content_type=content_type)
    return blob_name


def upload_index_json(stem: str, local_index_path: Path) -> None:
    s = get_settings()
    client = get_storage_client()
    blob = client.bucket(s.gcs_bucket).blob(f"{stem}/{INDEX_BLOB}")
    blob.upload_from_filename(str(local_index_path), content_type="application/json")


def upload_meta(stem: str, meta: dict) -> None:
    s = get_settings()
    client = get_storage_client()
    blob = client.bucket(s.gcs_bucket).blob(f"{stem}/{META_BLOB}")
    blob.upload_from_string(
        json.dumps(meta, indent=2),
        content_type="application/json",
    )


def download_index_to(stem: str, dest_path: Path) -> Path:
    s = get_settings()
    client = get_storage_client()
    blob = client.bucket(s.gcs_bucket).blob(f"{stem}/{INDEX_BLOB}")
    if not blob.exists():
        raise FileNotFoundError(f"No index in GCS for stem '{stem}'")
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    blob.download_to_filename(str(dest_path))
    return dest_path


def _guess_content_type(ext: str) -> str:
    return {
        ".pdf": "application/pdf",
        ".md": "text/markdown",
        ".markdown": "text/markdown",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xls": "application/vnd.ms-excel",
        ".csv": "text/csv",
    }.get(ext, "application/octet-stream")
