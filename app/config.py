from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from pathlib import Path


ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ENV_PATH), env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Scholarly Aether API"
    secret_key: str
    access_token_expires_minutes: int = 60 * 24
    algorithm: str = "HS256"

    database_url: str

    firecrawl_api_key: str
    firecrawl_base_url: str = "https://api.firecrawl.dev"

    llm_base_url: str = "http://localhost:1234/v1"
    llm_model: str = "local-model"
    llm_api_key: str | None = None

    pdf_output_dir: str = "./storage/pdfs"

    redis_url: str = "redis://redis:6379/0"
    rq_queue_name: str = "crawl"
    use_queue: bool = True

    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str | None = None

    password_reset_code_expiry_minutes: int = 10


@lru_cache
def get_settings() -> Settings:
    return Settings()
