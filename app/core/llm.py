"""Chat model for retrieval and answers (Gemini or OpenAI)."""

import os

from langchain_core.language_models.chat_models import BaseChatModel

from app.config import get_settings


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
