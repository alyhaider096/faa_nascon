"""Environment loading. Signing salts are read once, only from the process environment."""
from __future__ import annotations

import os
from dataclasses import dataclass, field


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class Settings:
    # repr=False so the salt can never leak through logging/printing a Settings object.
    day1_salt: str = field(repr=False)
    day2_salt: str = field(repr=False)
    database_url: str
    redis_url: str
    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "nascon"
    minio_secret_key: str = field(default="nascon-minio-dev", repr=False)
    minio_bucket: str = "nascon-vod"
    recordings_dir: str = "/recordings"
    pool_max: int = 40
    body_limit_bytes: int = 1024 * 1024
    rate_limit_requests: int = 100
    rate_limit_window_seconds: float = 10.0
    token_ttl_seconds: int = 4 * 3600
    check_runtime_dependencies: bool = False
    public_base_url: str = "http://localhost:8080"
    media_public_host: str = "localhost"
    cors_origins: tuple[str, ...] = (
        "http://localhost:19006",
        "http://127.0.0.1:19006",
    )


_settings: Settings | None = None


def load_settings(env: dict | None = None) -> Settings:
    env = os.environ if env is None else env
    salt = env.get("DAY1_SALT")
    day2_salt = env.get("DAY2_SALT")
    if salt is None or salt == "":
        raise ConfigError(
            "DAY1_SALT is not set. Start with: DAY1_SALT=<team-secret> docker compose up -d --build"
        )
    if day2_salt is None or day2_salt == "":
        raise ConfigError(
            "DAY2_SALT is not set. Start with both DAY1_SALT and DAY2_SALT in the environment."
        )
    cors_origins = tuple(
        origin.strip()
        for origin in env.get(
            "CORS_ORIGINS",
            "http://localhost:19006,http://127.0.0.1:19006",
        ).split(",")
        if origin.strip()
    )
    return Settings(
        day1_salt=salt,
        day2_salt=day2_salt,
        database_url=env.get("DATABASE_URL", "postgresql://nascon:nascon@db:5432/nascon"),
        redis_url=env.get("REDIS_URL", "redis://redis:6379/0"),
        minio_endpoint=env.get("MINIO_ENDPOINT", "minio:9000"),
        minio_access_key=env.get("MINIO_ROOT_USER", "nascon"),
        minio_secret_key=env.get("MINIO_ROOT_PASSWORD", "nascon-minio-dev"),
        minio_bucket=env.get("MINIO_VOD_BUCKET", "nascon-vod"),
        recordings_dir=env.get("RECORDINGS_DIR", "/recordings"),
        pool_max=int(env.get("DB_POOL_MAX", "40")),
        check_runtime_dependencies=env.get("CHECK_RUNTIME_DEPENDENCIES", "0") == "1",
        public_base_url=env.get("PUBLIC_BASE_URL", "http://localhost:8080").rstrip("/"),
        media_public_host=env.get("MEDIA_PUBLIC_HOST", "localhost"),
        cors_origins=cors_origins,
    )


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = load_settings()
    return _settings


def set_settings(settings: Settings | None) -> None:
    """Test hook: inject (or clear) settings."""
    global _settings
    _settings = settings
