"""Chạy API theo cổng trong config: `uv run python -m app` (đọc API_PORT từ .env, mặc định 8390)."""

import uvicorn

from app.core.config import settings

if __name__ == "__main__":
    uvicorn.run("app.main:app", host=settings.api_host, port=settings.api_port, reload=True)
