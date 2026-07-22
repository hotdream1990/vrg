"""Repository báo cáo tiêu thụ–tồn kho theo ngày (unit_daily_report) + chỉ tiêu kế hoạch thu mua.

2 loại báo cáo ('purchase' / 'consumption'), số liệu jsonb theo (ngày, đơn vị). Đơn vị tự nhập
của mình; chuyên viên có quyền `unit_daily` xem/sửa mọi đơn vị — realtime theo mốc updated_at.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from app.core.db import ensure_schema, session_scope
from app.services import unit_daily_fields

_UPSERT = text("""
    INSERT INTO unit_daily_report (as_of, company, kind, payload, updated_by, updated_at)
    VALUES (:as_of, :company, :kind, CAST(:payload AS jsonb), :updated_by, now())
    ON CONFLICT (as_of, company, kind) DO UPDATE SET
        payload = EXCLUDED.payload, updated_by = EXCLUDED.updated_by, updated_at = now()
""")


def upsert(kind: str, as_of: str, company: str, fields: dict, updated_by: str | None) -> None:
    """Ghi/ghi đè số liệu 1 đơn vị cho 1 ngày (payload đã lọc theo allowlist)."""
    import json

    clean = unit_daily_fields.clean_fields(kind, fields)
    ensure_schema()
    with session_scope() as db:
        db.execute(_UPSERT, {"as_of": as_of, "company": company, "kind": kind,
                             "payload": json.dumps(clean), "updated_by": updated_by})


def has_entry(kind: str, as_of: str, company: str) -> bool:
    """Đã có bản ghi CÓ số liệu cho (ngày, đơn vị, loại) chưa — dùng chống ghi trùng."""
    ensure_schema()
    with session_scope() as db:
        row = db.execute(
            text("SELECT payload FROM unit_daily_report "
                 "WHERE kind = :k AND as_of = :d AND company = :c"),
            {"k": kind, "d": as_of, "c": company},
        ).scalar()
    return bool(row)


def _attach_contracts(entries: dict[str, dict[str, Any]], as_of: str, create_missing: bool) -> None:
    """Gắn khối 3 (tồn kho ĐÃ KÝ HĐ) — số TỰ TÍNH từ bảng hợp đồng, KHÔNG lưu trong payload ngày.

    Hợp đồng nhập 1 lần và tự nằm trong tồn kho từ ngày bắt đầu đến hết ngày trước ngày giao
    (xem `unit_stock_contract_repo`). `create_missing`=True: đơn vị chỉ có hợp đồng, chưa nhập số
    liệu ngày đó vẫn hiện ra (dùng cho màn nhập/lưới theo ngày).
    """
    from app.services import unit_stock_contract_repo

    by_company = unit_stock_contract_repo.active_on(as_of)
    for company, rows in by_company.items():
        e = entries.get(company)
        if e is None:
            if not create_missing:
                continue
            e = entries[company] = {"fields": {}, "updated_at": None, "updated_by": None}
        e["fields"]["stock_signed_undelivered"] = rows
    for e in entries.values():
        e["fields"].setdefault("stock_signed_undelivered", [])


def _attach_contracts_to_list(items: list[dict[str, Any]], kind: str) -> None:
    """Như `_attach_contracts` nhưng cho danh sách bản ghi nhiều ngày (timeline / báo cáo kỳ)."""
    if kind != "consumption" or not items:
        return
    from app.services import unit_stock_contract_repo

    cache: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for it in items:
        d = it["as_of"]
        if d not in cache:
            cache[d] = unit_stock_contract_repo.active_on(d)
        it["fields"]["stock_signed_undelivered"] = cache[d].get(it["company"], [])


def entries_on(kind: str, as_of: str) -> dict[str, dict[str, Any]]:
    """Số liệu mọi đơn vị cho 1 ngày → {company: {fields, updated_at, updated_by}}."""
    ensure_schema()
    with session_scope() as db:
        rows = db.execute(
            text("SELECT company, payload, updated_at, updated_by FROM unit_daily_report "
                 "WHERE kind = :k AND as_of = :d"),
            {"k": kind, "d": as_of},
        ).mappings().all()
    entries = {r["company"]: {"fields": dict(r["payload"] or {}),
                              "updated_at": str(r["updated_at"]), "updated_by": r["updated_by"]}
               for r in rows}
    if kind == "consumption":
        _attach_contracts(entries, as_of, create_missing=True)
    return entries


def recent(kind: str, date_from: str, companies: list[str] | None = None) -> list[dict[str, Any]]:
    """Các bản ghi CÓ số liệu từ ngày `date_from` → nay (ngày giảm dần) — cho timeline.
    `companies`=None → mọi đơn vị (chuyên viên); có danh sách → chỉ các đơn vị đó (đơn vị thành viên)."""
    ensure_schema()
    with session_scope() as db:
        rows = db.execute(
            text("SELECT as_of, company, payload, updated_at, updated_by FROM unit_daily_report "
                 "WHERE kind = :k AND as_of >= :d AND payload <> '{}'::jsonb "
                 "ORDER BY as_of DESC, company"),
            {"k": kind, "d": date_from},
        ).mappings().all()
    keep = set(companies) if companies is not None else None
    out = [{"as_of": str(r["as_of"]), "company": r["company"], "fields": dict(r["payload"] or {}),
            "updated_at": str(r["updated_at"]), "updated_by": r["updated_by"]}
           for r in rows if keep is None or r["company"] in keep]
    _attach_contracts_to_list(out, kind)
    return out


def in_range(kind: str, date_from: str, date_to: str,
             companies: list[str] | None = None) -> list[dict[str, Any]]:
    """Các bản ghi CÓ số liệu trong khoảng [date_from, date_to] (ngày tăng dần) — cho báo cáo kỳ."""
    ensure_schema()
    with session_scope() as db:
        rows = db.execute(
            text("SELECT as_of, company, payload FROM unit_daily_report "
                 "WHERE kind = :k AND as_of BETWEEN CAST(:a AS date) AND CAST(:b AS date) "
                 "AND payload <> '{}'::jsonb ORDER BY as_of, company"),
            {"k": kind, "a": date_from, "b": date_to},
        ).mappings().all()
    keep = set(companies) if companies is not None else None
    out = [{"as_of": str(r["as_of"]), "company": r["company"], "fields": dict(r["payload"] or {})}
           for r in rows if keep is None or r["company"] in keep]
    _attach_contracts_to_list(out, kind)
    return out


def prev_stock(company: str, before: str) -> dict[str, Any] | None:
    """Tồn kho của ngày GẦN NHẤT TRƯỚC `before` cho 1 đơn vị (cho nút 'Lấy tồn ngày trước').

    Tồn kho là chỉ tiêu THỜI ĐIỂM: ngày mới thường gần giống ngày trước, nên cho phép chép sang
    rồi sửa. Chỉ trả 2 khối nhập tay + ô nguyên liệu — KHÔNG kèm dòng bán (tiêu thụ là số phát
    sinh trong ngày, chép sang sẽ thành khai khống) và KHÔNG kèm khối 3 (hợp đồng đã ký tự nối
    sang ngày mới theo vòng đời của nó, chép lại sẽ thành nhân đôi).
    """
    ensure_schema()
    with session_scope() as db:
        row = db.execute(
            text("SELECT as_of, payload FROM unit_daily_report "
                 "WHERE kind = 'consumption' AND company = :c AND as_of < CAST(:d AS date) "
                 "AND payload <> '{}'::jsonb ORDER BY as_of DESC LIMIT 1"),
            {"c": company, "d": before},
        ).mappings().first()
    if not row:
        return None
    f = dict(row["payload"] or {})
    stock = {
        "stock_not_warehoused": f.get("stock_not_warehoused") or [],
        "stock_warehoused": f.get("stock_warehoused") or [],
        "stock_material": f.get("stock_material"),
        "stock_ccy": f.get("stock_ccy"),
    }
    if not any([stock["stock_not_warehoused"], stock["stock_warehoused"],
                stock["stock_material"] is not None]):
        return None
    return {"as_of": str(row["as_of"]), **stock}


def attach_purchase_prices(entries: list[dict[str, Any]], kind: str) -> None:
    """Gắn đơn giá mủ nước/mủ chén (link từ 'Giá mủ nguyên liệu') vào từng dòng timeline (chỉ đọc).

    Chỉ áp cho kind='purchase'. Mỗi dòng có `as_of`+`company` → `prices={latex,cup}` đúng ngày dòng đó.
    """
    if kind != "purchase" or not entries:
        return
    from app.services import price_repo

    cache: dict[str, tuple[dict, dict]] = {}
    for e in entries:
        d = e["as_of"]
        if d not in cache:
            cache[d] = (price_repo.purchase_by_company_on_date(d, "purchase"),
                        price_repo.purchase_by_company_on_date(d, "purchase_cup"))
        latex, cup = cache[d]
        e["prices"] = {"latex": latex.get(e["company"]), "cup": cup.get(e["company"])}


def day_extras(kind: str, as_of: str, units: list[str]) -> dict[str, Any]:
    """Phụ trợ form Thu mua cho 1 ngày: loại tiền mỗi đơn vị + đơn giá thu mua (link, chỉ đọc).

    - currencies: {đơn vị: 'VND'|'LAK'|'KHR'} — ≠VND ⇒ đơn vị nước ngoài, form hiện ô tỷ giá.
    - prices (chỉ kind='purchase'): {đơn vị: {latex, cup}} đơn giá mủ nước/mủ chén ĐÚNG NGÀY
      (đồng/độ TSC), lấy từ kho 'Giá mủ nguyên liệu' — hiển thị lại, KHÔNG nhập/lưu trùng.
    """
    from app.services import member_unit_repo, price_repo

    cur = member_unit_repo.currency_by_name()
    fac = member_unit_repo.factory_by_name()
    currencies = {u: cur.get(u, "VND") for u in units}
    factories = {u: fac.get(u, True) for u in units}   # có nhà máy? (Tiêu thụ: ẩn/hiện tồn kho nguyên liệu)
    prices: dict[str, dict[str, float | None]] = {}
    if kind == "purchase":
        latex = price_repo.purchase_by_company_on_date(as_of, "purchase")
        cup = price_repo.purchase_by_company_on_date(as_of, "purchase_cup")
        prices = {u: {"latex": latex.get(u), "cup": cup.get(u)} for u in units}
    return {"currencies": currencies, "factories": factories, "prices": prices}


# ── Chỉ tiêu kế hoạch thu mua theo năm (tính % kế hoạch) ──
def plans_for_year(year: int) -> dict[str, float]:
    """{company: plan_tonnes} cho 1 năm (bỏ đơn vị chưa cấu hình)."""
    ensure_schema()
    with session_scope() as db:
        rows = db.execute(
            text("SELECT company, plan_tonnes FROM unit_purchase_plan WHERE year = :y"),
            {"y": year},
        ).mappings().all()
    return {r["company"]: r["plan_tonnes"] for r in rows if r["plan_tonnes"] is not None}


def year_plan(year: int, companies: list[str] | None = None) -> dict[str, dict[str, float | None]]:
    """Số liệu NĂM (nhập 1 lần, không theo ngày) → {company: {plan_tonnes, signed_lt_tonnes}}.

    `companies`=None → mọi đơn vị (chuyên viên); có danh sách → chỉ các đơn vị đó (đơn vị thành viên).
    """
    ensure_schema()
    with session_scope() as db:
        rows = db.execute(
            text("SELECT company, plan_tonnes, signed_lt_tonnes, carry_lt_tonnes, carry_spot_tonnes "
                 "FROM unit_purchase_plan WHERE year = :y"),
            {"y": year},
        ).mappings().all()
    keep = set(companies) if companies is not None else None
    return {r["company"]: {"plan_tonnes": r["plan_tonnes"], "signed_lt_tonnes": r["signed_lt_tonnes"],
                           "carry_lt_tonnes": r["carry_lt_tonnes"], "carry_spot_tonnes": r["carry_spot_tonnes"]}
            for r in rows if keep is None or r["company"] in keep}


def set_year_plan(year: int, company: str, plan_tonnes: float | None, signed_lt_tonnes: float | None,
                  carry_lt_tonnes: float | None, carry_spot_tonnes: float | None,
                  updated_by: str | None) -> None:
    """Đặt số liệu năm cho 1 đơn vị (ghi đè các ô; None = xoá ô đó)."""
    ensure_schema()
    with session_scope() as db:
        db.execute(
            text("INSERT INTO unit_purchase_plan "
                 "(year, company, plan_tonnes, signed_lt_tonnes, carry_lt_tonnes, carry_spot_tonnes, "
                 " updated_by, updated_at) "
                 "VALUES (:y, :c, :p, :s, :cl, :cs, :by, now()) "
                 "ON CONFLICT (year, company) DO UPDATE SET "
                 "plan_tonnes = EXCLUDED.plan_tonnes, signed_lt_tonnes = EXCLUDED.signed_lt_tonnes, "
                 "carry_lt_tonnes = EXCLUDED.carry_lt_tonnes, carry_spot_tonnes = EXCLUDED.carry_spot_tonnes, "
                 "updated_by = EXCLUDED.updated_by, updated_at = now()"),
            {"y": year, "c": company, "p": plan_tonnes, "s": signed_lt_tonnes,
             "cl": carry_lt_tonnes, "cs": carry_spot_tonnes, "by": updated_by},
        )


def set_plan(year: int, company: str, plan_tonnes: float | None, updated_by: str | None) -> None:
    """Đặt/xoá (None) chỉ tiêu kế hoạch thu mua năm cho 1 đơn vị."""
    ensure_schema()
    with session_scope() as db:
        db.execute(
            text("INSERT INTO unit_purchase_plan (year, company, plan_tonnes, updated_by, updated_at) "
                 "VALUES (:y, :c, :p, :by, now()) "
                 "ON CONFLICT (year, company) DO UPDATE SET "
                 "plan_tonnes = EXCLUDED.plan_tonnes, updated_by = EXCLUDED.updated_by, updated_at = now()"),
            {"y": year, "c": company, "p": plan_tonnes, "by": updated_by},
        )
