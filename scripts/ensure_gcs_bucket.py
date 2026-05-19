"""Create rocket_uploaded_files bucket if missing. Run from project root."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.gcs_store import ensure_bucket

if __name__ == "__main__":
    name = ensure_bucket()
    print(f"Bucket ready: {name}")
