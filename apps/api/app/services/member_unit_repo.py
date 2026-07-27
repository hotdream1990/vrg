"""Repository Đơn vị thành viên (member_unit) — danh sách công ty cho Giá mủ nguyên liệu.

Thay cho hardcode: quản lý động (thêm/đổi tên/ẩn/sắp xếp/xoá). Lazy-seed từ VRG_COMPANIES.
Đổi tên đơn vị → chuyển theo MỌI dữ liệu gắn theo tên đơn vị (giá mủ, báo cáo ngày, hợp đồng
tồn kho, kế hoạch năm, nhu cầu thị trường, danh sách đơn vị của tài khoản) — xem `rename_unit`.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from app.core.db import ensure_schema, session_scope
from app.core.market_meta import PURCHASE_SOURCES, VRG_COMPANIES
from app.services import audit_repo

_COLS = ("name, sort_order, is_active, region, country, currency, has_factory, has_purchase_plan")


def _snapshot(name: str) -> dict[str, Any] | None:
    """Ảnh chụp 1 đơn vị (None nếu không có) — giá trị trước/sau cho nhật ký."""
    with session_scope() as db:
        row = db.execute(text(f"SELECT {_COLS} FROM member_unit WHERE name = :n"),
                         {"n": name}).mappings().first()
    return dict(row) if row else None


def _update(name: str, sql: str, params: dict[str, Any], after_name: str | None = None) -> None:
    """Chạy 1 câu UPDATE trên member_unit + ghi nhật ký kèm giá trị trước/sau (DRY cho các setter)."""
    ensure_schema()
    before = _snapshot(name)
    with session_scope() as db:
        db.execute(text(sql), params)
    audit_repo.log("member_unit", "update", after_name or name, before=before,
                   after=_snapshot(after_name or name), company=after_name or name)


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
        res = db.execute(
            text("INSERT INTO member_unit (name, sort_order, is_active) VALUES (:n, :o, true) "
                 "ON CONFLICT (name) DO NOTHING"),
            {"n": name, "o": nxt},
        )
        created = res.rowcount > 0
    if created:  # hàm này được gọi idempotent nhiều nơi — chỉ ghi nhật ký khi THỰC SỰ thêm mới
        audit_repo.log("member_unit", "create", name, after=_snapshot(name), company=name)


# Các bảng số liệu gắn theo TÊN ĐƠN VỊ ở cột `company` — đổi tên đơn vị phải chuyển hết sang tên mới.
_COMPANY_TABLES = ("unit_daily_report", "unit_stock_contract", "unit_purchase_plan", "market_demand")


def rename_unit(old: str, new: str) -> None:
    """Đổi tên đơn vị + chuyển MỌI dữ liệu đang gắn theo tên đơn vị sang tên mới.

    Tên đơn vị chính là khoá liên kết của: giá mủ nguyên liệu (fact_price.grade), báo cáo ngày,
    hợp đồng tồn kho, kế hoạch năm, nhu cầu thị trường và danh sách đơn vị của tài khoản thành viên
    (app_user.member_units). Bỏ sót bảng nào thì dữ liệu bảng đó thành mồ côi — riêng member_units
    còn làm đơn vị **mất quyền vào chính đơn vị của mình** sau khi đổi tên.
    """
    ensure_schema()
    new = new.strip()
    if not new or new == old:
        return
    before = _snapshot(old)
    with session_scope() as db:
        db.execute(text("UPDATE member_unit SET name = :new WHERE name = :old"),
                   {"new": new, "old": old})
        # ĐỦ mọi loại giá gắn theo TÊN ĐƠN VỊ: mủ nước ('purchase') và mủ chén ('purchase_cup'),
        # CẢ HAI lớp — giá chuyên viên chốt (`vrg`) lẫn giá đơn vị tự khai (`vrg_unit`).
        # Bỏ sót lớp/loại nào là lịch sử giá đó thành mồ côi (không còn đơn vị nào khớp tên).
        db.execute(
            text("UPDATE fact_price SET grade = :new WHERE source = ANY(:srcs) "
                 "AND price_type IN ('purchase', 'purchase_cup') AND grade = :old"),
            {"new": new, "old": old, "srcs": list(PURCHASE_SOURCES)},
        )
        for tbl in _COMPANY_TABLES:
            db.execute(text(f"UPDATE {tbl} SET company = :new WHERE company = :old"),
                       {"new": new, "old": old})
        # Tài khoản đơn vị thành viên giữ danh sách đơn vị dạng mảng jsonb → thay đúng phần tử cũ.
        db.execute(
            text("UPDATE app_user SET member_units = ("
                 "  SELECT jsonb_agg(CASE WHEN u = to_jsonb(CAST(:old AS text)) "
                 "                        THEN to_jsonb(CAST(:new AS text)) ELSE u END) "
                 "    FROM jsonb_array_elements(member_units) u) "
                 "WHERE member_units @> jsonb_build_array(CAST(:old AS text))"),
            {"new": new, "old": old},
        )
    audit_repo.log("member_unit", "update", new, before=before, after=_snapshot(new),
                   company=new, note=f"Đổi tên: {old} → {new} (số liệu & tài khoản chuyển theo)")


def set_active(name: str, active: bool) -> None:
    _update(name, "UPDATE member_unit SET is_active = :a WHERE name = :n",
            {"a": active, "n": name})


def set_region(name: str, region: str | None) -> None:
    """Gán đơn vị vào 1 khu vực (region=None để bỏ gán)."""
    _update(name, "UPDATE member_unit SET region = :r WHERE name = :n",
            {"r": (region or "").strip() or None, "n": name})


def set_locale(name: str, country: str | None, currency: str | None) -> None:
    """Gán quốc gia + loại tiền cho đơn vị (mặc định VN/VND nếu trống)."""
    _update(name, "UPDATE member_unit SET country = :c, currency = :cur WHERE name = :n",
            {"c": (country or "").strip().upper() or "VN",
             "cur": (currency or "").strip().upper() or "VND", "n": name})


def currency_by_name(include_inactive: bool = True) -> dict[str, str]:
    """Map tên đơn vị → loại tiền (VND/LAK/KHR) — form Thu mua dùng để ẩn/hiện ô tỷ giá."""
    return {u["name"]: (u.get("currency") or "VND") for u in list_units(include_inactive)}


def set_factory(name: str, has_factory: bool) -> None:
    """Đặt cờ đơn vị có nhà máy chế biến (không có → nhập tồn kho nguyên liệu)."""
    _update(name, "UPDATE member_unit SET has_factory = :f WHERE name = :n",
            {"f": has_factory, "n": name})


def factory_by_name(include_inactive: bool = True) -> dict[str, bool]:
    """Map tên đơn vị → có nhà máy? — form Tiêu thụ dùng để ẩn/hiện ô tồn kho nguyên liệu."""
    return {u["name"]: bool(u.get("has_factory", True)) for u in list_units(include_inactive)}


def set_purchase_plan(name: str, has_purchase_plan: bool) -> None:
    """Đặt cờ đơn vị có giao kế hoạch thu mua năm (bật ⇒ hiện ở màn Kế hoạch năm)."""
    _update(name, "UPDATE member_unit SET has_purchase_plan = :p WHERE name = :n",
            {"p": has_purchase_plan, "n": name})


def reorder(names: list[str]) -> None:
    """Đặt lại sort_order theo thứ tự danh sách truyền vào."""
    ensure_schema()
    before = [u["name"] for u in list_units()]
    with session_scope() as db:
        for i, n in enumerate(names):
            db.execute(text("UPDATE member_unit SET sort_order = :o WHERE name = :n"),
                       {"o": i, "n": n})
    audit_repo.log("member_unit", "update", "(thứ tự hiển thị)",
                   before={"order": before}, after={"order": names},
                   note="Sắp xếp lại danh sách đơn vị")


def delete_unit(name: str) -> bool:
    """Xoá đơn vị khỏi danh sách (giá đã nhập trong fact_price vẫn giữ, chỉ không hiển thị cột)."""
    ensure_schema()
    before = _snapshot(name)
    with session_scope() as db:
        res = db.execute(text("DELETE FROM member_unit WHERE name = :n"), {"n": name})
        deleted = res.rowcount > 0
    if deleted:
        audit_repo.log("member_unit", "delete", name, before=before, company=name)
    return deleted
