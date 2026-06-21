"""
Centralized application configuration.

All runtime configuration (database URL, CORS, metadata) is read from
environment variables via pydantic-settings, so the same code works
locally (.env file), in Docker, and on Render with zero changes.
"""
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg2://user:password@localhost:5432/products"
    api_title: str = "CodeVector Product Browser"
    api_version: str = "1.0.0"
    cors_origins: List[str] = ["*"]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
