"""Application settings from environment."""

from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

_ROOT = Path(__file__).resolve().parent.parent
_ENV = _ROOT / ".env"
if _ENV.is_file():
    load_dotenv(_ENV, override=True)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(_ENV), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM: "gemini" (default) or "openai"
    llm_provider: str = "gemini"

    openai_api_key: str = ""
    openai_model: str = "gpt-4o"

    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"

    pageindex_repo: str = "./PageIndex"
    data_dir: str = "./data"
    max_upload_mb: int = 50

    # Local dev: path to ligaments-portal-*.json (see README). Cloud Run: leave unset (ADC).
    google_application_credentials: str = ""
    gcp_project_id: str = "ligaments-portal"
    gcs_bucket: str = "rocket_uploaded_files"
    gcs_location: str = ""

    # V1 platform API (optional; if empty, Bearer auth is skipped for local dev)
    service_api_key: str = ""

    @property
    def root(self) -> Path:
        return _ROOT

    @property
    def uploads_dir(self) -> Path:
        return (_ROOT / self.data_dir / "uploads").resolve()

    @property
    def indexes_dir(self) -> Path:
        return (_ROOT / self.data_dir / "indexes").resolve()

    @property
    def pageindex_path(self) -> Path:
        p = Path(self.pageindex_repo)
        if not p.is_absolute():
            p = _ROOT / p
        return p.resolve()

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def provider(self) -> str:
        return (self.llm_provider or "gemini").strip().lower()

    @property
    def litellm_model(self) -> str:
        """Model id for PageIndex (LiteLLM)."""
        if self.provider == "gemini":
            m = (self.gemini_model or "gemini-2.0-flash").strip()
            return m if m.startswith("gemini/") else f"gemini/{m}"
        return (self.openai_model or "gpt-4o").strip()

    @property
    def chat_model_name(self) -> str:
        """Model id for LangChain chat (no provider prefix for Gemini)."""
        if self.provider == "gemini":
            m = (self.gemini_model or "gemini-2.0-flash").strip()
            return m.removeprefix("gemini/")
        return (self.openai_model or "gpt-4o").strip()

    def validate_llm_config(self) -> None:
        if self.provider == "gemini":
            if not self.gemini_api_key.strip():
                raise RuntimeError("GEMINI_API_KEY is not set in .env")
        elif self.provider == "openai":
            if not self.openai_api_key.strip():
                raise RuntimeError("OPENAI_API_KEY is not set in .env")
        else:
            raise RuntimeError(f"Unknown LLM_PROVIDER: {self.llm_provider}")


def get_settings() -> Settings:
    return Settings()
