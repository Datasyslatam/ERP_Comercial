"""Configuración central. Todo valor sensible llega por variables de entorno (ver .env.example)."""
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "DATASYS ERP"
    environment: Literal["development", "test", "staging", "production"] = "development"
    debug: bool = False

    database_url: str = "postgresql+psycopg://erp:erp@localhost:5432/erp"
    db_pool_size: int = 10
    db_max_overflow: int = 20

    # Autenticación
    auth_mode: Literal["local", "oidc"] = "local"
    jwt_secret: str = Field(default="", description="Obligatorio fuera de desarrollo; mínimo 32 caracteres")
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 7
    oidc_issuer: str = ""
    oidc_audience: str = ""
    oidc_jwks_url: str = ""
    max_failed_logins: int = 5
    lockout_minutes: int = 15
    password_min_length: int = 12
    # Parámetros Argon2id (valores por defecto de OWASP; en pruebas se reducen para acelerar)
    argon2_time_cost: int = 3
    argon2_memory_kib: int = 65536
    argon2_parallelism: int = 4

    # Seguridad HTTP
    cors_origins: list[str] = ["http://localhost:5173"]
    rate_limit_per_minute: int = 300
    login_rate_limit_per_minute: int = 10
    trusted_proxy_count: int = 1

    # Almacenamiento de adjuntos
    storage_path: str = "./storage"
    max_upload_mb: int = 20

    # Facturación electrónica: nombre del adaptador por país (ver integrations/einvoicing)
    einvoice_adapter_co: str = "sandbox_dian"
    einvoice_adapter_ve: str = "sandbox_seniat"

    sentry_dsn: str = ""
    log_level: str = "INFO"

    @field_validator("database_url")
    @classmethod
    def _normalize_db_url(cls, v: str) -> str:
        # Railway y otros PaaS entregan postgres:// o postgresql:// sin driver.
        if v.startswith("postgres://"):
            v = "postgresql://" + v[len("postgres://"):]
        if v.startswith("postgresql://"):
            v = "postgresql+psycopg://" + v[len("postgresql://"):]
        return v

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, v):
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    def validate_for_runtime(self) -> None:
        if self.environment in ("staging", "production"):
            if len(self.jwt_secret) < 32 and self.auth_mode == "local":
                raise RuntimeError("JWT_SECRET debe tener al menos 32 caracteres en staging/producción")
            if self.debug:
                raise RuntimeError("DEBUG no puede estar activo en staging/producción")
        if self.auth_mode == "oidc" and not (self.oidc_issuer and self.oidc_jwks_url and self.oidc_audience):
            raise RuntimeError("AUTH_MODE=oidc requiere OIDC_ISSUER, OIDC_AUDIENCE y OIDC_JWKS_URL")

    @property
    def effective_jwt_secret(self) -> str:
        if self.jwt_secret:
            return self.jwt_secret
        if self.environment in ("development", "test"):
            return "dev-only-insecure-secret-change-me-0123456789"
        raise RuntimeError("JWT_SECRET no configurado")


@lru_cache
def get_settings() -> Settings:
    return Settings()
