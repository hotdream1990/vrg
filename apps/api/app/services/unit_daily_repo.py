"""Repository báo cáo tiêu thụ–tồn kho theo ngày (unit_daily_report) + chỉ tiêu kế hoạch thu mua.

2 loại báo cáo ('purchase' / 'consumption'), số liệu jsonb theo (ngày, đơn vị). Đơn vị tự nhập
của mình; chuyên viên có quyền `unit_daily` xem/sửa mọi đơn vị — realtime theo mốc updated_at.

Khối 3 (`stock_signed_undelivered`, đã ký HĐ chưa giao) KHÔNG nằm trong payload — xem `contracts_on`.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import text

from app.core.db import ensure_schema, session_scope
from app.core.market_meta import PURCHASE_SOURCE_UNIT as UNIT_SRC
from app.services import audit_repo, unit_daily_fields

#: 'purchase' | 'consumption' → nhãn ghi vào nhật ký (đúng tên biểu mẫu người dùng thấy).
_KIND_LABEL = {"purchase": "Thu mua", "consumption": "Tiêu thụ – tồn kho"}

_UPSERT = text("""
    INSERT INTO unit_daily_report (as_of, company, kind, payload, updated_by, updated_at)
    VALUES (:as_of, :company, :kind, CAST(:payload AS jsonb), :updated_by, now())
    ON CONFLICT (as_of, company, kind) DO UPDATE SET
        payload = EXCLUDED.payload, updated_by = EXCLUDED.updated_by, updated_at = now()
""")


def upsert(kind: str, as_of: str, company: str, fields: dict, updated_by: str | None,
           note: str | None = None) -> None:
    """Ghi/ghi đè số liệu 1 đơn vị cho 1 ngày (payload đã lọc theo allowlist)."""
    import json

    clean = unit_daily_fields.clean_fields(kind, fields)
    ensure_schema()
    with session_scope() as db:
        row = db.execute(text("SELECT payload FROM unit_daily_report "
                              "WHERE kind = :k AND as_of = :d AND company = :c"),
                         {"k": kind, "d": as_of, "c": company}).mappings().first()
        before = dict(row["payload"]) if row else None
        # `sales_migrated` là DẤU HỆ THỐNG (script chuyển đổi đặt), không phải ô người dùng nhập.
        # Payload ghi đè toàn bộ nên form không gửi kèm là mất dấu → mảng tiêu thụ cũ sống lại và
        # bị cộng chồng lên hợp đồng. Luôn giữ lại dấu cũ, client không xoá được.
        if before and before.get("sales_migrated") is True:
            clean["sales_migrated"] = True
        db.execute(_UPSERT, {"as_of": as_of, "company": company, "kind": kind,
                             "payload": json.dumps(clean), "updated_by": updated_by})
    audit_repo.log("unit_daily", "update" if before else "create",
                   f"{as_of}|{company}|{kind}", before=before, after=clean,
                   as_of=as_of, company=company,
                   note=note or f"Biểu {_KIND_LABEL.get(kind, kind)}")


def move_day(kind: str, company: str, as_of: str, to_date: str, updated_by: str | None) -> dict:
    """Đổi NGÀY của 1 bản ghi (nhập nhầm ngày) — giữ nguyên nội dung, không nhập lại.

    Ngày đích đã có số liệu thì DỪNG (`ValueError`): 2 ngày là 2 lần khai riêng, gộp vào nhau
    sẽ mất số của một ngày. Biểu Thu mua còn có đơn giá lưu ở kho "Giá mủ nguyên liệu" (bảng khác,
    cũng khoá theo ngày) → chuyển kèm, không thì giá bình quân của báo cáo kỳ lệch.
    Cửa sổ sửa cho CẢ ngày cũ lẫn ngày mới do router ép trước khi gọi.
    """
    from app.services import price_repo

    if to_date == as_of:
        raise ValueError("Ngày mới trùng ngày hiện tại của bản ghi.")
    ensure_schema()
    with session_scope() as db:
        keys = {"k": kind, "c": company}
        src = db.execute(text("SELECT payload FROM unit_daily_report "
                              "WHERE kind = :k AND as_of = :d AND company = :c"),
                         {**keys, "d": as_of}).mappings().first()
        if src is None:
            raise ValueError("Không tìm thấy số liệu của ngày cần đổi.")
        if db.execute(text("SELECT 1 FROM unit_daily_report "
                           "WHERE kind = :k AND as_of = :d AND company = :c"),
                      {**keys, "d": to_date}).scalar() is not None:
            raise ValueError(f"Ngày {to_date} đã có số liệu của {company} — "
                             "xoá số ngày đó hoặc chọn ngày khác.")
        db.execute(text("UPDATE unit_daily_report SET as_of = CAST(:new AS date), "
                        "updated_by = :u, updated_at = now() "
                        "WHERE kind = :k AND as_of = CAST(:d AS date) AND company = :c"),
                   {**keys, "d": as_of, "new": to_date, "u": updated_by})
    audit_repo.log("unit_daily", "update", f"{to_date}|{company}|{kind}",
                   before={"as_of": as_of}, after={"as_of": to_date},
                   as_of=to_date, company=company,
                   note=f"Đổi ngày biểu {_KIND_LABEL.get(kind, kind)}: {as_of} → {to_date}")
    # Đơn giá đi theo bản ghi Thu mua; đơn vị tự khai nên chỉ đụng lớp `vrg_unit` (KHÔNG đụng
    # lớp `vrg` của chuyên viên chốt giá) — xem tách 2 lớp ở market_meta.
    prices = (price_repo.move_purchase_prices(company, as_of, to_date, UNIT_SRC)
              if kind == "purchase" else {"moved": [], "kept": []})
    return {"moved_prices": prices["moved"], "kept_prices": prices["kept"]}


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


#: Khối 3 rỗng (không có hợp đồng nào đang tồn) — dùng làm mặc định, LUÔN new() tránh mutate chung.
def _empty_contracts() -> dict[str, Any]:
    return {"qty": 0.0, "by_grade": {}, "items": []}


def contracts_on(as_of: str, companies: list[str] | None = None) -> dict[str, dict[str, Any]]:
    """{đơn vị: {qty, by_grade, items}} — khối 3 (ĐÃ KÝ HĐ CHƯA GIAO) tại ngày `as_of`.

    Nguồn DUY NHẤT là `sales_contract` (chốt 02/08/2026). Hợp đồng nhập theo cách cũ
    (`unit_stock_contract`) KHÔNG còn được cộng vào: hai cơ chế không cùng khuôn số liệu, trộn vào
    nhau làm khối 3 lộn xộn. Số cũ vẫn tra cứu được ở màn "Hợp đồng cũ" và sẽ vào báo cáo sau khi
    chạy `scripts/migrate-sales-contracts.py` (chuyển sang bảng mới rồi bật cờ `migrated`).
    """
    from app.services import sales_contract_report

    return sales_contract_report.undelivered_on(as_of, companies)


def _attach_contracts(entries: dict[str, dict[str, Any]], as_of: str, create_missing: bool) -> None:
    """Gắn khối 3 (đã ký HĐ chưa giao) — số TỰ TÍNH từ `contracts_on`, KHÔNG lưu trong payload ngày.

    `create_missing`=True: đơn vị chỉ có hợp đồng, chưa nhập số liệu ngày đó vẫn hiện ra (dùng cho
    màn nhập/lưới theo ngày). Shape gắn vào `fields["stock_signed_undelivered"]`:
    `{"qty": float, "by_grade": {chủng loại: số lượng}, "items": [...]}`.
    """
    by_company = contracts_on(as_of)
    for company, data in by_company.items():
        e = entries.get(company)
        if e is None:
            if not create_missing:
                continue
            e = entries[company] = {"fields": {}, "updated_at": None, "updated_by": None}
        e["fields"]["stock_signed_undelivered"] = data
    for e in entries.values():
        e["fields"].setdefault("stock_signed_undelivered", _empty_contracts())


def _attach_contracts_to_list(items: list[dict[str, Any]], kind: str) -> None:
    """Như `_attach_contracts` nhưng cho danh sách bản ghi nhiều ngày (timeline / báo cáo kỳ)."""
    if kind != "consumption" or not items:
        return
    cache: dict[str, dict[str, dict[str, Any]]] = {}
    for it in items:
        d = it["as_of"]
        if d not in cache:
            cache[d] = contracts_on(d)
        it["fields"]["stock_signed_undelivered"] = cache[d].get(it["company"]) or _empty_contracts()


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


def recent(kind: str, date_from: str, companies: list[str] | None = None,
           date_to: str | None = None) -> list[dict[str, Any]]:
    """Các bản ghi CÓ số liệu trong khoảng [date_from, date_to] (date_to=None → tới nay), ngày giảm dần — cho timeline.
    `companies`=None → mọi đơn vị (chuyên viên); có danh sách → chỉ các đơn vị đó (đơn vị thành viên)."""
    ensure_schema()
    where = ["kind = :k", "as_of >= CAST(:d AS date)", "payload <> '{}'::jsonb"]
    params: dict[str, Any] = {"k": kind, "d": date_from}
    if date_to:
        where.append("as_of <= CAST(:dt AS date)")
        params["dt"] = date_to
    with session_scope() as db:
        rows = db.execute(
            text("SELECT as_of, company, payload, updated_at, updated_by FROM unit_daily_report "
                 f"WHERE {' AND '.join(where)} ORDER BY as_of DESC, company"),
            params,
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
            cache[d] = (price_repo.purchase_by_company_on_date(d, "purchase", UNIT_SRC),
                        price_repo.purchase_by_company_on_date(d, "purchase_cup", UNIT_SRC))
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
        latex = price_repo.purchase_by_company_on_date(as_of, "purchase", UNIT_SRC)
        cup = price_repo.purchase_by_company_on_date(as_of, "purchase_cup", UNIT_SRC)
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


def companies_with_purchase_plan(year: int | None = None) -> set[str]:
    """Đơn vị ĐƯỢC GIAO kế hoạch thu mua → mới bật màn Thu mua (chốt 03/08/2026).

    Thay cho cờ bật/tắt thủ công trước đây: chính con số ở màn "Kế hoạch năm" là công tắc.
    Với MỖI đơn vị, lấy **năm gần nhất ≤ năm đang xét mà đơn vị đó có khai số**, rồi bật khi
    số đó **> 0**. Nhờ vậy:
      - Đầu năm chưa ai kịp nhập kế hoạch năm mới → vẫn dùng số năm ngoái, không đơn vị nào
        đột ngột mất màn Thu mua đúng lúc cần nhập số đầu năm.
      - Khai **0** = KHÔNG tổ chức thu mua → tắt hẳn (khác với "chưa khai").
    """
    ensure_schema()
    y = year or date.today().year
    with session_scope() as db:
        rows = db.execute(
            text("SELECT DISTINCT ON (company) company, plan_tonnes FROM unit_purchase_plan "
                 "WHERE year <= :y AND plan_tonnes IS NOT NULL "
                 "ORDER BY company, year DESC"),
            {"y": y},
        ).mappings().all()
    return {r["company"] for r in rows if (r["plan_tonnes"] or 0) > 0}


def year_plan(year: int, companies: list[str] | None = None) -> dict[str, dict[str, float | None]]:
    """Số liệu NĂM (nhập 1 lần, không theo ngày) → {company: {plan_tonnes, signed_lt_tonnes}}.

    `companies`=None → mọi đơn vị (chuyên viên); có danh sách → chỉ các đơn vị đó (đơn vị thành viên).
    """
    ensure_schema()
    with session_scope() as db:
        rows = db.execute(
            text("SELECT company, plan_tonnes, signed_lt_tonnes, carry_lt_tonnes, carry_spot_tonnes, "
                 "       plan_sales_spot_tonnes "
                 "FROM unit_purchase_plan WHERE year = :y"),
            {"y": year},
        ).mappings().all()
    keep = set(companies) if companies is not None else None
    return {r["company"]: {"plan_tonnes": r["plan_tonnes"], "signed_lt_tonnes": r["signed_lt_tonnes"],
                           "carry_lt_tonnes": r["carry_lt_tonnes"], "carry_spot_tonnes": r["carry_spot_tonnes"],
                           "plan_sales_spot_tonnes": r["plan_sales_spot_tonnes"]}
            for r in rows if keep is None or r["company"] in keep}


def set_year_plan(year: int, company: str, plan_tonnes: float | None, signed_lt_tonnes: float | None,
                  carry_lt_tonnes: float | None, carry_spot_tonnes: float | None,
                  plan_sales_spot_tonnes: float | None,
                  updated_by: str | None) -> None:
    """Đặt số liệu năm cho 1 đơn vị (ghi đè các ô; None = xoá ô đó)."""
    ensure_schema()
    after = {"plan_tonnes": plan_tonnes, "signed_lt_tonnes": signed_lt_tonnes,
             "carry_lt_tonnes": carry_lt_tonnes, "carry_spot_tonnes": carry_spot_tonnes,
             "plan_sales_spot_tonnes": plan_sales_spot_tonnes}
    with session_scope() as db:
        before = _plan_snapshot(db, year, company)
        db.execute(
            text("INSERT INTO unit_purchase_plan "
                 "(year, company, plan_tonnes, signed_lt_tonnes, carry_lt_tonnes, carry_spot_tonnes, "
                 " plan_sales_spot_tonnes, "
                 " updated_by, updated_at) "
                 "VALUES (:y, :c, :p, :s, :cl, :cs, :ps, :by, now()) "
                 "ON CONFLICT (year, company) DO UPDATE SET "
                 "plan_tonnes = EXCLUDED.plan_tonnes, signed_lt_tonnes = EXCLUDED.signed_lt_tonnes, "
                 "plan_sales_spot_tonnes = EXCLUDED.plan_sales_spot_tonnes, "
                 "carry_lt_tonnes = EXCLUDED.carry_lt_tonnes, carry_spot_tonnes = EXCLUDED.carry_spot_tonnes, "
                 "updated_by = EXCLUDED.updated_by, updated_at = now()"),
            {"y": year, "c": company, "p": plan_tonnes, "s": signed_lt_tonnes,
             "cl": carry_lt_tonnes, "cs": carry_spot_tonnes, "ps": plan_sales_spot_tonnes,
             "by": updated_by},
        )
    audit_repo.log("unit_plan", "update" if before else "create", f"{year}|{company}",
                   before=before, after=after, company=company, note=f"Số liệu năm {year}")


def set_plan(year: int, company: str, plan_tonnes: float | None, updated_by: str | None) -> None:
    """Đặt/xoá (None) chỉ tiêu kế hoạch thu mua năm cho 1 đơn vị."""
    ensure_schema()
    with session_scope() as db:
        before = _plan_snapshot(db, year, company)
        db.execute(
            text("INSERT INTO unit_purchase_plan (year, company, plan_tonnes, updated_by, updated_at) "
                 "VALUES (:y, :c, :p, :by, now()) "
                 "ON CONFLICT (year, company) DO UPDATE SET "
                 "plan_tonnes = EXCLUDED.plan_tonnes, updated_by = EXCLUDED.updated_by, updated_at = now()"),
            {"y": year, "c": company, "p": plan_tonnes, "by": updated_by},
        )
    audit_repo.log("unit_plan", "update" if before else "create", f"{year}|{company}",
                   before=before, after={**(before or {}), "plan_tonnes": plan_tonnes},
                   company=company, note=f"Kế hoạch thu mua năm {year}")


def _plan_snapshot(db, year: int, company: str) -> dict[str, Any] | None:  # noqa: ANN001
    """Số liệu năm hiện có của 1 đơn vị (None nếu chưa có) — giá trị TRƯỚC khi sửa."""
    row = db.execute(
        text("SELECT plan_tonnes, signed_lt_tonnes, carry_lt_tonnes, carry_spot_tonnes "
             "FROM unit_purchase_plan WHERE year = :y AND company = :c"),
        {"y": year, "c": company}).mappings().first()
    return dict(row) if row else None
