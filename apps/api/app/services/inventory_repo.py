"""CRUD + chuỗi tồn kho Tập đoàn (fact_inventory) — báo cáo tuần chị Hạnh.

Mỗi tuần 1 dòng: ton_kho (tồn kho thành phẩm) + ton_kho_hd (tồn kho đã có hợp đồng), đơn vị tấn.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import text

from app.core.db import ensure_schema, session_scope


def _row(r) -> dict[str, Any]:
    return {"as_of": str(r[0]), "ton_kho": r[1], "ton_kho_hd": r[2],
            "note": r[3], "source": r[4]}


def series(limit: int | None = None) -> list[dict[str, Any]]:
    """Danh sách tuần, mới nhất trước (cho bảng nhập liệu + chart)."""
    ensure_schema()
    sql = ("SELECT as_of, ton_kho, ton_kho_hd, note, source FROM fact_inventory "
           "ORDER BY as_of DESC")
    if limit:
        sql += f" LIMIT {int(limit)}"
    with session_scope() as db:
        return [_row(r) for r in db.execute(text(sql)).all()]


def upsert(as_of: str, ton_kho: float | None, ton_kho_hd: float | None,
           note: str | None = None, source: str = "manual") -> dict[str, Any]:
    """Thêm/sửa 1 tuần (khóa = as_of)."""
    ensure_schema()
    with session_scope() as db:
        db.execute(text(
            "INSERT INTO fact_inventory (as_of, ton_kho, ton_kho_hd, note, source) "
            "VALUES (:a, :t, :h, :n, :s) "
            "ON CONFLICT (as_of) DO UPDATE SET ton_kho=EXCLUDED.ton_kho, "
            "ton_kho_hd=EXCLUDED.ton_kho_hd, note=EXCLUDED.note, ingested_at=now()"),
            {"a": as_of, "t": ton_kho, "h": ton_kho_hd, "n": note, "s": source})
        r = db.execute(text("SELECT as_of, ton_kho, ton_kho_hd, note, source "
                            "FROM fact_inventory WHERE as_of=:a"), {"a": as_of}).first()
    return _row(r)


def delete(as_of: str) -> bool:
    ensure_schema()
    with session_scope() as db:
        res = db.execute(text("DELETE FROM fact_inventory WHERE as_of=:a"), {"a": as_of})
    return res.rowcount > 0
