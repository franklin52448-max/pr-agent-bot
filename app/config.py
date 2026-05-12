from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import os


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "pr-agent-bot")
    app_version: str = os.getenv("APP_VERSION", "2.0.0")
    price_per_pitch_usdc: Decimal = Decimal(os.getenv("X402_PRICE_USDC", "0.50"))
    default_match_limit: int = int(os.getenv("DEFAULT_MATCH_LIMIT", "12"))
    follow_up_after_days: int = int(os.getenv("FOLLOW_UP_AFTER_DAYS", "3"))
    weekly_update_poll_seconds: int = int(os.getenv("WEEKLY_UPDATE_POLL_SECONDS", "3600"))
    follow_up_poll_seconds: int = int(os.getenv("FOLLOW_UP_POLL_SECONDS", "60"))
    outreach_from_email: str = os.getenv("OUTREACH_FROM_EMAIL", "pitcher@pr-agent-bot.local")
    outreach_from_name: str = os.getenv("OUTREACH_FROM_NAME", "PR Agent Bot")
    email_provider: str = os.getenv("EMAIL_PROVIDER", "smtp").strip().lower()
    resend_api_key: str | None = os.getenv("RESEND_API_KEY")
    sendgrid_api_key: str | None = os.getenv("SENDGRID_API_KEY")
    smtp_host: str | None = os.getenv("SMTP_HOST")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_username: str | None = os.getenv("SMTP_USERNAME")
    smtp_password: str | None = os.getenv("SMTP_PASSWORD")
    smtp_use_tls: bool = _env_bool("SMTP_USE_TLS", True)
    smtp_use_ssl: bool = _env_bool("SMTP_USE_SSL", False)
    dry_run_default: bool = _env_bool("DRY_RUN_DEFAULT", True)
    require_payment_for_send: bool = _env_bool("REQUIRE_PAYMENT_FOR_SEND", False)
    allow_console_sender: bool = _env_bool("ALLOW_CONSOLE_SENDER", False)


settings = Settings()
