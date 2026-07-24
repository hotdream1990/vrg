"""Repository bản nháp bản tin (bulletin_draft) — lưu bền phần TEXT admin sửa, theo report_date.

Giá (sàn/physical/floor/mủ) luôn dựng lại từ DB khi mở bản tin; bảng này chỉ giữ overrides
admin (exchange_summary, physical_summary, market_analysis, source_urls) để không mất khi
restart và để hiện trong danh sách "Nháp".
"""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text

from app.core.db import ensure_schema, session_scope
from app.services import audit_repo


def save_draft(report_date: str, payload: dict[str, Any]) -> None:
    """Lưu/ghi đè overrides của 1 ngày (report_date dạng YYYY-MM-DD)."""
    ensure_schema()
    with session_scope() as db:
        row = db.execute(text("SELECT payload FROM bulletin_draft "
                              "WHERE report_date = CAST(:d AS date)"),
                         {"d": report_date}).mappings().first()
        before = dict(row["payload"]) if row else None
        db.execute(
            text("INSERT INTO bulletin_draft (report_date, payload, updated_at) "
                 "VALUES (CAST(:d AS date), CAST(:p AS jsonb), now()) "
                 "ON CONFLICT (report_date) DO UPDATE SET payload = EXCLUDED.payload, updated_at = now()"),
            {"d": report_date, "p": json.dumps(payload, ensure_ascii=False)},
        )
    # Soạn bản tin lưu nhiều lần liên tiếp → gộp trong 10 phút cho nhật ký gọn.
    audit_repo.log("bulletin_daily", "update" if before else "create", report_date,
                   before=before, after=payload, as_of=report_date, coalesce=True)


def get_overrides(report_date: str) -> dict[str, Any] | None:
    """Overrides đã lưu cho 1 ngày (None nếu chưa có nháp). psycopg trả jsonb → dict sẵn."""
    ensure_schema()
    with session_scope() as db:
        row = db.execute(
            text("SELECT payload FROM bulletin_draft WHERE report_date = CAST(:d AS date)"),
            {"d": report_date},
        ).mappings().first()
        return dict(row["payload"]) if row else None


def recent_market_analysis(before_date: str, limit: int = 5) -> list[dict[str, Any]]:
    """Các đoạn 'market_analysis' ĐÃ LƯU (chuyên viên biên tập) của tối đa `limit` ngày
    TRƯỚC before_date — mới nhất trước — để AI tham chiếu văn phong/tông giọng khi viết
    mục IV. Bỏ ngày chưa có market_analysis. before_date dạng YYYY-MM-DD."""
    ensure_schema()
    with session_scope() as db:
        rows = db.execute(
            text("SELECT report_date, payload FROM bulletin_draft "
                 "WHERE report_date < CAST(:d AS date) "
                 "AND jsonb_typeof(payload -> 'market_analysis') = 'array' "
                 "AND jsonb_array_length(payload -> 'market_analysis') > 0 "
                 "ORDER BY report_date DESC LIMIT :n"),
            {"d": before_date, "n": limit},
        ).mappings().all()
    out: list[dict[str, Any]] = []
    for r in rows:
        paras = [p.strip() for p in (dict(r["payload"]).get("market_analysis") or [])
                 if isinstance(p, str) and p.strip()]
        if paras:
            out.append({"report_date": str(r["report_date"]), "paragraphs": paras})
    return out


def list_drafts() -> list[dict[str, Any]]:
    """Danh sách nháp đã lưu (mới nhất trước) cho trang danh sách bản tin."""
    ensure_schema()
    with session_scope() as db:
        rows = db.execute(text(
            "SELECT report_date, updated_at FROM bulletin_draft ORDER BY report_date DESC"
        )).mappings().all()
        return [
            {"report_date": str(r["report_date"]),
             "updated_at": r["updated_at"].isoformat(timespec="seconds")}
            for r in rows
        ]


def delete_draft(report_date: str) -> int:
    """Xoá nháp 1 ngày. Trả số dòng đã xoá."""
    before = get_overrides(report_date)
    with session_scope() as db:
        removed = db.execute(
            text("DELETE FROM bulletin_draft WHERE report_date = CAST(:d AS date)"),
            {"d": report_date},
        ).rowcount
    if removed:
        audit_repo.log("bulletin_daily", "delete", report_date, before=before, as_of=report_date)
    return removed
