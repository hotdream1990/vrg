"""Router NHẮC LỊCH — Tập đoàn hẹn giờ, tới hạn hệ thống tự gửi thông báo + email cho đơn vị.

Tách khỏi `support.py` cho gọn file; phạm vi truy cập dùng chung `support_scope` (chỉ phía Tập
đoàn vào được, và phải đạt mức Sửa mới tạo/sửa/gửi). Việc phát tin đi ĐÚNG đường thông báo thường
nên cũng cách ly theo đơn vị — xem `services/support_reminder_repo.dispatch`.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.routers.support_scope import Scope, ScopeDep, assert_hq, assert_may_write
from app.schemas.support import ReminderEdit
from app.services import support_reminder_repo

router = APIRouter(prefix="/api/support/reminders", tags=["support"])


def _hq_writer(scope: Scope) -> None:
    assert_hq(scope)
    assert_may_write(scope)


@router.get("")
def list_reminders(scope: ScopeDep) -> dict:
    """Danh sách lịch nhắc + số đơn vị đang thuộc phạm vi (để soát trước khi tới giờ phát)."""
    assert_hq(scope)
    rows = support_reminder_repo.list_reminders()
    for r in rows:
        r["target_count"] = len(support_reminder_repo.targets(r))
    return {"rows": rows, "now": support_reminder_repo.now().isoformat()}


@router.post("")
def create_reminder(body: ReminderEdit, scope: ScopeDep) -> dict:
    _hq_writer(scope)
    return support_reminder_repo.create(body.model_dump(), scope[0])


@router.put("/{reminder_id}")
def update_reminder(reminder_id: int, body: ReminderEdit, scope: ScopeDep) -> dict:
    _hq_writer(scope)
    out = support_reminder_repo.update(reminder_id, body.model_dump())
    if not out:
        raise HTTPException(404, "Không tìm thấy lịch nhắc.")
    return out


@router.delete("/{reminder_id}")
def delete_reminder(reminder_id: int, scope: ScopeDep) -> dict:
    _hq_writer(scope)
    if not support_reminder_repo.delete(reminder_id):
        raise HTTPException(404, "Không tìm thấy lịch nhắc.")
    return {"ok": True}


@router.post("/{reminder_id}/run")
def run_reminder(reminder_id: int, scope: ScopeDep) -> dict:
    """Phát NGAY một lịch nhắc (nhắc gấp / gửi thử) — KHÔNG đụng tới mốc phát định kỳ."""
    _hq_writer(scope)
    reminder = support_reminder_repo.get_reminder(reminder_id)
    if not reminder:
        raise HTTPException(404, "Không tìm thấy lịch nhắc.")
    return {"ok": True, "threads": support_reminder_repo.dispatch(reminder)}
