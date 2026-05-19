"""Convert uploads to PDF or Markdown for PageIndex indexing."""

from __future__ import annotations

import csv
from pathlib import Path

import mammoth
import pandas as pd
from markdownify import markdownify

SUPPORTED = {".pdf", ".md", ".markdown", ".docx", ".xlsx", ".xls", ".csv"}


def assert_supported(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED:
        raise ValueError(
            f"Unsupported file type '{ext}'. Supported: {', '.join(sorted(SUPPORTED))}"
        )
    return ext


def convert_to_indexable(source: Path, work_dir: Path) -> tuple[Path, str]:
    """
    Return (path_for_pageindex, mode) where mode is 'pdf' or 'md'.
  """
    ext = source.suffix.lower()
    work_dir.mkdir(parents=True, exist_ok=True)

    if ext == ".pdf":
        return source, "pdf"
    if ext in (".md", ".markdown"):
        return source, "md"
    if ext == ".docx":
        return _docx_to_md(source, work_dir), "md"
    if ext in (".xlsx", ".xls"):
        return _excel_to_md(source, work_dir), "md"
    if ext == ".csv":
        return _csv_to_md(source, work_dir), "md"
    raise ValueError(f"Unsupported extension: {ext}")


def _docx_to_md(source: Path, work_dir: Path) -> Path:
    with source.open("rb") as f:
        result = mammoth.convert_to_html(f)
    if result.messages:
        warnings = [str(m) for m in result.messages]
        # non-fatal conversion notes
        _ = warnings
    html = result.value
    md_body = markdownify(html, heading_style="ATX")
    out = work_dir / f"{source.stem}_converted.md"
    out.write_text(f"# {source.stem}\n\n{md_body}", encoding="utf-8")
    return out


def _excel_to_md(source: Path, work_dir: Path) -> Path:
    out = work_dir / f"{source.stem}_converted.md"
    parts = [f"# {source.stem}\n"]
    sheets = pd.read_excel(source, sheet_name=None, engine="openpyxl")
    for sheet_name, df in sheets.items():
        parts.append(f"\n## {sheet_name}\n\n")
        parts.append(_dataframe_to_md_table(df))
    out.write_text("\n".join(parts), encoding="utf-8")
    return out


def _csv_to_md(source: Path, work_dir: Path) -> Path:
    out = work_dir / f"{source.stem}_converted.md"
    df = pd.read_csv(source)
    body = _dataframe_to_md_table(df)
    out.write_text(f"# {source.stem}\n\n{body}", encoding="utf-8")
    return out


def _dataframe_to_md_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_No rows._\n"
    df = df.fillna("")
    headers = [str(c) for c in df.columns]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for _, row in df.iterrows():
        cells = [str(v).replace("|", "\\|").replace("\n", " ") for v in row.tolist()]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"
