"""Phạm vi truy cập của hộp thư Hỗ trợ & Thông báo — dùng chung cho các router `support*`.

MỘT bộ endpoint phục vụ cả hai phía; `scope_dep` quyết định tài khoản đang đứng ở bên nào và ĐƯỢC
THẤY những đơn vị nào (server tự ép, KHÔNG tin danh sách client gửi lên):
  - `role=leader`  → bên `unit`, phạm vi = các đơn vị được gán;
  - quyền `support` (admin/chuyên viên) → bên `hq`, phạm vi = mọi đơn vị (`companies=None`).
Vai trò khác — kể cả `member` (tài khoản nhập liệu của chính đơn vị đó) — đều bị chặn 403.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException

from app.core.permissions import LEVEL_EDIT
from app.core.security import assert_cap, get_current_user
from app.services import attachment_store, support_repo, user_repo

CAP = "support"

#: Kho file đính kèm của module (thư mục riêng — nhớ mount volume khi deploy).
store = attachment_store.AttachmentStore("support-files")

#: (username, companies|None, side) — `companies=None` nghĩa là Tập đoàn (thấy mọi đơn vị).
Scope = tuple[str, list[str] | None, str]


def scope_dep(username: str = Depends(get_current_user)) -> Scope:
    user = user_repo.get_user(username)
    if not user or not user.get("is_active", True):
        raise HTTPException(401, "Tài khoản không tồn tại hoặc đã bị khoá")
    if user.get("role") == "leader":
        units = list(user.get("member_units") or [])
        if not units:
            raise HTTPException(403, "Tài khoản chưa được gán đơn vị thành viên — liên hệ quản trị.")
        return username, units, support_repo.UNIT
    assert_cap(username, CAP)
    return username, None, support_repo.HQ


ScopeDep = Annotated[Scope, Depends(scope_dep)]


def assert_may_write(scope: Scope) -> None:
    """Phía Tập đoàn phải đạt mức Sửa mới được gửi/phản hồi; lãnh đạo đơn vị luôn được."""
    username, _, side = scope
    if side == support_repo.HQ:
        assert_cap(username, CAP, LEVEL_EDIT)


def assert_hq(scope: Scope) -> None:
    """Chặn phía đơn vị với các thao tác chỉ Tập đoàn mới làm (gửi thông báo · nhắc lịch)."""
    if scope[2] != support_repo.HQ:
        raise HTTPException(403, "Chỉ dành cho Tập đoàn.")


def can_write(scope: Scope) -> bool:
    """Có được gửi/phản hồi không (để UI ẩn nút thay vì mời bấm rồi báo lỗi)."""
    from app.core.permissions import has_cap
    from app.core.security import user_caps

    username, _, side = scope
    return side != support_repo.HQ or has_cap(user_caps(username), CAP, LEVEL_EDIT)


def display_name(username: str) -> str:
    """Tên hiển thị của người gửi (họ tên nếu có, không thì username)."""
    user = user_repo.get_user(username) or {}
    return user.get("full_name") or username
