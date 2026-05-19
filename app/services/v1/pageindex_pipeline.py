"""Build PageIndex from a local file path."""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.services.convert import convert_to_indexable
from app.services.pageindex_build import build_index


def build_pageindex_from_file(local_path: Path, filename: str) -> dict[str, Any]:
    """Run conversion (if needed) + PageIndex. Returns raw structure JSON dict."""
    work = Path(tempfile.mkdtemp(prefix="v1_index_"))
    try:
        staged = work / local_path.name
        shutil.copy2(local_path, staged)
        canonical, mode = convert_to_indexable(staged, work)
        out_dir = work / "out"
        out_dir.mkdir(parents=True, exist_ok=True)
        tree_path = build_index(canonical, mode, out_dir)
        return json.loads(tree_path.read_text(encoding="utf-8"))
    finally:
        shutil.rmtree(work, ignore_errors=True)
