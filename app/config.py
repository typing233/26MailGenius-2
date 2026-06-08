from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/mailgenius"
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    confirmation_token_ttl_hours: int = 48
    public_api_url: str = "http://localhost:8000"
    cors_origins: list[str] = ["http://localhost:3000"]
    import_chunk_size: int = 500

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
