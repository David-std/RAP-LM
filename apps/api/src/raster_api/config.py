from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:8088"]
    # Cloud demo: host of the static web service (render.yaml), allowed as https origin.
    web_origin_host: str | None = None
    # Read-only role (raplm_reader). The API never receives write credentials.
    database_url: str = "postgresql+psycopg://raplm_reader:raplm_reader_dev@127.0.0.1:5433/raplm"
    max_compare_units: int = 4
    max_compare_periods: int = 24  # all published years of one band
    # Serialised /risk responses kept per worker (about 4.4 MB each for the full 1 km map).
    risk_cache_entries: int = 16

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def sqlalchemy_url(self) -> str:
        """Managed providers hand out ``postgresql://`` URLs; the API uses the psycopg 3 driver."""
        url = self.database_url
        return (
            "postgresql+psycopg://" + url.split("://", 1)[1]
            if url.startswith("postgresql://")
            else url
        )

    @property
    def allowed_origins(self) -> list[str]:
        extra = [f"https://{self.web_origin_host}"] if self.web_origin_host else []
        return [*self.cors_origins, *extra]


@lru_cache
def get_settings() -> Settings:
    return Settings()
