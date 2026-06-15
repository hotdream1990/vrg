"""Cấu hình ứng dụng — đọc từ biến môi trường (.env). Không hardcode secret."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8390
    cors_origins: list[str] = ["http://localhost:5390"]

    # Placeholders — điền giá trị thật trong .env (xem .env.example ở repo root)
    database_url: str = ""
    anthropic_api_key: str = ""


settings = Settings()
