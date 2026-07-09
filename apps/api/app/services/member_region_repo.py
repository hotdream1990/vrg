"""Repository Khu vực (member_region) — nhóm các đơn vị thành viên.

Quản lý động (thêm/đổi tên/ẩn/sắp xếp/xoá). Lazy-seed từ VRG_REGIONS.
Đổi tên khu vực → cập nhật luôn member_unit.region để giữ liên kết; xoá → gỡ liên kết (set null).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from app.core.db import ensure_schema, session_scope
from app.core.market_meta import VRG_REGIONS


def _seed_if_empty(db) -> None:
    n = db.execute(text("SELECT count(*) FROM member_region")).scalar() or 0
    if n == 0:
        db.execute(
            text("INSERT INTO member_region (name, sort_order, is_active) "
                 "VALUES (:name, :ord, true) ON CONFLICT (name) DO NOTHING"),
            [{"name": r, "ord": i} for i, r in enumerate(VRG_REGIONS)],
        )


def list_regions(include_inactive: bool = True) -> list[dict[str, Any]]:
    """Danh sách khu vực theo sort_order (seed lần đầu nếu trống)."""
    ensure_schema()
    with session_scope() as db:
        _seed_if_empty(db)
        clause = "" if include_inactive else "WHERE is_active"
        rows = db.execute(text(
            f"SELECT name, sort_order, is_active FROM member_region {clause} "
            "ORDER BY sort_order, name")).mappings().all()
        return [dict(r) for r in rows]


def active_names() -> list[str]:
    """Tên các khu vực đang active (theo thứ tự) — dùng gom giá mủ trong bản tin."""
    return [r["name"] for r in list_regions(include_inactive=False)]


def add_region(name: str) -> None:
    """Thêm khu vực mới (sort_order = max+1)."""
    ensure_schema()
    name = name.strip()
    if not name:
        return
    with session_scope() as db:
        nxt = (db.execute(text("SELECT COALESCE(MAX(sort_order), -1) FROM member_region")).scalar() or -1) + 1
        db.execute(
            text("INSERT INTO member_region (name, sort_order, is_active) VALUES (:n, :o, true) "
                 "ON CONFLICT (name) DO NOTHING"),
            {"n": name, "o": nxt},
        )


def rename_region(old: str, new: str) -> None:
    """Đổi tên khu vực + cập nhật member_unit.region để giữ liên kết đơn vị."""
    ensure_schema()
    new = new.strip()
    if not new or new == old:
        return
    with session_scope() as db:
        db.execute(text("UPDATE member_region SET name = :new WHERE name = :old"),
                   {"new": new, "old": old})
        db.execute(text("UPDATE member_unit SET region = :new WHERE region = :old"),
                   {"new": new, "old": old})


def set_active(name: str, active: bool) -> None:
    ensure_schema()
    with session_scope() as db:
        db.execute(text("UPDATE member_region SET is_active = :a WHERE name = :n"),
                   {"a": active, "n": name})


def reorder(names: list[str]) -> None:
    """Đặt lại sort_order theo thứ tự danh sách truyền vào."""
    ensure_schema()
    with session_scope() as db:
        for i, n in enumerate(names):
            db.execute(text("UPDATE member_region SET sort_order = :o WHERE name = :n"),
                       {"o": i, "n": n})


def delete_region(name: str) -> bool:
    """Xoá khu vực + gỡ liên kết các đơn vị đang thuộc khu vực này (region = null)."""
    ensure_schema()
    with session_scope() as db:
        db.execute(text("UPDATE member_unit SET region = NULL WHERE region = :n"), {"n": name})
        res = db.execute(text("DELETE FROM member_region WHERE name = :n"), {"n": name})
        return res.rowcount > 0
