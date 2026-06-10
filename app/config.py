from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/mailgenius"
    database_url_sync: str = "postgresql://postgres:postgres@localhost:5432/mailgenius"
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    confirmation_token_ttl_hours: int = 48
    public_api_url: str = "http://localhost:8000"
    tracking_base_url: str = "http://localhost:8000/api/v1/tracking"
    cors_origins: list[str] = ["http://localhost:3000"]
    import_chunk_size: int = 500
    # Redis
    redis_url: str = "redis://localhost:6379/0"
    # Encryption (Fernet key, base64-encoded 32 bytes)
    encryption_key: str = ""
    # SMTP defaults
    default_sender_name: str = "MailGenius"
    default_sender_email: str = "noreply@example.com"
    # Rate limits
    tenant_daily_send_limit: int = 50000
    # Celery
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
