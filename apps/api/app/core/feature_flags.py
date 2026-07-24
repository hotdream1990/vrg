"""Công tắc bật/tắt tính năng ở mức hệ thống — đổi giá trị rồi triển khai lại là xong.

Giữ ở đây (thay vì rải rác trong router) để bật/tắt chỉ sửa MỘT chỗ.
"""

from __future__ import annotations

from fastapi import HTTPException

# Nhập liệu bằng Excel (tải mẫu · xem trước · ghi) — TẠM TẮT theo yêu cầu vận hành.
# Bật lại: đổi thành True (frontend đổi EXCEL_IMPORT_ENABLED trong ExcelImportBar.tsx).
EXCEL_IMPORT_ENABLED = False

_EXCEL_OFF = ("Nhập liệu bằng Excel đang tạm ngưng — vui lòng nhập trực tiếp trên biểu mẫu "
              "của hệ thống.")


def require_excel_import() -> None:
    """Dependency chặn mọi endpoint nhập Excel khi tính năng đang tắt."""
    if not EXCEL_IMPORT_ENABLED:
        raise HTTPException(503, _EXCEL_OFF)
