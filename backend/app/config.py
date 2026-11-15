from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# Відомий усім секрет лише для локальної розробки. У продакшені запуск із ним заборонено (D08).
DEV_JWT_SECRET = "dev-secret-change-me-in-production"
MIN_PROD_SECRET_LENGTH = 32


class Settings(BaseSettings):
    """Налаштування застосунку. Значення можна перевизначити змінними середовища KASA_* або у файлі .env."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="KASA_")

    env: Literal["dev", "prod"] = "dev"
    database_url: str = "sqlite:///./kasa.db"
    jwt_secret: str = DEV_JWT_SECRET
    jwt_algorithm: str = "HS256"
    jwt_ttl_minutes: int = 60 * 24 * 7
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    upload_dir: str = "uploads"
    max_photo_mb: int = 8
    max_photo_side_px: int = 12000
    db_lock_timeout_s: float = 5.0


class ConfigError(RuntimeError):
    """Неприпустима конфігурація: сервер не повинен приймати запити."""


def validate_settings(s: "Settings") -> None:
    """Перевірка під час запуску. Значення секрету ніколи не потрапляє в повідомлення чи журнали."""
    if s.env != "prod":
        return
    if s.jwt_secret == DEV_JWT_SECRET:
        raise ConfigError("KASA_JWT_SECRET не задано: у режимі prod не можна використовувати секрет розробки")
    if len(s.jwt_secret) < MIN_PROD_SECRET_LENGTH:
        raise ConfigError(f"KASA_JWT_SECRET закороткий: потрібно щонайменше {MIN_PROD_SECRET_LENGTH} символи")


settings = Settings()
