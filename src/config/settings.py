"""Dynaconf-backed application settings."""

from functools import lru_cache
from pathlib import Path
from typing import Any

from dynaconf import Dynaconf

ROOT_DIR = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT_DIR / "config"


def _settings_files() -> list[str]:
    files = [CONFIG_DIR / "settings.yml"]
    files.extend(sorted((CONFIG_DIR / "apis").glob("*.yml")))
    return [str(path) for path in files if path.exists()]


class Settings:
    """Small compatibility wrapper around Dynaconf values."""

    def __init__(self) -> None:
        self._settings = Dynaconf(
            envvar_prefix=False,
            load_dotenv=True,
            settings_files=_settings_files(),
        )

    def get(self, key: str, default: Any = None) -> Any:
        return self._settings.get(key, default)

    @property
    def openai_api_key(self) -> str:
        return str(self.get("OPENAI_API_KEY", ""))

    @property
    def model_to_use(self) -> str:
        return str(self.get("MODEL_TO_USE", "gpt-4o"))

    @property
    def temperature(self) -> float:
        return float(self.get("TEMPERATURE", 0.0))

    @property
    def max_tokens(self) -> int:
        return int(self.get("MAX_TOKENS", 4096))

    @property
    def llm_provider(self) -> str:
        return str(self.get("LLM_PROVIDER", "langchain_openai"))

    @property
    def llm_timeout_seconds(self) -> int:
        return int(self.get("LLM_TIMEOUT_SECONDS", 120))

    @property
    def host(self) -> str:
        return str(self.get("HOST", "0.0.0.0"))

    @property
    def port(self) -> int:
        return int(self.get("PORT", 8000))

    @property
    def retry(self) -> int:
        return int(self.get("RETRY", 3))

    @property
    def log_level(self) -> str:
        return str(self.get("LOG_LEVEL", "INFO"))

    @property
    def aws_region(self) -> str:
        return str(self.get("AWS_REGION", "us-east-1"))

    @property
    def aws_access_key_id(self) -> str:
        return str(self.get("AWS_ACCESS_KEY_ID", ""))

    @property
    def aws_secret_access_key(self) -> str:
        return str(self.get("AWS_SECRET_ACCESS_KEY", ""))

    @property
    def stock_sheet_pdf_max_pages(self) -> int:
        return int(self.get("STOCK_SHEET_PDF_MAX_PAGES", 3))

    @property
    def stock_sheet_max_image_pixels(self) -> int:
        return int(self.get("STOCK_SHEET_MAX_IMAGE_PIXELS", 25_000_000))

    @property
    def stock_sheet_enable_preprocess(self) -> bool:
        return bool(self.get("STOCK_SHEET_ENABLE_PREPROCESS", True))

    @property
    def stock_sheet_llm_batch_size(self) -> int:
        return int(self.get("STOCK_SHEET_LLM_BATCH_SIZE", 60))


@lru_cache
def get_settings() -> Settings:
    """Return cached settings."""

    return Settings()
