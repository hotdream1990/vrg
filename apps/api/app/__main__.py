"""Chạy API theo cổng trong config: `uv run python -m app` (đọc API_PORT từ .env, mặc định 8390)."""

from pathlib import Path

import uvicorn

from app.core.config import settings

# Watch cả apps/api lẫn services/bulletin (generator/pdf) để hot-reload khi sửa.
_API_DIR = Path(__file__).resolve().parents[1]
_BULLETIN_DIR = _API_DIR.parents[1] / "services" / "bulletin"

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
        reload_dirs=[str(_API_DIR), str(_BULLETIN_DIR)],
    )
