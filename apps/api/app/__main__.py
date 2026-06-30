"""Chạy API theo cổng trong config: `uv run python -m app` (đọc API_PORT từ .env, mặc định 8390)."""

from pathlib import Path

import uvicorn

from app.core.config import settings
from app.core.paths import bulletin_dir

# Watch cả apps/api lẫn services/bulletin (generator/pdf) để hot-reload khi sửa.
_API_DIR = Path(__file__).resolve().parents[1]
_RELOAD_DIRS = [str(p) for p in (_API_DIR, bulletin_dir()) if p.is_dir()]

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
        reload_dirs=_RELOAD_DIRS,
    )
