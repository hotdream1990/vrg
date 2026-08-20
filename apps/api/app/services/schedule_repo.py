"""Repository lịch chạy job định kỳ (schedule_job): giờ/phút (+ thứ) + bật/tắt cho mỗi job.

Job metadata (nhãn, mô tả, hàm chạy) nằm ở app/services/scheduler.py; bảng này chỉ giữ lịch.
`day_of_week` rỗng = chạy HẰNG NGÀY; có giá trị ('fri'…) = chỉ chạy đúng thứ đó (job theo tuần).
Admin chỉ sửa giờ/bật-tắt trên UI — chu kỳ theo thứ do code quy định, không cho đổi lung tung.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import text

from app.core.db import ensure_schema, session_scope
from app.services import audit_repo


def seed_defaults(defaults: dict[str, tuple[int, int, str | None]]) -> None:
    """Tạo lịch mặc định cho job chưa có (không đụng giờ/bật-tắt admin đã cấu hình).

    Riêng `day_of_week` LUÔN đồng bộ theo registry: đó là chu kỳ nghiệp vụ của job (job tuần phải
    chạy đúng thứ), không phải tuỳ chọn của admin — job cũ trong DB nhờ vậy cũng được nâng cấp.
    """
    ensure_schema()
    with session_scope() as db:
        for name, (hour, minute, dow) in defaults.items():
            db.execute(
                text("INSERT INTO schedule_job (name, hour, minute, day_of_week) "
                     "VALUES (:n, :h, :m, :d) "
                     "ON CONFLICT (name) DO UPDATE SET day_of_week = EXCLUDED.day_of_week"),
                {"n": name, "h": hour, "m": minute, "d": dow},
            )


def list_jobs() -> list[dict[str, Any]]:
    ensure_schema()
    with session_scope() as db:
        rows = db.execute(text(
            "SELECT name, hour, minute, day_of_week, enabled, updated_at "
            "FROM schedule_job ORDER BY name"))
        return [dict(m) for m in rows.mappings().all()]


def update_job(name: str, hour: int, minute: int, enabled: bool) -> None:
    with session_scope() as db:
        row = db.execute(text("SELECT hour, minute, enabled FROM schedule_job WHERE name = :n"),
                         {"n": name}).mappings().first()
        before = dict(row) if row else None
        db.execute(
            text("UPDATE schedule_job SET hour=:h, minute=:m, enabled=:e, updated_at=now() "
                 "WHERE name=:n"),
            {"n": name, "h": hour, "m": minute, "e": enabled},
        )
    audit_repo.log("schedule", "update", name, before=before,
                   after={"hour": hour, "minute": minute, "enabled": enabled})


def last_run_for(source: str) -> dict[str, Any] | None:
    """Lần chạy gần nhất (meta_crawl_run) ứng với 'sources' của job — cho cột Lần chạy gần nhất."""
    with session_scope() as db:
        row = db.execute(
            text("SELECT started_at, finished_at, status, rows, error FROM meta_crawl_run "
                 "WHERE sources = :s ORDER BY started_at DESC LIMIT 1"),
            {"s": source},
        ).mappings().first()
        return dict(row) if row else None
