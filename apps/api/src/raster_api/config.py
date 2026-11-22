from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:8088"]
    # Read-only role (raplm_reader). The API never receives write credentials.
    database_url: str = "postgresql+psycopg://raplm_reader:raplm_reader_dev@127.0.0.1:5433/raplm"
    max_compare_units: int = 4
    max_compare_periods: int = 8

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
