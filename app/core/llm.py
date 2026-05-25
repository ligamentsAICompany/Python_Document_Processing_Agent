"""Chat model for retrieval and answers (Gemini or OpenAI)."""

from __future__ import annotations

import logging
import os
import time

from langchain_core.language_models.chat_models import BaseChatModel

from app.config import get_settings

logger = logging.getLogger(__name__)
_SMOKE_CACHE_TTL_SECONDS = 300
_smoke_cache: dict[str, tuple[float, bool, str | None]] = {}


def _clean_model_error(message: str, model: str) -> str:
    if (
        "NOT_FOUND" in message
        or "not found" in message.lower()
        or "no longer available" in message
    ):
        return (
            f"Model '{model}' is not available for generation. "
            "Set GEMINI_MODEL to a supported Gemini model."
        )
    if "API key" in message or "PERMISSION_DENIED" in message or "403" in message:
        return "The configured Gemini API key cannot access the selected model."
    if "RESOURCE_EXHAUSTED" in message or "quota" in message.lower() or "429" in message:
        return "The configured Gemini project is out of quota or rate limited."
    compact = " ".join(message.split())
    return compact[:300] if compact else "The configured model smoke test failed."


def smoke_test_chat_model(*, force: bool = False) -> tuple[bool, str | None]:
    """Verify the configured generation model is callable.

    Gemini model metadata can list preview ids that still fail generateContent.
    This lightweight call catches that at startup/health instead of during indexing.
    """
    s = get_settings()
    try:
        s.validate_llm_config()
    except RuntimeError as e:
        return False, str(e)

    if s.provider != "gemini":
        return True, None

    cache_key = f"{s.provider}:{s.chat_model_name}:{bool(s.gemini_api_key.strip())}"
    now = time.time()
    cached = _smoke_cache.get(cache_key)
    if cached and not force and now - cached[0] < _SMOKE_CACHE_TTL_SECONDS:
        return cached[1], cached[2]

    try:
        from google import genai

        client = genai.Client(api_key=s.gemini_api_key.strip())
        client.models.generate_content(
            model=s.chat_model_name,
            contents="Reply with OK only.",
        )
        _smoke_cache[cache_key] = (now, True, None)
        return True, None
    except Exception as e:
        logger.warning(
            "Gemini model smoke check failed for %s: %s", s.chat_model_name, e
        )
        message = _clean_model_error(str(e), s.chat_model_name)
        _smoke_cache[cache_key] = (now, False, message)
        return False, message


def get_chat_model() -> BaseChatModel:
    s = get_settings()
    s.validate_llm_config()

    if s.provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        key = s.gemini_api_key.strip()
        os.environ["GEMINI_API_KEY"] = key
        # Avoid duplicate-key warning from google-genai (prefer GEMINI_API_KEY only)
        os.environ.pop("GOOGLE_API_KEY", None)
        return ChatGoogleGenerativeAI(
            model=s.chat_model_name,
            google_api_key=key,
            temperature=0,
        )

    from langchain_openai import ChatOpenAI

    key = s.openai_api_key.strip()
    os.environ.setdefault("OPENAI_API_KEY", key)
    return ChatOpenAI(
        model=s.chat_model_name,
        api_key=key,
        temperature=0,
    )
