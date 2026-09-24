"""Router cài đặt đọc-được cho mọi tài khoản đăng nhập (khác /api/config chỉ-admin).

Hiện chỉ trả cửa sổ nhập liệu để frontend dựng chế độ chỉ-xem cho ngày đã quá hạn.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.core import edit_window

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/edit-windows")
def edit_windows() -> dict:
    """Cửa sổ nhập liệu (đơn vị thành viên · chuyên viên) theo giờ server (giờ VN).

    `*_editable_from` = ngày số liệu cũ nhất còn nhập/sửa được NGAY LÚC NÀY (đã tính giờ chốt) —
    web so thẳng với mốc này, không tự tính giờ ở trình duyệt (đồng hồ máy người dùng có thể lệch).
    Có thể lớn hơn `today` (N = 0 và đã qua giờ chốt ⇒ hôm nay cũng đã khoá).
    `next_change_at` = giờ chốt kế tiếp (ISO, có múi giờ): trang để mở qua mốc này hẹn giờ tải lại;
    `now` = giờ server lúc trả lời, để web tính khoảng chờ không phụ thuộc đồng hồ máy người dùng.
    """
    now = edit_window.now()
    member, editor = edit_window.member_window(), edit_window.editor_window()
    return {
        "member_days": member,
        "editor_days": editor,
        "member_editable_from": edit_window.editable_from(member, now).isoformat(),
        "editor_editable_from": edit_window.editable_from(editor, now).isoformat(),
        "cutoff_hour": edit_window.cutoff_hour(),
        "today": now.date().isoformat(),
        "now": now.isoformat(),
        "next_change_at": edit_window.next_change_at(now).isoformat(),
    }
