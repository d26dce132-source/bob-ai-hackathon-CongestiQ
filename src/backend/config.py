"""
Application configuration loaded from environment variables.
Uses pydantic-settings so every variable has a type and a default.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database — override via DATABASE_URL environment variable or .env file
    # The default below is a local-dev convenience value only.
    # In any shared or production environment, always set DATABASE_URL explicitly.
    database_url: str = "postgresql://congestiq:congestiq@localhost:5432/congestiq"

    # Server
    app_port: int = 8000
    app_env: str = "development"

    # CORS — stored as a comma-separated string in .env
    # Kept as a plain string and split at use-time to avoid pydantic-settings
    # JSON-parsing issues across different versions.
    cors_origins_str: str = "http://localhost:5173,http://localhost:3000"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_origins_str.split(",") if o.strip()]


settings = Settings()
