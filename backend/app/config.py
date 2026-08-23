import os
from pathlib import Path
from typing import List, Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Determine project directories
_current_dir = Path(__file__).resolve().parent
_backend_dir = _current_dir.parent
_project_root = _backend_dir.parent

_env_candidates = [
    _project_root / ".env",
    _backend_dir / ".env",
    Path(".env").resolve(),
]
_env_file = next((str(p) for p in _env_candidates if p.is_file()), None)

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=_env_file,
        env_file_encoding="utf-8",
        extra="allow",
    )

    PROJECT_NAME: str = "Clinica"

    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    DATABASE_URL: str = f"sqlite:///{(_project_root / 'healthcare.db').as_posix()}"
    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""
    SLOT_HOLD_DURATION_MINUTES: int = 5
    DEFAULT_SLOT_DURATION_MINUTES: int = 30
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]
    AI_PROVIDER: str = "gemini"
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.6-flash"
    # Phase 2B: Notification / SMTP settings (all optional – defaults to no-op)
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    NOTIFICATION_FROM_EMAIL: str = "noreply@clinica.local"
    NOTIFICATION_ENABLED: bool = False

    @field_validator("SECRET_KEY", mode="before")
    @classmethod
    def validate_secret_key(cls, v: Optional[str]) -> str:
        secret = (v or os.getenv("SECRET_KEY", "")).strip()
        if not secret:
            raise ValueError(
                "CRITICAL SECURITY ERROR: SECRET_KEY environment variable is required and cannot be empty. "
                "Please configure SECRET_KEY in your environment or .env file."
            )
        if secret in ("unthinkable-ai-super-secret-jwt-key-2026", "secret", "changeme", "default"):
            raise ValueError(
                "CRITICAL SECURITY ERROR: SECRET_KEY is set to an insecure default value. "
                "A strong, unique cryptographic secret key is required."
            )
        return secret

settings = Settings()

