"""Repository Đơn vị thành viên (member_unit) — danh sách công ty cho Giá mủ nguyên liệu.

Thay cho hardcode: quản lý động (thêm/đổi tên/ẩn/sắp xếp/xoá). Lazy-seed từ VRG_COMPANIES.
Đổi tên đơn vị → migrate luôn fact_price.grade (source=vrg) để không mất lịch sử giá.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from app.core.db import ensure_schema, session_scope
from app.core.market_meta import VRG_COMPANIES


def _seed_if_empty(db) -> None:
    n = db.execute(text("SELECT count(*) FROM member_unit")).scalar() or 0
    if n == 0:
        db.execute(
            text("INSERT INTO member_unit (name, sort_order, is_active) "
                 "VALUES (:name, :ord, true) ON CONFLICT (name) DO NOTHING"),
            [{"name": c, "ord": i} for i, c in enumerate(VRG_COMPANIES)],
        )


def list_units(include_inactive: bool = True) -> list[dict[str, Any]]:
    """Danh sách đơn vị theo sort_order (seed lần đầu nếu trống)."""
    ensure_schema()
    with session_scope() as db:
        _seed_if_empty(db)
        clause = "" if include_inactive else "WHERE is_active"
        rows = db.execute(text(
            "SELECT name, sort_order, is_active, region, country, currency, has_factory, "
            f"has_purchase_plan FROM member_unit {clause} "
            "ORDER BY sort_order, name")).mappings().all()
        return [dict(r) for r in rows]


def active_names() -> list[str]:
    """Tên các đơn vị đang active (theo thứ tự) — dùng cho purchase_sheet + bản tin."""
    return [u["name"] for u in list_units(include_inactive=False)]


def plan_names() -> list[str]:
    """Tên các đơn vị active CÓ giao kế hoạch thu mua (theo thứ tự) — dùng cho màn Kế hoạch năm."""
    return [u["name"] for u in list_units(include_inactive=False) if u.get("has_purchase_plan", True)]


def add_unit(name: str) -> None:
    """Thêm đơn vị mới (sort_order = max+1)."""
    ensure_schema()
    name = name.strip()
    if not name:
        return
    with session_scope() as db:
        nxt = (db.execute(text("SELECT COALESCE(MAX(sort_order), -1) FROM member_unit")).scalar() or -1) + 1
        db.execute(
            text("INSERT INTO member_unit (name, sort_order, is_active) VALUES (:n, :o, true) "
                 "ON CONFLICT (name) DO NOTHING"),
            {"n": name, "o": nxt},
        )


def rename_unit(old: str, new: str) -> None:
    """Đổi tên đơn vị + migrate fact_price.grade (source=vrg) để giữ lịch sử giá."""
    ensure_schema()
    new = new.strip()
    if not new or new == old:
        return
    with session_scope() as db:
        db.execute(text("UPDATE member_unit SET name = :new WHERE name = :old"),
                   {"new": new, "old": old})
        # ĐỦ mọi loại giá gắn theo TÊN ĐƠN VỊ: mủ nước ('purchase') và mủ chén ('purchase_cup').
        # Bỏ sót loại nào là lịch sử giá của loại đó thành mồ côi (không còn đơn vị nào khớp tên).
        db.execute(
            text("UPDATE fact_price SET grade = :new WHERE source = 'vrg' "
                 "AND price_type IN ('purchase', 'purchase_cup') AND grade = :old"),
            {"new": new, "old": old},
        )


def set_active(name: str, active: bool) -> None:
    ensure_schema()
    with session_scope() as db:
        db.execute(text("UPDATE member_unit SET is_active = :a WHERE name = :n"),
                   {"a": active, "n": name})


def set_region(name: str, region: str | None) -> None:
    """Gán đơn vị vào 1 khu vực (region=None để bỏ gán)."""
    ensure_schema()
    region = (region or "").strip() or None
    with session_scope() as db:
        db.execute(text("UPDATE member_unit SET region = :r WHERE name = :n"),
                   {"r": region, "n": name})


def set_locale(name: str, country: str | None, currency: str | None) -> None:
    """Gán quốc gia + loại tiền cho đơn vị (mặc định VN/VND nếu trống)."""
    ensure_schema()
    country = (country or "").strip().upper() or "VN"
    currency = (currency or "").strip().upper() or "VND"
    with session_scope() as db:
        db.execute(text("UPDATE member_unit SET country = :c, currency = :cur WHERE name = :n"),
                   {"c": country, "cur": currency, "n": name})


def currency_by_name(include_inactive: bool = True) -> dict[str, str]:
    """Map tên đơn vị → loại tiền (VND/LAK/KHR) — form Thu mua dùng để ẩn/hiện ô tỷ giá."""
    return {u["name"]: (u.get("currency") or "VND") for u in list_units(include_inactive)}


def set_factory(name: str, has_factory: bool) -> None:
    """Đặt cờ đơn vị có nhà máy chế biến (không có → nhập tồn kho nguyên liệu)."""
    ensure_schema()
    with session_scope() as db:
        db.execute(text("UPDATE member_unit SET has_factory = :f WHERE name = :n"),
                   {"f": has_factory, "n": name})


def factory_by_name(include_inactive: bool = True) -> dict[str, bool]:
    """Map tên đơn vị → có nhà máy? — form Tiêu thụ dùng để ẩn/hiện ô tồn kho nguyên liệu."""
    return {u["name"]: bool(u.get("has_factory", True)) for u in list_units(include_inactive)}


def set_purchase_plan(name: str, has_purchase_plan: bool) -> None:
    """Đặt cờ đơn vị có giao kế hoạch thu mua năm (bật ⇒ hiện ở màn Kế hoạch năm)."""
    ensure_schema()
    with session_scope() as db:
        db.execute(text("UPDATE member_unit SET has_purchase_plan = :p WHERE name = :n"),
                   {"p": has_purchase_plan, "n": name})


def reorder(names: list[str]) -> None:
    """Đặt lại sort_order theo thứ tự danh sách truyền vào."""
    ensure_schema()
    with session_scope() as db:
        for i, n in enumerate(names):
            db.execute(text("UPDATE member_unit SET sort_order = :o WHERE name = :n"),
                       {"o": i, "n": n})


def delete_unit(name: str) -> bool:
    """Xoá đơn vị khỏi danh sách (giá đã nhập trong fact_price vẫn giữ, chỉ không hiển thị cột)."""
    ensure_schema()
    with session_scope() as db:
        res = db.execute(text("DELETE FROM member_unit WHERE name = :n"), {"n": name})
        return res.rowcount > 0
