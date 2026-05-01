"""Pydantic Settings for the web shell.

Configuration is environment-driven with the ``ARCHITHREAT_`` prefix; defaults
match SPEC §5.4 exactly. The Settings object is constructed lazily via
``get_settings()`` so tests can override the environment before instantiation.

We intentionally avoid the optional ``pydantic-settings`` package: the web
extras list (SPEC §5.4) only includes fastapi, uvicorn, jinja2,
python-multipart, and slowapi. We read ``os.environ`` directly and validate via
plain Pydantic.
"""

from __future__ import annotations

import os
from functools import lru_cache

from pydantic import BaseModel, Field, ValidationError


def _env(name: str, default: str) -> str:
    return os.environ.get(f"ARCHITHREAT_{name}", default)


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(f"ARCHITHREAT_{name}")
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"ARCHITHREAT_{name} must be an integer, got {raw!r}") from exc


class Settings(BaseModel):
    """Environment-driven configuration for the FastAPI web shell."""

    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    max_upload_mb: int = Field(default=50, ge=1)
    request_timeout_seconds: int = Field(default=120, ge=1)
    rate_limit_per_minute: int = Field(default=30, ge=0)
    cors_origins: str = Field(default="")
    log_level: str = Field(default="info")
    forwarded_allow_ips: str = Field(default="")

    @classmethod
    def from_env(cls) -> Settings:
        try:
            return cls(
                host=_env("HOST", "0.0.0.0"),
                port=_env_int("PORT", 8000),
                max_upload_mb=_env_int("MAX_UPLOAD_MB", 50),
                request_timeout_seconds=_env_int("REQUEST_TIMEOUT_SECONDS", 120),
                rate_limit_per_minute=_env_int("RATE_LIMIT_PER_MINUTE", 30),
                cors_origins=_env("CORS_ORIGINS", ""),
                log_level=_env("LOG_LEVEL", "info"),
                forwarded_allow_ips=_env("FORWARDED_ALLOW_IPS", ""),
            )
        except ValidationError:
            raise

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance built from the current environment."""
    return Settings.from_env()


def reset_settings_cache() -> None:
    """Clear the cached Settings; tests call this after mutating env vars."""
    get_settings.cache_clear()


__all__ = ["Settings", "get_settings", "reset_settings_cache"]
