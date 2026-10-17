"""Environment loading. DAY1_SALT is read once, only from the process environment."""
from __future__ import annotations

import os
from dataclasses import dataclass, field


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class Settings:
    # repr=False so the salt can never leak through logging/printing a Settings object.
    day1_salt: str = field(repr=False)
    database_url: str
    redis_url: str
    pool_max: int = 40
    body_limit_bytes: int = 1024 * 1024
    rate_limit_requests: int = 100
    rate_limit_window_seconds: float = 10.0
    token_ttl_seconds: int = 4 * 3600


_settings: Settings | None = None


def load_settings(env: dict | None = None) -> Settings:
    env = os.environ if env is None else env
    salt = env.get("DAY1_SALT")
    if salt is None or salt == "":
        raise ConfigError(
            "DAY1_SALT is not set. Start with: DAY1_SALT=<team-secret> docker compose up -d --build"
        )
    return Settings(
        day1_salt=salt,
        database_url=env.get("DATABASE_URL", "postgresql://nascon:nascon@db:5432/nascon"),
        redis_url=env.get("REDIS_URL", "redis://redis:6379/0"),
        pool_max=int(env.get("DB_POOL_MAX", "40")),
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
