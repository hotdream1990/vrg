"""Repository + bộ phát NHẮC LỊCH (`support_reminder`).

Đến giờ, lịch nhắc phát một thông báo tới các đơn vị đã chọn — đi ĐÚNG đường thông báo thường
(`support_repo.open_threads` + email), nên cũng cách ly theo đơn vị và cũng có chỗ để đơn vị phản hồi.

Vì sao lưu `next_at` (mốc phát kế tiếp) thay vì tính lại từ giờ/thứ: máy chủ tắt hoặc deploy đúng
lúc tới hạn thì mốc vẫn nằm đó, khởi động lại là phát bù ĐÚNG MỘT LẦN rồi mới dời chu kỳ.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import text

from app.core.db import ensure_schema, session_scope
from app.services import audit_repo, support_notify, support_repo

logger = logging.getLogger("vrg.support-reminder")

TZ = ZoneInfo("Asia/Ho_Chi_Minh")
REPEAT_RULES = ("once", "daily", "weekly", "monthly")
SCOPES = ("all", "units", "region")

_COLS = ("id, title, body, files, scope, units, region, repeat_rule, next_at, enabled, "
         "last_sent_at, created_by, created_at, audience")


def now() -> datetime:
    return datetime.now(TZ)


def next_after(current: datetime, rule: str) -> datetime | None:
    """Mốc phát kế tiếp theo chu kỳ. `once` → None (phát xong là tắt lịch)."""
    if rule == "daily":
        return current + timedelta(days=1)
    if rule == "weekly":
        return current + timedelta(days=7)
    if rule == "monthly":
        year, month = current.year + (current.month // 12), current.month % 12 + 1
        day = min(current.day, _days_in_month(year, month))
        return current.replace(year=year, month=month, day=day)
    return None


def _days_in_month(year: int, month: int) -> int:
    """Số ngày của tháng — để lịch ngày 31 không nhảy sang tháng sau khi tháng chỉ có 30 ngày."""
    nxt = datetime(year + (month // 12), month % 12 + 1, 1)
    return (nxt - timedelta(days=1)).day


def _row(row: Any) -> dict[str, Any]:
    d = dict(row)
    d["files"] = list(d.get("files") or [])
    d["units"] = list(d.get("units") or [])
    d["audience"] = support_repo.audience_of(d.get("audience"))
    return d


def list_reminders() -> list[dict[str, Any]]:
    """Mọi lịch nhắc (sắp tới trước) — danh sách ngắn, không cần phân trang."""
    ensure_schema()
    with session_scope() as db:
        rows = db.execute(text(
            f"SELECT {_COLS} FROM support_reminder ORDER BY enabled DESC, next_at")).mappings().all()
        return [_row(r) for r in rows]


def get_reminder(reminder_id: int) -> dict[str, Any] | None:
    ensure_schema()
    with session_scope() as db:
        row = db.execute(text(f"SELECT {_COLS} FROM support_reminder WHERE id = :i"),
                         {"i": reminder_id}).mappings().first()
        return _row(row) if row else None


def create(data: dict[str, Any], by: str) -> dict[str, Any]:
    ensure_schema()
    with session_scope() as db:
        rid = db.execute(
            text("INSERT INTO support_reminder "
                 "(title, body, files, scope, units, region, repeat_rule, next_at, enabled, created_by, "
                 "audience) VALUES (:t, :b, CAST(:f AS jsonb), :s, CAST(:u AS jsonb), :r, :rr, :n, :e, "
                 ":by, CAST(:aud AS jsonb)) "
                 "RETURNING id"),
            _params(data) | {"by": by},
        ).scalar()
    out = get_reminder(int(rid))
    audit_repo.log("support_reminder", "create", str(rid), after=out)
    return out  # type: ignore[return-value]


def update(reminder_id: int, data: dict[str, Any]) -> dict[str, Any] | None:
    before = get_reminder(reminder_id)
    if not before:
        return None
    with session_scope() as db:
        db.execute(
            text("UPDATE support_reminder SET title = :t, body = :b, files = CAST(:f AS jsonb), "
                 "scope = :s, units = CAST(:u AS jsonb), region = :r, repeat_rule = :rr, "
                 "next_at = :n, enabled = :e, audience = CAST(:aud AS jsonb) WHERE id = :i"),
            _params(data) | {"i": reminder_id},
        )
    after = get_reminder(reminder_id)
    audit_repo.log("support_reminder", "update", str(reminder_id), before=before, after=after)
    return after


def delete(reminder_id: int) -> bool:
    before = get_reminder(reminder_id)
    if not before:
        return False
    with session_scope() as db:
        db.execute(text("DELETE FROM support_reminder WHERE id = :i"), {"i": reminder_id})
    audit_repo.log("support_reminder", "delete", str(reminder_id), before=before)
    return True


def _params(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "t": data["title"], "b": data.get("body") or "",
        "f": json.dumps(data.get("files") or []),
        "s": data.get("scope") or "all", "u": json.dumps(data.get("units") or []),
        "r": data.get("region"), "rr": data.get("repeat_rule") or "once",
        "n": data["next_at"], "e": bool(data.get("enabled", True)),
        "aud": json.dumps(support_repo.audience_of(data.get("audience"))),
    }


def targets(reminder: dict[str, Any]) -> list[str]:
    """Các đơn vị nhận thông báo của lịch nhắc này (giải phạm vi tại LÚC PHÁT, không lưu cứng).

    Nhờ giải muộn, đơn vị mới thêm vào khu vực sẽ tự nhận lịch nhắc "theo khu vực" mà không phải
    sửa lại từng lịch.
    """
    from app.services import member_unit_repo

    scope = reminder.get("scope") or "all"
    if scope == "units":
        active = set(member_unit_repo.active_names())
        # KHỬ TRÙNG LẶP: danh sách do client gửi lên có thể lặp tên. `open_threads` tự khử trùng nên
        # số luồng tạo ra sẽ ít hơn số phần tử ở đây, và bước ghép luồng↔đơn vị (để gửi email) sẽ vỡ.
        return [u for u in dict.fromkeys(reminder.get("units") or []) if u in active]
    if scope == "region":
        region = reminder.get("region")
        return [u["name"] for u in member_unit_repo.list_units(include_inactive=False)
                if region and u.get("region") == region]
    return member_unit_repo.active_names()


def dispatch(reminder: dict[str, Any]) -> int:
    """Phát 1 lịch nhắc ngay → trả số đơn vị đã nhận (0 nếu phạm vi rỗng).

    Luồng sinh ra mang đúng nhóm người nhận của lịch (`audience`) — email/push cũng chỉ tới nhóm đó.
    """
    units = targets(reminder)
    if not units:
        logger.warning("[nhắc lịch] '%s' không có đơn vị nào trong phạm vi — bỏ qua", reminder["title"])
        return 0
    audience = support_repo.audience_of(reminder.get("audience"))
    ids = support_repo.open_threads(
        units, support_repo.KIND_REMINDER, reminder["title"], reminder.get("body") or "",
        reminder.get("files"), "system", "Nhắc lịch tự động", support_repo.HQ,
        reminder_id=reminder["id"], audience=audience,
    )
    support_notify.notify_to_units(
        list(zip(ids, units, strict=True)), reminder["title"], reminder.get("body") or "",
        "Ban Thị trường Kinh doanh (nhắc lịch tự động)", audience=audience,
        push_title=support_notify.PUSH_REMINDER,
    )
    return len(ids)


def run_due(ref: datetime | None = None) -> dict[str, Any]:
    """Phát mọi lịch nhắc đã tới hạn rồi dời `next_at` sang chu kỳ sau (lịch `once` thì tắt).

    Chạy định kỳ trong tiến trình API (xem `services/scheduler.py`). An toàn khi gọi lại: lịch nào
    đã dời mốc thì lần sau không tới hạn nữa.
    """
    ensure_schema()
    at = ref or now()
    with session_scope() as db:
        rows = db.execute(
            text(f"SELECT {_COLS} FROM support_reminder "
                 "WHERE enabled AND next_at <= :now ORDER BY next_at"),
            {"now": at},
        ).mappings().all()
    due = [_row(r) for r in rows]
    sent = 0
    for reminder in due:
        try:
            sent += dispatch(reminder)
        except Exception as exc:  # noqa: BLE001 - một lịch lỗi không được chặn các lịch còn lại
            logger.error("[nhắc lịch] '%s' lỗi: %s", reminder["title"], exc)
            continue
        # Dời tới mốc TƯƠNG LAI gần nhất: lịch lỡ nhiều chu kỳ (máy chủ tắt vài ngày) chỉ phát
        # bù MỘT lần rồi về đúng nhịp, chứ không phát dồn mỗi vòng chạy một lần.
        nxt = next_after(reminder["next_at"], reminder["repeat_rule"])
        while nxt is not None and nxt <= at:
            nxt = next_after(nxt, reminder["repeat_rule"])
        with session_scope() as db:
            db.execute(
                text("UPDATE support_reminder SET last_sent_at = :now, next_at = :nxt, "
                     "enabled = :en WHERE id = :i"),
                {"now": at, "nxt": nxt or reminder["next_at"], "en": nxt is not None,
                 "i": reminder["id"]},
            )
    return {"reminders": len(due), "threads": sent}
