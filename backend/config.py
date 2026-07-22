from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql://postgres:postgres@localhost:5432/dans_boat_guide"
    public_guide_url: str = "http://localhost:8000/guide/"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from: str = "Dan's Boat Life <guide@dansboatlife.com>"
    sales_sqlite_path: str = "/Users/adrianstock/Documents/Codex/2026-07-16/running-on-this-device-claude-is/outputs/soldboats_full_pass/soldboats_full_structured.sqlite"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def project_root(self) -> Path:
        return Path(__file__).resolve().parents[1]


settings = Settings()
