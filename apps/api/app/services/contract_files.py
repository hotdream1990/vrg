"""Lưu/đọc file Hợp đồng đính kèm ở tồn kho đã có HĐ (biểu Tiêu thụ – Tồn kho).

Lưu file cục bộ dưới `data_dir()/unit-daily-contracts/` (mount volume khi deploy — như ảnh bản tin).
Chỉ nhận PDF + ảnh (JPG/PNG). Trả về tên file lưu (uuid) để ghi vào payload dòng tồn kho.
"""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile

from app.core.paths import data_dir

_DIR = data_dir() / "unit-daily-contracts"
_EXT = {"application/pdf": ".pdf", "image/jpeg": ".jpg", "image/png": ".png"}
_MAX_BYTES = 15 * 1024 * 1024  # 15 MB


def save(file: UploadFile) -> dict:
    """Lưu file upload → trả {file: tên-lưu, filename: tên-gốc, size}. Kiểm định dạng + kích thước."""
    ext = _EXT.get(file.content_type or "")
    if not ext:
        raise HTTPException(400, "Chỉ nhận file PDF hoặc ảnh JPG/PNG.")
    _DIR.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}{ext}"
    dest = _DIR / name
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    size = dest.stat().st_size
    if size > _MAX_BYTES:
        dest.unlink(missing_ok=True)
        raise HTTPException(400, "File quá lớn (tối đa 15 MB).")
    return {"file": name, "filename": (file.filename or name)[:200], "size": size}


def path_for(name: str) -> Path:
    """Đường dẫn file theo tên lưu (chặn path traversal). 404 nếu không có."""
    safe = Path(name).name  # bỏ mọi thành phần thư mục
    p = _DIR / safe
    if not safe or not p.is_file():
        raise HTTPException(404, "Không tìm thấy file hợp đồng.")
    return p
