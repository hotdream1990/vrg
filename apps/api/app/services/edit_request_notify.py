"""Email của «Đề nghị sửa số liệu quá khứ».

- Đơn vị GỬI (hoặc cập nhật) đề nghị → mọi tài khoản đang hoạt động có quyền `edit_request`
  (quản trị luôn có). Một email chung cho người duyệt — họ là người của Ban, không lộ chéo đơn vị.
- Ban DUYỆT / TỪ CHỐI → người gửi, kèm ghi chú và (nếu có) lời nhắc chốt số liệu đã bị gỡ.

Email KHÔNG BAO GIỜ làm hỏng nghiệp vụ (xem `mailer`): mọi lỗi ở đây chỉ ghi log.
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.permissions import effective_caps, has_cap
from app.services import mailer, user_repo
from app.services.support_notify import address

logger = logging.getLogger("vrg.edit_request")

_CAP = "edit_request"
_FOOTER = "Email tự động từ Hệ thống Dự báo & Quản trị Giá Cao su — vui lòng không trả lời email này."


def reviewer_recipients() -> list[str]:
    out = []
    for u in user_repo.list_users():
        if u.get("is_active", True) and has_cap(effective_caps(u.get("role", ""), u.get("permissions")), _CAP):
            out.append(address(u))
    return [a for a in out if a]


def _dmy(iso: str) -> str:
    return f"{iso[8:10]}/{iso[5:7]}/{iso[:4]}"


def _link(path: str, fallback: str) -> str:
    base = mailer.base_url()
    return f"Xem tại: {base}{path}" if base else fallback


def _who(req: dict[str, Any]) -> str:
    name = req.get("requested_by_name")
    return f"{name} ({req['requested_by']})" if name else req["requested_by"]


def notify_submitted(req: dict[str, Any], replaced: bool) -> None:
    try:
        to = reviewer_recipients()
        if not to:
            return
        verb = "cập nhật" if replaced else "gửi"
        body = "\n".join([
            f"Đơn vị {req['company']} vừa {verb} đề nghị sửa số liệu, đang chờ duyệt.", "",
            f"Đơn vị: {req['company']}", f"Người gửi: {_who(req)}", f"Nội dung: {req['title']}",
            f"Lý do: {req['reason']}", "",
            _link(f"/duyet-de-nghi-sua/{req['id']}",
                  "Vui lòng đăng nhập hệ thống VRG, vào mục 'Duyệt đề nghị sửa' để xem và duyệt."),
            "", _FOOTER])
        mailer.send_async(to, f"[VRG] Đề nghị sửa số liệu — {req['company']}: {req['title']}", body)
    except Exception as exc:  # noqa: BLE001 - email không được chặn việc gửi đề nghị
        logger.warning("[edit_request] Không gửi được email báo đề nghị #%s: %s", req.get("id"), exc)


def notify_result(req: dict[str, Any]) -> None:
    try:
        user = user_repo.get_user(req["requested_by"])
        to = [address(user)] if user and user.get("is_active", True) else []
        if not [a for a in to if a]:
            return
        approved = req["status"] == "approved"
        lines = [f"Đề nghị sửa số liệu của đơn vị {req['company']} đã được "
                 f"{'DUYỆT' if approved else 'TỪ CHỐI'}.", "",
                 f"Nội dung: {req['title']}", f"Lý do đơn vị gửi: {req['reason']}"]
        if req.get("review_note"):
            lines.append(f"Ghi chú của người duyệt: {req['review_note']}")
        unlocked = req.get("unlocked") or []
        if approved and unlocked and req.get("dates"):
            first = min(req["dates"])   # ngày sửa sớm nhất — phần chốt từ ngày này bị gỡ
            lines.append(f"Chốt số liệu của đơn vị từ ngày {_dmy(first)} đã được gỡ — "
                         "vui lòng rà lại và xác nhận chốt.")
        lines += ["", _link("/de-nghi-sua", "Vui lòng đăng nhập hệ thống VRG, vào mục "
                                            "'Đề nghị sửa số liệu' để xem."), "", _FOOTER]
        verdict = "đã duyệt" if approved else "bị từ chối"
        mailer.send_async(to, f"[VRG] Đề nghị sửa số liệu {verdict}: {req['title']}", "\n".join(lines))
    except Exception as exc:  # noqa: BLE001 - email không được chặn việc duyệt
        logger.warning("[edit_request] Không gửi được email kết quả đề nghị #%s: %s", req.get("id"), exc)
