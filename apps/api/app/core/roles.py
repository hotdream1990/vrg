"""Nhãn vai trò RBAC (tiếng Việt) — dùng chung cho các file xuất Excel / báo cáo.

Giữ khớp với `apps/web/src/lib/roles.ts`; định nghĩa quyền hạn nằm ở `core/security.py`.
"""

from __future__ import annotations

ROLE_LABEL: dict[str, str] = {
    "admin": "Quản trị viên",
    "executive": "Lãnh đạo Tập đoàn",
    "editor": "Chuyên viên nhập liệu",
    "viewer": "Người xem",
    "member": "Đơn vị thành viên",
    "leader": "Lãnh đạo đơn vị thành viên",
}


def role_label(role: str | None) -> str:
    """Mã vai trò → nhãn; mã lạ thì trả nguyên mã (không giấu dữ liệu)."""
    return ROLE_LABEL.get(role or "", role or "")
