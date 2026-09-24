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

import logging
import threading

from app.core.permissions import effective_caps, has_cap
from app.services import mailer, user_repo

_CAP = "support"
_SUBJECT_PREFIX = "[VRG]"
_EXCERPT = 600  # ký tự nội dung đưa vào email — phần còn lại đọc trên trang

logger = logging.getLogger("vrg.support_notify")

#: 1 thư đã dựng sẵn: (nhãn để ghi log — vd tên đơn vị, (người nhận, tiêu đề, nội dung)).
Mail = tuple[str, tuple[list[str], str, str]]


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


def _body(intro: str, subject: str, content: str, thread_id: int, footer: str,
          extra: str = "") -> str:
    parts = [intro, "", f"Tiêu đề: {subject}", ""]
    text = (content or "").strip()
    if text:
        parts += [text[:_EXCERPT] + ("…" if len(text) > _EXCERPT else ""), ""]
    if extra:  # dòng người gửi bắt buộc phải tới tay người đọc (vd link) — không bị cắt như nội dung
        parts += [extra, ""]
    link = _link(thread_id)
    if link:
        parts += [f"Xem và phản hồi tại: {link}", ""]
    else:
        parts += ["Vui lòng đăng nhập hệ thống VRG, vào mục 'Hỗ trợ & Thông báo' để xem và phản hồi.", ""]
    parts.append(footer)
    return "\n".join(parts)


def unit_email(thread_id: int, company: str, subject: str, content: str, sender_label: str,
               extra: str = "") -> tuple[list[str], str, str] | None:
    """(người nhận, tiêu đề, nội dung) email báo lãnh đạo `company` — None nếu đơn vị chưa có ai nhận.

    Chỉ DỰNG, không gửi: người gọi tự chọn cách gửi (từng thư ở luồng nền, hay gửi tuần tự cả đợt).
    """
    to = unit_recipients(company)
    if not to:
        return None
    return (to, f"{_SUBJECT_PREFIX} {subject}",
            _body(f"Kính gửi {company},\n{sender_label} vừa gửi một thông tin trên hệ thống VRG.",
                  subject, content, thread_id,
                  "Email tự động từ Hệ thống Dự báo & Quản trị Giá Cao su — vui lòng không trả lời email này.",
                  extra))


def notify_to_units(threads: list[tuple[int, str]], subject: str, content: str,
                    sender_label: str, extra: str = "") -> None:
    """Báo cho lãnh đạo các đơn vị: MỘT email cho MỘT đơn vị (link riêng của đơn vị đó)."""
    for thread_id, company in threads:
        mail = unit_email(thread_id, company, subject, content, sender_label, extra)
        if mail:
            mailer.send_async(*mail)


def send_sequential(mails: list[Mail]) -> int:
    """Gửi LẦN LƯỢT từng thư (mỗi lúc một kết nối SMTP) → số thư lỗi. Thư lỗi chỉ ghi log."""
    failed = 0
    for label, (to, subject, body) in mails:
        try:
            ok, err = mailer.send(to, subject, body)
        except Exception as exc:  # noqa: BLE001 - một thư hỏng không được chặn các thư sau
            ok, err = False, str(exc)
        if not ok:
            failed += 1
            logger.warning("[mail] thư cho %s lỗi: %s", label, err)
    return failed


def _in_background(fn, *args) -> None:
    """Chạy ở MỘT luồng nền — người gọi không chờ máy chủ mail. Test thay bằng chạy đồng bộ."""
    threading.Thread(target=fn, args=args, daemon=True, name="support-mail-batch").start()


def send_batch(mails: list[Mail]) -> None:
    """Gửi cả đợt thư (job gửi hàng loạt): TUẦN TỰ trong một luồng nền. Mở hàng chục kết nối SMTP
    cùng lúc (mỗi thư một `send_async`) dễ bị máy chủ mail chặn (421 too many connections)."""
    if mails:
        _in_background(send_sequential, list(mails))


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
