"""Báo có tin mới trong hộp thư Hỗ trợ & Thông báo — email + Web Push (thông báo trình duyệt).

Ai nhận:
- Tin gửi XUỐNG đơn vị (thông báo · nhắc lịch · cảnh báo · Tập đoàn phản hồi) → tài khoản đang hoạt
  động, được gán đúng đơn vị đó và thuộc NHÓM NGƯỜI NHẬN của thẻ (`audience`): lãnh đạo nếu có
  `leader`, chuyên viên nhập liệu nếu loại của họ có trong `audience`. Mỗi đơn vị một email riêng
  kèm link riêng — không bao giờ để hai đơn vị chung một email (lộ danh sách người nhận là lộ chéo).
- Tin gửi LÊN Tập đoàn (đơn vị mở yêu cầu · đơn vị phản hồi) → quản trị + chuyên viên có quyền
  `support`.

Web Push đi ĐỘC LẬP với email: chưa cấu hình SMTP hoặc tài khoản không có địa chỉ email thì vẫn báo
được lên trình duyệt. Không bao giờ báo cho chính người vừa nhắn.

Địa chỉ email lấy ở cột `app_user.email`; bỏ trống thì dùng chính `username` nếu username là email
(các tài khoản đơn vị đang được cấp theo địa chỉ email — xem tài liệu cấp tài khoản).
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Iterable

from app.core.entry_types import DEFAULT_AUDIENCE, clean_audience, user_audiences
from app.core.permissions import effective_caps, has_cap
from app.services import mailer, user_repo, web_push

_CAP = "support"
_SUBJECT_PREFIX = "[VRG]"
_EXCERPT = 600  # ký tự nội dung đưa vào email — phần còn lại đọc trên trang
_PUSH_EXCERPT = 200  # thông báo trình duyệt chỉ hiện vài dòng

#: Tiêu đề thông báo trình duyệt.
PUSH_ANNOUNCE = "Thông báo mới từ Tập đoàn"
PUSH_REMINDER = "Nhắc lịch từ Tập đoàn"
PUSH_ALERT = "Cảnh báo số liệu sau giờ chốt"
PUSH_HQ_REPLY = "Tập đoàn phản hồi"

logger = logging.getLogger("vrg.support_notify")

#: 1 thư đã dựng sẵn: (nhãn để ghi log — vd tên đơn vị, (người nhận, tiêu đề, nội dung)).
Mail = tuple[str, tuple[list[str], str, str]]


def address(user: dict) -> str:
    """Email nhận thông báo của 1 tài khoản (ưu tiên cột email, sau đó tới username dạng email)."""
    return mailer.normalize(user.get("email")) or mailer.normalize(user.get("username"))


def _active(users: list[dict]) -> list[dict]:
    return [u for u in users if u.get("is_active", True)]


def _emails(users: list[dict]) -> list[str]:
    return list(dict.fromkeys(a for a in (address(u) for u in users) if a))


def unit_users(company: str, audience: Iterable[str] | None = None,
               users: list[dict] | None = None) -> list[dict]:
    """Tài khoản phía đơn vị `company` thuộc nhóm người nhận `audience` (mặc định: lãnh đạo).

    `users` = danh sách tài khoản đã tải sẵn (gửi nhiều đơn vị một lượt thì chỉ đọc bảng một lần).
    """
    aud = set(clean_audience(audience) or DEFAULT_AUDIENCE)
    return [u for u in _active(user_repo.list_users() if users is None else users)
            if company in (u.get("member_units") or []) and user_audiences(u) & aud]


def unit_recipients(company: str, audience: Iterable[str] | None = None) -> list[str]:
    """Email người nhận phía đơn vị `company` theo `audience` (rỗng nếu chưa có ai nhận)."""
    return _emails(unit_users(company, audience))


def hq_users() -> list[dict]:
    """Quản trị + chuyên viên được cấp quyền `support` (đang hoạt động)."""
    return [u for u in _active(user_repo.list_users())
            if has_cap(effective_caps(u.get("role", ""), u.get("permissions")), _CAP)]


def hq_recipients() -> list[str]:
    """Email của quản trị + chuyên viên được cấp quyền `support`."""
    return _emails(hq_users())


def push_item(usernames: Iterable[str], title: str, subject: str, content: str, url: str,
              tag: str | None = None, exclude: str | None = None) -> web_push.PushItem | None:
    """Dựng MỘT lượt Web Push (bỏ người vừa nhắn) — None nếu không còn ai nhận."""
    names = [u for u in dict.fromkeys(usernames) if u and u != exclude]
    if not names:
        return None
    text = " ".join(" — ".join(x for x in (subject.strip(), (content or "").strip()) if x).split())
    body = text if len(text) <= _PUSH_EXCERPT else text[:_PUSH_EXCERPT - 1] + "…"
    return (names, title, body, url, tag)


def push_batch(items: Iterable[web_push.PushItem | None]) -> None:
    """Gửi cả đợt Web Push trong MỘT luồng nền (gửi ~80 đơn vị không đẻ ~80 luồng). Lỗi chỉ ghi log."""
    batch = [it for it in items if it]
    if not batch:
        return
    try:
        web_push.send_batch_async(batch)
    except Exception as exc:  # noqa: BLE001 - thông báo trình duyệt không được chặn nghiệp vụ
        logger.warning("[push] lỗi gửi '%s': %s", batch[0][1], exc)


def push(usernames: Iterable[str], title: str, subject: str, content: str, url: str,
         tag: str | None = None, exclude: str | None = None) -> None:
    """Web Push tới các tài khoản (bỏ người vừa nhắn). Lỗi chỉ ghi log — tin đã lưu."""
    push_batch([push_item(usernames, title, subject, content, url, tag, exclude)])


def thread_url(thread_id: int) -> str:
    """Đường dẫn (tương đối) mở đúng luồng trên web — dùng cho thông báo trình duyệt."""
    return f"/ho-tro/{thread_id}"


def unit_push(thread_id: int, company: str, subject: str, content: str, *,
              audience: Iterable[str] | None = None, title: str = PUSH_ANNOUNCE,
              exclude: str | None = None, users: list[dict] | None = None) -> web_push.PushItem | None:
    """Lượt Web Push tới đúng nhóm người nhận của MỘT luồng (một đơn vị) — gom rồi `push_batch`."""
    names = [u["username"] for u in unit_users(company, audience, users)]
    return push_item(names, title, subject, content, thread_url(thread_id), f"support-{thread_id}",
                     exclude)


def _link(thread_id: int) -> str:
    """Link vào đúng luồng trên web. Chưa khai `APP_BASE_URL` thì email không có link."""
    base = mailer.base_url()
    return f"{base}{thread_url(thread_id)}" if base else ""


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
               extra: str = "", audience: Iterable[str] | None = None,
               users: list[dict] | None = None) -> tuple[list[str], str, str] | None:
    """(người nhận, tiêu đề, nội dung) email báo nhóm `audience` (mặc định lãnh đạo) của `company`
    — None nếu đơn vị chưa có ai nhận.

    Chỉ DỰNG, không gửi: người gọi tự chọn cách gửi (từng thư ở luồng nền, hay gửi tuần tự cả đợt).
    """
    to = _emails(unit_users(company, audience, users))
    if not to:
        return None
    return (to, f"{_SUBJECT_PREFIX} {subject}",
            _body(f"Kính gửi {company},\n{sender_label} vừa gửi một thông tin trên hệ thống VRG.",
                  subject, content, thread_id,
                  "Email tự động từ Hệ thống Dự báo & Quản trị Giá Cao su — vui lòng không trả lời email này.",
                  extra))


def notify_to_units(threads: list[tuple[int, str]], subject: str, content: str,
                    sender_label: str, extra: str = "", *, audience: Iterable[str] | None = None,
                    push_title: str = PUSH_ANNOUNCE, actor: str | None = None) -> None:
    """Báo cho nhóm người nhận của từng đơn vị: MỘT email cho MỘT đơn vị (link riêng của đơn vị
    đó) + Web Push tới từng tài khoản trong nhóm (cả đợt gửi trong một luồng nền)."""
    users = user_repo.list_users()
    pushes = []
    for thread_id, company in threads:
        mail = unit_email(thread_id, company, subject, content, sender_label, extra, audience, users)
        if mail:
            mailer.send_async(*mail)
        pushes.append(unit_push(thread_id, company, subject, content, audience=audience,
                                title=push_title, exclude=actor, users=users))
    push_batch(pushes)


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


def notify_to_hq(thread_id: int, company: str, subject: str, content: str, actor: str, *,
                 is_new: bool = False, author: str | None = None) -> None:
    """Báo cho Tập đoàn: đơn vị vừa gửi yêu cầu (`is_new`) hoặc vừa phản hồi."""
    users = hq_users()
    to = _emails(users)
    if to:
        mailer.send_async(
            to, f"{_SUBJECT_PREFIX} {company} — {subject}",
            _body(f"Đơn vị {company} ({actor}) vừa gửi thông tin trên hệ thống VRG.",
                  subject, content, thread_id,
                  "Email tự động từ Hệ thống Dự báo & Quản trị Giá Cao su."),
        )
    title = f"Đơn vị {company} {'gửi yêu cầu' if is_new else 'phản hồi'}"
    push([u["username"] for u in users], title, subject, content, thread_url(thread_id),
         f"support-{thread_id}", author)
