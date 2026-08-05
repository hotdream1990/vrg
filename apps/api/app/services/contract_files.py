"""Lưu/đọc chứng từ đính kèm (bộ Hợp đồng · phiếu xuất kho · hoá đơn) của biểu Tiêu thụ – Tồn kho.

Lưu file cục bộ dưới `data_dir()/unit-daily-contracts/` (mount volume khi deploy — như ảnh bản tin).
Tên lưu là uuid; tên gốc giữ riêng ở payload để hiển thị. Trả về tên lưu để ghi vào dòng.

Định dạng nhận: xem `_TYPES` — tài liệu (PDF/Word/Excel/XML hoá đơn điện tử), ảnh scan (kể cả
HEIC của iPhone) và ZIP để gói cả bộ hợp đồng nhiều văn bản vào 1 file.
CỐ Ý KHÔNG nhận SVG/HTML và mọi loại chạy được: file được phục vụ lại cho trình duyệt, hai loại
này chèn được JavaScript và sẽ chạy dưới chính tên miền của hệ thống.
"""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile

from app.core.paths import data_dir

_DIR = data_dir() / "unit-daily-contracts"
_MAX_BYTES = 25 * 1024 * 1024  # 25 MB — đủ cho bản scan nhiều trang hoặc 1 gói ZIP cả bộ HĐ

# đuôi file → (kiểu MIME khi trả về, có cho XEM THẲNG trong trình duyệt không)
# Loại không xem thẳng được thì ép TẢI VỀ, tránh trình duyệt tự đoán kiểu và diễn giải nhầm.
_TYPES: dict[str, tuple[str, bool]] = {
    ".pdf": ("application/pdf", True),
    ".jpg": ("image/jpeg", True),
    ".jpeg": ("image/jpeg", True),
    ".png": ("image/png", True),
    ".webp": ("image/webp", True),
    ".gif": ("image/gif", True),
    ".heic": ("image/heic", False),      # ảnh mặc định của iPhone
    ".heif": ("image/heif", False),
    ".tif": ("image/tiff", False),       # máy scan văn phòng hay xuất TIFF
    ".tiff": ("image/tiff", False),
    ".doc": ("application/msword", False),
    ".docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", False),
    ".xls": ("application/vnd.ms-excel", False),
    ".xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", False),
    ".xml": ("application/xml", False),  # bản gốc hoá đơn điện tử
    ".zip": ("application/zip", False),  # gói cả bộ hợp đồng + đợt giao
}

# Kiểu MIME trình duyệt khai báo → đuôi file, dùng khi tên file không có đuôi.
_CT_EXT = {
    "application/pdf": ".pdf", "image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp",
    "image/gif": ".gif", "image/heic": ".heic", "image/heif": ".heif", "image/tiff": ".tif",
    "application/msword": ".doc", "application/vnd.ms-excel": ".xls",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "application/xml": ".xml", "text/xml": ".xml", "application/zip": ".zip",
    "application/x-zip-compressed": ".zip",
}

ACCEPT_LABEL = "PDF · Word · Excel · XML · ảnh (JPG, PNG, HEIC, WEBP, TIFF) · ZIP"


def _ext_of(file: UploadFile) -> str | None:
    """Đuôi file hợp lệ — ưu tiên tên file (đáng tin hơn), sau đó mới tới kiểu MIME.

    Trình duyệt khai kiểu MIME rất lệch nhau: HEIC trên Windows thường về rỗng, XML lúc
    `text/xml` lúc `application/xml`, .docx đôi khi về `application/octet-stream`.
    """
    ext = Path(file.filename or "").suffix.lower()
    if ext in _TYPES:
        return ext
    return _CT_EXT.get((file.content_type or "").split(";")[0].strip().lower())


def save(file: UploadFile) -> dict:
    """Lưu file upload → trả {file: tên-lưu, filename: tên-gốc, size}. Kiểm định dạng + kích thước."""
    ext = _ext_of(file)
    if not ext:
        raise HTTPException(400, f"Định dạng không hỗ trợ. Chỉ nhận: {ACCEPT_LABEL}.")
    _DIR.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}{ext}"
    dest = _DIR / name
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    size = dest.stat().st_size
    if size > _MAX_BYTES:
        dest.unlink(missing_ok=True)
        raise HTTPException(400, f"File quá lớn (tối đa {_MAX_BYTES // (1024 * 1024)} MB).")
    return {"file": name, "filename": (file.filename or name)[:200], "size": size}


def path_for(name: str) -> Path:
    """Đường dẫn file theo tên lưu (chặn path traversal). 404 nếu không có."""
    safe = Path(name).name  # bỏ mọi thành phần thư mục
    p = _DIR / safe
    if not safe or not p.is_file():
        raise HTTPException(404, "Không tìm thấy file hợp đồng.")
    return p


def serve(name: str, filename: str | None = None):
    """FileResponse an toàn: đúng kiểu MIME, chặn trình duyệt đoán kiểu, ép tải về khi cần.

    `filename` (tên gốc do client gửi kèm) chỉ dùng để đặt tên lúc tải về cho dễ đọc.
    """
    from fastapi.responses import FileResponse

    p = path_for(name)
    media, inline = _TYPES.get(p.suffix.lower(), ("application/octet-stream", False))
    nice = Path(filename or "").name[:200] or p.name
    headers = {"X-Content-Type-Options": "nosniff"}
    if inline:
        return FileResponse(str(p), media_type=media, headers=headers)
    return FileResponse(str(p), media_type=media, headers=headers, filename=nice)
