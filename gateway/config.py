"""Configuration loaded from environment / .env file."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Server
    gateway_host: str = "0.0.0.0"
    gateway_port: int = 8000

    # Admin
    admin_api_key: str = "change-me-admin-key"

    # Database (SQLite file path)
    database_url: str = "./gateway.db"

    # Logging
    log_level: str = "INFO"

    # Provider base URLs
    openai_base_url: str = "https://api.openai.com/v1"
    anthropic_base_url: str = "https://api.anthropic.com"

    # Optional fallback provider keys (used when caller does not supply a key)
    openai_api_key: str = ""
    anthropic_api_key: str = ""


settings = Settings()
