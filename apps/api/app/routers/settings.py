"""Router cài đặt đọc-được cho mọi tài khoản đăng nhập (khác /api/config chỉ-admin).

Hiện chỉ trả cửa sổ nhập liệu (số ngày) để frontend dựng chế độ chỉ-xem cho ngày cũ.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.core import edit_window

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/edit-windows")
def edit_windows() -> dict:
    """Số ngày sửa được (đơn vị thành viên · chuyên viên) + hôm nay (giờ VN) cho frontend."""
    return {
        "member_days": edit_window.member_window(),
        "editor_days": edit_window.editor_window(),
        "today": edit_window.today().isoformat(),
    }
