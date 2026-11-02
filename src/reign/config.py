"""Application configuration via pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///./reign.db"
    host: str = "127.0.0.1"
    app_env: str = "development"
    log_level: str = "INFO"
    cors_origins: list[str] = ["http://localhost:8000", "http://127.0.0.1:8000"]
    max_csv_bytes: int = 5 * 1024 * 1024
    max_json_bytes: int = 10 * 1024 * 1024
    backups_dir: str = "./backups"
    alert_smtp_host: str = ""
    alert_smtp_port: int = 587
    alert_smtp_user: str = ""
    alert_smtp_password: str = ""
    alert_email_from: str = ""
    alert_email_to: str = ""
    alert_webhook_url: str = ""


settings = Settings()
