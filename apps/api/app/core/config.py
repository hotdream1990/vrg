"""Cấu hình ứng dụng — đọc từ biến môi trường (.env). Không hardcode secret."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8390
    cors_origins: list[str] = ["http://localhost:5390"]

    # DB dev default khớp infra/docker (cổng 5433, mật khẩu compose mặc định "changeme").
    # Production: BẮT BUỘC ghi đè qua .env, không dùng mật khẩu mặc định.
    database_url: str = "postgresql://vrg:changeme@localhost:5433/vrg_caosu"

    # Placeholders — điền giá trị thật trong .env (xem .env.example ở repo root)
    anthropic_api_key: str = ""


settings = Settings()
