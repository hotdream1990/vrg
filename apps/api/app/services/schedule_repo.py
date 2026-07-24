"""Repository lịch chạy job định kỳ (schedule_job): giờ/phút + bật/tắt cho mỗi job.

Job metadata (nhãn, mô tả, hàm chạy) nằm ở app/services/scheduler.py; bảng này chỉ giữ lịch.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import text

from app.core.db import ensure_schema, session_scope
from app.services import audit_repo


def seed_defaults(defaults: dict[str, tuple[int, int]]) -> None:
    """Tạo lịch mặc định cho job chưa có (không đụng job đã cấu hình)."""
    ensure_schema()
    with session_scope() as db:
        for name, (hour, minute) in defaults.items():
            db.execute(
                text("INSERT INTO schedule_job (name, hour, minute) VALUES (:n, :h, :m) "
                     "ON CONFLICT (name) DO NOTHING"),
                {"n": name, "h": hour, "m": minute},
            )


def list_jobs() -> list[dict[str, Any]]:
    ensure_schema()
    with session_scope() as db:
        rows = db.execute(text(
            "SELECT name, hour, minute, enabled, updated_at FROM schedule_job ORDER BY name"))
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
