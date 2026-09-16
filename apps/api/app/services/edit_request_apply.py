"""Ban xem · DUYỆT · TỪ CHỐI «Đề nghị sửa số liệu quá khứ» — và gỡ chốt số liệu khi duyệt.

Duyệt:
1. Khoá dòng đề nghị (`FOR UPDATE`), kiểm còn `pending` và `expected_updated_at` khớp — đơn vị vừa gửi
   lại (ghi đè nội dung) hoặc người khác vừa duyệt thì 409, người duyệt phải tải lại.
2. Kiểm LẠI quyền của người gửi với đơn vị (tài khoản có thể đã bị khoá / đổi đơn vị sau khi gửi) và
   luật nghiệp vụ; bản ghi đã đổi kể từ lúc gửi mà chưa `accept_changed` ⇒ 409.
3. Ghi thật qua `op.apply` (bỏ qua cửa sổ sửa + chốt, giữ mọi luật nghiệp vụ của repo).
4. Gỡ xác nhận chốt của đơn vị ở mọi đợt chưa huỷ có ngày chốt ≥ ngày sửa sớm nhất — số đã chốt vừa
   đổi nên đơn vị phải rà và xác nhận lại (chốt 15/09/2026). Thao tác không thuộc chốt (`lockable`
   False — nhu cầu thị trường) thì không gỡ gì.

⚠ Các bước ghi KHÔNG chung một transaction: repo nghiệp vụ và gỡ chốt tự mở phiên riêng, chỉ dòng đề
nghị nằm trong phiên khoá. Lỗi giữa chừng ⇒ phần đã ghi KHÔNG được hoàn tác, đề nghị VẪN `pending`;
người duyệt mở lại, xem cột Hiện tại rồi duyệt lại (xác nhận ghi đè) hoặc từ chối.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from fastapi import HTTPException

from app.core import request_ctx
from app.core.db import ensure_schema, session_scope
from app.services import audit_repo, data_lock_repo, edit_request_notify, edit_request_repo, user_repo
from app.services.edit_request_ops import Op, changed_since, get_op, uniq_dates

_NOT_PENDING = "Đề nghị này không còn chờ duyệt."
_NOT_FOUND = "Không tìm thấy đề nghị sửa số liệu."
_STALE = "Đơn vị vừa cập nhật đề nghị này — tải lại để xem nội dung mới."
_CHANGED = ("Số liệu đã thay đổi kể từ lúc đơn vị gửi đề nghị — xem cột Hiện tại rồi xác nhận "
            "ghi đè.")


def unlock_plan(company: str, dates: list[str]) -> list[dict[str, Any]]:
    """Các đợt chốt SẼ bị gỡ nếu duyệt (dùng cho cả xem trước lẫn lúc duyệt thật)."""
    return data_lock_repo.rounds_locked_from(company, min(dates)) if dates else []


def _effective_dates(op: Op, row: dict[str, Any], current: dict | None) -> list[str]:
    """Ngày lúc gửi ∪ ngày tính lại trên bản ghi HIỆN TẠI (vd ngày giao hợp đồng đã đổi sau khi gửi)."""
    return uniq_dates(*(row.get("dates") or []), *op.dates(row["payload"] or {}, current))


def _get(req_id: int) -> dict[str, Any]:
    req = edit_request_repo.get(req_id)
    if not req:
        raise HTTPException(404, _NOT_FOUND)
    return req


def detail(req_id: int) -> dict[str, Any]:
    req = _get(req_id)
    op = get_op(req["op"])
    current = op.snapshot(req["payload"])
    try:
        still: bool | None = bool(op.blocked(req["requested_by"], req["payload"], current))
    except HTTPException:   # người gửi đã bị khoá, bản ghi đã mất… → không kiểm được
        still = None
    locked = data_lock_repo.locked_until(req["company"])
    will = (unlock_plan(req["company"], _effective_dates(op, req, current))
            if req["status"] == "pending" and op.lockable else [])
    return {"request": req, "current": current,
            "changed_since_submit": changed_since(current, req["before"]),
            "still_blocked": still,
            "labels": op.labels([req["payload"], req["before"], current]) if op.labels else {},
            "lock": {"locked_until": str(locked) if locked else None, "will_unlock": will}}


def _requester(username: str) -> dict[str, Any]:
    user = user_repo.get_user(username)
    if not user or not user.get("is_active", True) or user.get("role") != "member":
        raise HTTPException(403, "Tài khoản gửi đề nghị không còn hoạt động hoặc không còn là tài "
                                 "khoản nhập liệu của đơn vị — hãy từ chối đề nghị này.")
    return user


def _assert_reviewable(row: dict[str, Any] | None, expected_updated_at: str | None) -> dict[str, Any]:
    """Dòng đã khoá FOR UPDATE còn chờ duyệt và đúng phiên bản người duyệt đang xem."""
    if not row:
        raise HTTPException(404, _NOT_FOUND)
    if row["status"] != "pending":
        raise HTTPException(409, _NOT_PENDING)
    try:
        seen = datetime.fromisoformat(str(expected_updated_at or "").strip())
    except ValueError:
        seen = None
    if seen is None or seen.tzinfo is None:
        raise HTTPException(400, "Thiếu mốc cập nhật của đề nghị — tải lại trang rồi thử lại.")
    # So theo THỜI ĐIỂM (không so chuỗi). Lệch < 1 ms coi là một: trình duyệt chỉ giữ mili-giây.
    if abs(seen - row["updated_at"]) >= timedelta(milliseconds=1):
        raise HTTPException(409, _STALE)
    return row


def approve(req_id: int, reviewer: str, note: str | None, expected_updated_at: str | None,
            accept_changed: bool = False) -> dict[str, Any]:
    ensure_schema()
    note = (note or "").strip() or None
    with session_scope() as db:
        row = _assert_reviewable(edit_request_repo.lock_for_review(db, req_id), expected_updated_at)
        op, payload = get_op(row["op"]), row["payload"] or {}
        current = op.snapshot(payload)
        company = op.company(payload, current)
        if company != row["company"]:
            raise HTTPException(403, "Bản ghi đã chuyển sang đơn vị khác — hãy từ chối đề nghị này.")
        op.check_scope(_requester(row["requested_by"]), company, payload)
        if op.precheck:
            op.precheck(payload, current)
        if changed_since(current, row["before"]) and not accept_changed:
            raise HTTPException(409, _CHANGED)
        dates = _effective_dates(op, row, current)
        with request_ctx.use_note(f"Duyệt đề nghị sửa #{req_id} của {row['requested_by']}"):
            op.apply(payload, row["requested_by"], company)
            unlocked = unlock_plan(company, dates) if op.lockable else []
            for r in unlocked:
                data_lock_repo.unlock(r["round_id"], company)
        edit_request_repo.mark_reviewed(db, req_id, "approved", reviewer, note, unlocked, dates)
    audit_repo.log("edit_request", "approve", f"#{req_id}", company=company,
                   after={"status": "approved", "note": note, "unlocked": unlocked,
                          "accept_changed": accept_changed})
    req = _get(req_id)
    edit_request_notify.notify_result(req)
    return req


def reject(req_id: int, reviewer: str, note: str | None, expected_updated_at: str | None) -> dict[str, Any]:
    note = (note or "").strip()
    if len(note) < 3:
        raise HTTPException(400, "Nhập ghi chú lý do từ chối (ít nhất 3 ký tự).")
    ensure_schema()
    with session_scope() as db:
        row = _assert_reviewable(edit_request_repo.lock_for_review(db, req_id), expected_updated_at)
        edit_request_repo.mark_reviewed(db, req_id, "rejected", reviewer, note)
    audit_repo.log("edit_request", "reject", f"#{req_id}", company=row["company"],
                   after={"status": "rejected", "note": note})
    req = _get(req_id)
    edit_request_notify.notify_result(req)
    return req
