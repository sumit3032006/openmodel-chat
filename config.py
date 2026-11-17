"""Central application settings.

Secrets are read only from environment variables (or a local, Git-ignored .env file).
The API key field uses repr=False so it can never leak through print() or logs.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"
load_dotenv(ENV_FILE)


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    app_name: str = "OpenModel Chat"
    version: str = "1.0.0"
    openrouter_base_url: str = os.getenv(
        "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
    ).rstrip("/")
    host: str = os.getenv("HOST", "127.0.0.1")
    port: int = _int_env("PORT", 8080)
    request_timeout: float = _float_env("REQUEST_TIMEOUT_SECONDS", 90.0)
    data_dir: Path = BASE_DIR / "data"
    db_path: Path = BASE_DIR / "data" / "chats.db"
    builtin_models_path: Path = BASE_DIR / "models" / "models.json"
    user_models_path: Path = BASE_DIR / "data" / "user_models.json"
    env_file: Path = ENV_FILE
    openrouter_api_key: str = field(
        default=os.getenv("OPENROUTER_API_KEY", "").strip(), repr=False
    )


settings = Settings()
