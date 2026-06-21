from __future__ import annotations

import os
from dataclasses import dataclass


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name, str(default)).strip()
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


def _csv_env(name: str, default: str = "") -> list[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    database_url: str
    redis_url: str
    github_webhook_secret: str
    dashboard_api_token: str
    max_webhook_bytes: int
    webhook_rate_limit_per_minute: int
    celery_task_max_retries: int
    deploy_mode: str
    deploy_command: str
    deploy_timeout_seconds: int
    allowed_repository: str
    allowed_branch: str
    app_env: str
    log_level: str
    cors_origins: list[str]


def load_settings() -> Settings:
    return Settings(
        database_url=os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg://relayops:relayops@db:5432/relayops",
        ),
        redis_url=os.getenv("REDIS_URL", "redis://redis:6379/0"),
        github_webhook_secret=os.getenv("GITHUB_WEBHOOK_SECRET", ""),
        dashboard_api_token=os.getenv("DASHBOARD_API_TOKEN", ""),
        max_webhook_bytes=_int_env("MAX_WEBHOOK_BYTES", 1_048_576),
        webhook_rate_limit_per_minute=_int_env("WEBHOOK_RATE_LIMIT_PER_MINUTE", 60),
        celery_task_max_retries=_int_env("CELERY_TASK_MAX_RETRIES", 3),
        deploy_mode=os.getenv("DEPLOY_MODE", "simulate").strip().lower(),
        deploy_command=os.getenv("DEPLOY_COMMAND", "").strip(),
        deploy_timeout_seconds=_int_env("DEPLOY_TIMEOUT_SECONDS", 120),
        allowed_repository=os.getenv("ALLOWED_REPOSITORY", "").strip(),
        allowed_branch=os.getenv("ALLOWED_BRANCH", "").strip(),
        app_env=os.getenv("APP_ENV", "development").strip(),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        cors_origins=_csv_env("CORS_ORIGINS", "http://localhost:8080"),
    )


settings = load_settings()
