"""Định vị thư mục `services/` (bulletin, crawlers…) — chạy đúng cả khi dev lẫn trong image gộp.

- Dev: dò ngược từ file này tới thư mục cha chứa `services/bulletin`.
- Image gộp: đặt sẵn biến môi trường `VRG_SERVICES_DIR=/app/services`.

Hàm KHÔNG bao giờ raise — nếu đường dẫn không tồn tại, tính năng phụ thuộc
(quét giá, sinh bản tin) tự xử lý lỗi runtime thay vì làm app không khởi động được.
"""

from __future__ import annotations

import os
from pathlib import Path


def services_dir() -> Path:
    """Đường dẫn thư mục `services/`."""
    env = os.getenv("VRG_SERVICES_DIR")
    if env:
        return Path(env)
    for parent in Path(__file__).resolve().parents:
        if (parent / "services" / "bulletin").is_dir():
            return parent / "services"
    # Fallback an toàn: cạnh thư mục cài đặt (vd /app/services trong image).
    return Path(__file__).resolve().parents[2] / "services"


def bulletin_dir() -> Path:
    """Thư mục `services/bulletin` (chứa package `bulletin` → import convert/generator)."""
    return services_dir() / "bulletin"


def crawlers_dir() -> Path:
    """Thư mục `services/crawlers` (chứa crawler chạy bằng subprocess)."""
    return services_dir() / "crawlers"
