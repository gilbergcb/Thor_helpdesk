import logging
from functools import lru_cache

from pydantic import AnyHttpUrl, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_logger = logging.getLogger("security.config")
_WEAK_JWT_SECRETS = {"change-me-in-production", "", "secret", "changeme"}


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
    # F-04 / Phase 2.2 — chave antiga aceita só em decifragem durante rotação.
    # Setar via env durante a janela de rotação; remover após rodar
    # `re_encrypt_all_credentials`.
    vault_secret_key_old: str | None = None
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 8

    zapi_base_url: AnyHttpUrl | None = None
    zapi_instance_id: str | None = None
    zapi_token: str | None = None
    zapi_client_token: str | None = None

    media_storage_dir: str = "/app/media"
    public_app_url: AnyHttpUrl = "https://helpdesk.thorconsultoria.com.br"

    # --- Security convergence batch 1 (feature flags) ---
    # Cada flag aceita: "off" | "audit" | "enforce".
    # - off     : comportamento legado, sem checagem.
    # - audit   : checa e LOGA violações, mas NÃO bloqueia (default seguro/compatível).
    # - enforce : bloqueia requisições que falham na checagem.
    security_media_auth: str = "audit"
    security_webhook_hmac: str = "audit"
    security_ssrf_allowlist: str = "audit"
    # F-05 Phase 4.1: tenant isolation em /tickets/*. Default audit
    # durante janela de 7 dias antes do flip para enforce.
    security_tenant_isolation: str = "audit"
    # F-09: aceita "on"/"off" (mapeados internamente para enforce/off).
    security_ratelimit_login: str = "on"
    # Protecao compatível para o portal publico de ticket.
    security_public_link_guard: str = "on"
    # F-public-uploads: limites do upload via portal.
    public_upload_max_bytes: int = 15 * 1024 * 1024  # 15 MB por arquivo
    public_upload_max_files_per_request: int = 3
    public_upload_quota_bytes_per_hour: int = 50 * 1024 * 1024  # 50 MB / token / hora
    waiting_customer_auto_close_enabled: bool = True
    waiting_customer_auto_close_hours: int = 24
    waiting_customer_auto_close_interval_seconds: int = 600
    # Hosts permitidos no download de mídia (Z-API + CDNs WhatsApp).
    # Separados por vírgula. Sufixos casam por endswith.
    ssrf_allowed_hosts: str = (
        "api.z-api.io,"
        ".z-api.io,"
        ".whatsapp.net,"
        ".whatsapp.com,"
        "mmg.whatsapp.net,"
        ".cdninstagram.com,"
        ".fbcdn.net"
    )

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @model_validator(mode="after")
    def _assert_jwt_secret_strength(self) -> "Settings":
        """F-13: rejeita boot em produção com JWT secret fraco/default.
        Em dev/staging, só WARNING."""
        secret = (self.jwt_secret_key or "").strip()
        is_weak = secret in _WEAK_JWT_SECRETS or len(secret) < 32
        if not is_weak:
            return self
        env = (self.environment or "").lower()
        msg = (
            f"JWT_SECRET_KEY fraco ou default detectado "
            f"(len={len(secret)}, env={env!r}). "
            "Gere com `python -c 'import secrets; print(secrets.token_urlsafe(64))'`."
        )
        if env == "production":
            raise ValueError(msg)
        _logger.warning("F-13 startup assert: %s (somente WARNING fora de production)", msg)
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
