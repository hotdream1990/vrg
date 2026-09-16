"""Gửi email báo có tin mới trong hộp thư Hỗ trợ & Thông báo.

Ai nhận:
- Tin gửi XUỐNG đơn vị (thông báo · nhắc lịch · Tập đoàn phản hồi) → tài khoản **lãnh đạo đơn vị**
  (`role=leader`) đang hoạt động, được gán đúng đơn vị đó. Mỗi đơn vị một email riêng kèm link
  riêng — không bao giờ để hai đơn vị chung một email (lộ danh sách người nhận là lộ chéo).
- Tin gửi LÊN Tập đoàn (đơn vị mở yêu cầu · đơn vị phản hồi) → quản trị + chuyên viên có quyền
  `support`.

Địa chỉ email lấy ở cột `app_user.email`; bỏ trống thì dùng chính `username` nếu username là email
(các tài khoản đơn vị đang được cấp theo địa chỉ email — xem tài liệu cấp tài khoản).
"""

from __future__ import annotations

from app.core.permissions import effective_caps, has_cap
from app.services import mailer, user_repo

_CAP = "support"
_SUBJECT_PREFIX = "[VRG]"
_EXCERPT = 600  # ký tự nội dung đưa vào email — phần còn lại đọc trên trang


def address(user: dict) -> str:
    """Email nhận thông báo của 1 tài khoản (ưu tiên cột email, sau đó tới username dạng email)."""
    return mailer.normalize(user.get("email")) or mailer.normalize(user.get("username"))


def _active(users: list[dict]) -> list[dict]:
    return [u for u in users if u.get("is_active", True)]


def unit_recipients(company: str) -> list[str]:
    """Email của lãnh đạo đơn vị `company` (rỗng nếu đơn vị chưa có tài khoản lãnh đạo)."""
    out = [
        address(u) for u in _active(user_repo.list_users())
        if u.get("role") == "leader" and company in (u.get("member_units") or [])
    ]
    return [a for a in out if a]


def hq_recipients() -> list[str]:
    """Email của quản trị + chuyên viên được cấp quyền `support`."""
    out = []
    for u in _active(user_repo.list_users()):
        caps = effective_caps(u.get("role", ""), u.get("permissions"))
        if has_cap(caps, _CAP):
            out.append(address(u))
    return [a for a in out if a]


def _link(thread_id: int) -> str:
    """Link vào đúng luồng trên web. Chưa khai `APP_BASE_URL` thì email không có link."""
    base = mailer.base_url()
    return f"{base}/ho-tro/{thread_id}" if base else ""


def _body(intro: str, subject: str, content: str, thread_id: int, footer: str) -> str:
    parts = [intro, "", f"Tiêu đề: {subject}", ""]
    text = (content or "").strip()
    if text:
        parts += [text[:_EXCERPT] + ("…" if len(text) > _EXCERPT else ""), ""]
    link = _link(thread_id)
    if link:
        parts += [f"Xem và phản hồi tại: {link}", ""]
    else:
        parts += ["Vui lòng đăng nhập hệ thống VRG, vào mục 'Hỗ trợ & Thông báo' để xem và phản hồi.", ""]
    parts.append(footer)
    return "\n".join(parts)


def notify_to_units(threads: list[tuple[int, str]], subject: str, content: str,
                    sender_label: str) -> None:
    """Báo cho lãnh đạo các đơn vị: MỘT email cho MỘT đơn vị (link riêng của đơn vị đó)."""
    for thread_id, company in threads:
        to = unit_recipients(company)
        if not to:
            continue
        mailer.send_async(
            to, f"{_SUBJECT_PREFIX} {subject}",
            _body(f"Kính gửi {company},\n{sender_label} vừa gửi một thông tin trên hệ thống VRG.",
                  subject, content, thread_id,
                  "Email tự động từ Hệ thống Dự báo & Quản trị Giá Cao su — vui lòng không trả lời email này."),
        )


def notify_to_hq(thread_id: int, company: str, subject: str, content: str, actor: str) -> None:
    """Báo cho Tập đoàn: đơn vị vừa gửi yêu cầu hoặc vừa phản hồi."""
    to = hq_recipients()
    if not to:
        return
    mailer.send_async(
        to, f"{_SUBJECT_PREFIX} {company} — {subject}",
        _body(f"Đơn vị {company} ({actor}) vừa gửi thông tin trên hệ thống VRG.",
              subject, content, thread_id,
              "Email tự động từ Hệ thống Dự báo & Quản trị Giá Cao su."),
    )
