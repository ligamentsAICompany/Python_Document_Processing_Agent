"""Run self-hosted PageIndex to produce *_structure.json."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from app.config import get_settings


def _find_repo() -> Path:
    repo = get_settings().pageindex_path
    run_py = repo / "run_pageindex.py"
    if not run_py.is_file():
        raise FileNotFoundError(
            f"PageIndex not found at {repo}. Clone: "
            "git clone https://github.com/VectifyAI/PageIndex.git PageIndex"
        )
    return repo


def _llm_env_for_subprocess(env: dict[str, str]) -> str:
    """LiteLLM model string passed to run_pageindex.py --model."""
    s = get_settings()
    s.validate_llm_config()
    model = s.litellm_model

    if s.provider == "gemini":
        key = s.gemini_api_key.strip()
        env["GEMINI_API_KEY"] = key
        env.pop("GOOGLE_API_KEY", None)
        env.pop("OPENAI_API_KEY", None)
        env.pop("CHATGPT_API_KEY", None)
    else:
        key = s.openai_api_key.strip()
        env["OPENAI_API_KEY"] = key
        env["CHATGPT_API_KEY"] = key

    return model


def build_index(canonical_path: Path, mode: str, out_dir: Path) -> Path:
    """
    Run PageIndex CLI. mode is 'pdf' or 'md'.
    Returns path to *_structure.json in out_dir.
    """
    s = get_settings()
    repo = _find_repo()
    run_py = repo / "run_pageindex.py"
    out_dir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    model = _llm_env_for_subprocess(env)

    cmd = [
        sys.executable,
        str(run_py),
        "--model",
        model,
        "--if-add-node-id",
        "yes",
        "--if-add-node-summary",
        "yes",
        "--if-add-node-text",
        "yes",
        "--if-add-doc-description",
        "yes",
    ]
    if mode == "pdf":
        cmd.extend(["--pdf_path", str(canonical_path.resolve())])
    else:
        cmd.extend(["--md_path", str(canonical_path.resolve())])

    result = subprocess.run(
        cmd,
        cwd=str(repo),
        env=env,
        capture_output=True,
        text=True,
        timeout=1800,
    )
    if result.returncode != 0:
        err = (result.stderr or result.stdout or "unknown error").strip()
        raise RuntimeError(f"PageIndex build failed: {err[:2000]}")

    stem = canonical_path.stem.replace("_converted", "")
    default_result = repo / "results" / f"{stem}_structure.json"
    if not default_result.is_file():
        alt = repo / "results" / f"{canonical_path.stem}_structure.json"
        default_result = alt if alt.is_file() else default_result

    if not default_result.is_file():
        raise RuntimeError(f"PageIndex did not produce structure JSON at {default_result}")

    dest = out_dir / f"{stem}_structure.json"
    shutil.copy2(default_result, dest)
    return dest
