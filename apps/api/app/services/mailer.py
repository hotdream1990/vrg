"""Gửi email thông báo qua SMTP — cấu hình khai trên trang Cấu hình hệ thống (tab Email).

Nguyên tắc: **email KHÔNG BAO GIỜ làm hỏng nghiệp vụ**. Chưa cấu hình SMTP, sai mật khẩu, máy chủ
mail chết… thì tin vẫn được lưu và đơn vị vẫn đọc được trên trang; lỗi gửi chỉ ghi log. Vì vậy
`send()` không ném ngoại lệ, và lời gọi từ luồng nghiệp vụ đi qua `send_async()` (chạy nền) để
người bấm không phải chờ máy chủ mail.
"""

from __future__ import annotations

import logging
import smtplib
import threading
from email.message import EmailMessage
from email.utils import formataddr

logger = logging.getLogger("vrg.mailer")

# Khoá cấu hình (app_config) — khai ở `config_repo.CONFIG_SPEC` để admin nhập trên UI.
HOST_KEY, PORT_KEY, USER_KEY, PASS_KEY = "SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD"
FROM_KEY, SECURITY_KEY, SENDER_KEY = "SMTP_FROM", "SMTP_SECURITY", "SMTP_SENDER_NAME"
BASE_URL_KEY = "APP_BASE_URL"

_TIMEOUT = 20  # giây — máy chủ mail treo thì bỏ qua, không giữ luồng nền mãi
_DEFAULT_SENDER = "Hệ thống VRG"


def _cfg(key: str, fallback: str = "") -> str:
    from app.services import config_repo

    return (config_repo.get_value(key) or fallback).strip()


def base_url() -> str:
    """Địa chỉ gốc của web (để dựng link trong email). Bỏ dấu `/` cuối cho khỏi thành `//`."""
    return _cfg(BASE_URL_KEY).rstrip("/")


def is_configured() -> bool:
    """Đã khai đủ để gửi được chưa (máy chủ + người gửi)."""
    return bool(_cfg(HOST_KEY) and (_cfg(FROM_KEY) or _cfg(USER_KEY)))


def normalize(address: str | None) -> str:
    """Địa chỉ email hợp lệ tối thiểu (có `@`, không khoảng trắng) — không thì trả rỗng."""
    a = (address or "").strip()
    return a if "@" in a and " " not in a and len(a) <= 254 else ""


def _build(to: list[str], subject: str, body: str, sender: str) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = formataddr((_cfg(SENDER_KEY, _DEFAULT_SENDER), sender))
    msg["To"] = ", ".join(to)
    msg["Subject"] = subject
    msg.set_content(body)
    return msg


def send(to: list[str], subject: str, body: str) -> tuple[bool, str]:
    """Gửi 1 email cho nhiều người nhận. Trả `(thành công, mô tả lỗi)` — KHÔNG ném ngoại lệ."""
    recipients = [a for a in (normalize(x) for x in to) if a]
    if not recipients:
        return False, "Không có địa chỉ email hợp lệ."
    host = _cfg(HOST_KEY)
    if not host:
        return False, "Chưa cấu hình máy chủ SMTP (trang Cấu hình hệ thống → tab Email)."
    sender = _cfg(FROM_KEY) or _cfg(USER_KEY)
    if not normalize(sender):
        return False, "Chưa cấu hình địa chỉ email người gửi (SMTP_FROM)."
    security = (_cfg(SECURITY_KEY, "starttls") or "starttls").lower()
    try:
        port = int(_cfg(PORT_KEY, "0")) or (465 if security == "ssl" else 587)
    except ValueError:
        port = 465 if security == "ssl" else 587

    msg = _build(recipients, subject, body, sender)
    try:
        smtp_class = smtplib.SMTP_SSL if security == "ssl" else smtplib.SMTP
        with smtp_class(host, port, timeout=_TIMEOUT) as smtp:
            if security == "starttls":
                smtp.starttls()
            user, password = _cfg(USER_KEY), _cfg(PASS_KEY)
            if user:
                smtp.login(user, password)
            smtp.send_message(msg)
        logger.info("[mail] Đã gửi '%s' tới %d địa chỉ", subject, len(recipients))
        return True, ""
    except Exception as exc:  # noqa: BLE001 - mail lỗi KHÔNG được làm hỏng nghiệp vụ
        logger.warning("[mail] Gửi thất bại '%s': %s", subject, exc)
        return False, str(exc)


def send_async(to: list[str], subject: str, body: str) -> None:
    """Gửi ở luồng nền — người dùng bấm gửi tin không phải chờ máy chủ mail trả lời."""
    if not to:
        return
    threading.Thread(target=send, args=(list(to), subject, body), daemon=True).start()
