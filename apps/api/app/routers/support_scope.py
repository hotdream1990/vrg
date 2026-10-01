"""Phạm vi truy cập của hộp thư Hỗ trợ & Thông báo — dùng chung cho các router `support*`.

MỘT bộ endpoint phục vụ cả hai phía; `scope_dep` quyết định tài khoản đang đứng ở bên nào, ĐƯỢC
THẤY những đơn vị nào và thuộc NHÓM NGƯỜI NHẬN nào (server tự ép, KHÔNG tin client gửi lên):
  - `role=leader` / `role=member` → bên `unit`, phạm vi = các đơn vị được gán; nhóm = `leader` với
    lãnh đạo, = các loại nhập liệu với chuyên viên đơn vị (chốt 01/10/2026). Chỉ thấy thẻ có gửi
    cho nhóm của mình — lãnh đạo cũng KHÔNG thấy thẻ không gửi cho lãnh đạo;
  - quyền `support` (admin/chuyên viên) → bên `hq`, phạm vi = mọi đơn vị (`companies=None`).
Vai trò khác (kể cả Lãnh đạo Tập đoàn — không có quyền `support`) đều bị chặn 403.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Annotated, NamedTuple

from fastapi import Depends, HTTPException

from app.core.entry_types import AUDIENCES, clean_audience, user_audiences
from app.core.permissions import LEVEL_EDIT
from app.core.security import assert_cap, get_current_user
from app.services import attachment_store, support_repo, user_repo

CAP = "support"
#: Vai trò đứng ở phía ĐƠN VỊ của hộp thư.
UNIT_SIDE_ROLES = ("leader", "member")

#: Kho file đính kèm của module (thư mục riêng — nhớ mount volume khi deploy).
store = attachment_store.AttachmentStore("support-files")

class Scope(NamedTuple):
    """Ai đang xem hộp thư. `companies=None` / `audiences=None` = Tập đoàn (mọi đơn vị, mọi nhóm)."""

    username: str
    companies: list[str] | None
    side: str
    audiences: list[str] | None


def scope_dep(username: str = Depends(get_current_user)) -> Scope:
    user = user_repo.get_user(username)
    if not user or not user.get("is_active", True):
        raise HTTPException(401, "Tài khoản không tồn tại hoặc đã bị khoá")
    if user.get("role") in UNIT_SIDE_ROLES:
        units = list(user.get("member_units") or [])
        if not units:
            raise HTTPException(403, "Tài khoản chưa được gán đơn vị thành viên — liên hệ quản trị.")
        audiences = [a for a in AUDIENCES if a in user_audiences(user)]
        return Scope(username, units, support_repo.UNIT, audiences)
    assert_cap(username, CAP)
    return Scope(username, None, support_repo.HQ, None)


ScopeDep = Annotated[Scope, Depends(scope_dep)]


def assert_may_write(scope: Scope) -> None:
    """Phía Tập đoàn phải đạt mức Sửa mới được gửi/phản hồi; tài khoản đơn vị luôn được."""
    if scope.side == support_repo.HQ:
        assert_cap(scope.username, CAP, LEVEL_EDIT)


def assert_hq(scope: Scope) -> None:
    """Chặn phía đơn vị với các thao tác chỉ Tập đoàn mới làm (gửi thông báo · nhắc lịch)."""
    if scope.side != support_repo.HQ:
        raise HTTPException(403, "Chỉ dành cho Tập đoàn.")


def require_audience(raw: Iterable[str] | None) -> list[str]:
    """Nhóm người nhận Tập đoàn chọn khi gửi thông báo / đặt lịch nhắc — bắt buộc ít nhất một."""
    audience = clean_audience(raw)
    if not audience:
        raise HTTPException(400, "Chọn ít nhất một nhóm người nhận.")
    return audience


def assert_may_set_status(scope: Scope, thread: dict, status: str) -> None:
    """Ai được khép / mở lại thẻ nào.

    - Tập đoàn: khép và mở lại mọi thẻ.
    - Đơn vị: chỉ KHÉP được yêu cầu do chính mình gửi lên. Thẻ Tập đoàn gửi xuống (thông báo ·
      nhắc lịch · cảnh báo) cần đơn vị phản hồi kết quả ngay trong thẻ, nên việc khép để Tập đoàn
      làm — 26/09/2026 có 6/63 đơn vị bấm "Đánh dấu đã xong" (tưởng là "đã nhận") rồi mất luôn ô
      phản hồi của thông báo cần trả lời.
    - Mở lại: chỉ Tập đoàn (mỗi thẻ = một trường hợp, việc mới thì đơn vị mở thẻ mới).
    """
    if scope.side == support_repo.HQ:
        return
    if status != "closed":
        raise HTTPException(403, "Chỉ Tập đoàn mở lại được thẻ đã khép — có việc mới, vui lòng "
                                 "gửi yêu cầu mới.")
    if thread.get("kind") != support_repo.KIND_REQUEST:
        raise HTTPException(403, "Thông báo của Tập đoàn do Tập đoàn khép lại. Vui lòng phản hồi "
                                 "kết quả ngay trong thông báo này.")


def can_write(scope: Scope) -> bool:
    """Có được gửi/phản hồi không (để UI ẩn nút thay vì mời bấm rồi báo lỗi)."""
    from app.core.permissions import has_cap
    from app.core.security import user_caps

    return scope.side != support_repo.HQ or has_cap(user_caps(scope.username), CAP, LEVEL_EDIT)


def display_name(username: str) -> str:
    """Tên hiển thị của người gửi (họ tên nếu có, không thì username)."""
    user = user_repo.get_user(username) or {}
    return user.get("full_name") or username
