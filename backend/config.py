from __future__ import annotations
import json
from pathlib import Path
from typing import List
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    APP_ENV: str = "development"
    APP_NAME: str = "PayPal RecoverIQ"
    APP_SECRET_KEY: str = "dev-secret-key-change-in-production"
    JWT_SECRET_KEY: str = "dev-jwt-secret-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://recoveriq:recoveriq_local_password@localhost:5432/recoveriq"

    # Redis / Celery
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_MAX_TOKENS: int = 2000
    OPENAI_TIMEOUT_SECONDS: int = 30

    # PayPal
    PAYPAL_ENV: str = "sandbox"
    PAYPAL_BASE_URL: str = "https://api-m.sandbox.paypal.com"
    PAYPAL_CLIENT_ID: str = ""
    PAYPAL_CLIENT_SECRET: str = ""
    PAYPAL_WEBHOOK_ID: str = ""
    PAYPAL_CURRENCY: str = "USD"
    PAYPAL_HTTP_TIMEOUT_SECONDS: int = 20

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]

    # Recovery settings
    REMINDER_DAYS_BEFORE_DUE: int = 1
    REMINDER_DAYS_AFTER_DUE: List[int] = [1, 3, 7]
    MAX_REMINDERS_PER_INVOICE_PER_DAY: int = 2
    WEBHOOK_PROCESSING_QUEUE: str = "paypal-webhooks"

    # Logging
    LOG_LEVEL: str = "INFO"
    SENTRY_DSN: str = ""

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @field_validator("REMINDER_DAYS_AFTER_DUE", mode="before")
    @classmethod
    def parse_reminder_days(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return [int(d.strip()) for d in v.split(",") if d.strip()]
        return v

    @model_validator(mode="after")
    def validate_paypal_env(self):
        if self.PAYPAL_ENV not in ("sandbox", "live"):
            raise ValueError("PAYPAL_ENV must be 'sandbox' or 'live'")
        if self.PAYPAL_ENV == "live" and self.PAYPAL_BASE_URL == "https://api-m.sandbox.paypal.com":
            raise ValueError("PAYPAL_BASE_URL must be live URL when PAYPAL_ENV=live")
        return self

    @property
    def is_sandbox(self) -> bool:
        return self.PAYPAL_ENV == "sandbox"

    @property
    def openai_configured(self) -> bool:
        return bool(self.OPENAI_API_KEY)

    @property
    def paypal_configured(self) -> bool:
        return bool(self.PAYPAL_CLIENT_ID and self.PAYPAL_CLIENT_SECRET)


settings = Settings()
