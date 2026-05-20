from functools import lru_cache

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "THOR-HelpDesk"
    environment: str = "local"
    api_prefix: str = "/api/v1"
    database_url: str = Field(
        default="postgresql+psycopg://helpdesk:helpdesk@localhost:5432/helpdesk"
    )
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    jwt_secret_key: str = "change-me-in-production"
    vault_secret_key: str | None = None
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 8

    zapi_base_url: AnyHttpUrl | None = None
    zapi_instance_id: str | None = None
    zapi_token: str | None = None
    zapi_client_token: str | None = None

    media_storage_dir: str = "/app/media"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
