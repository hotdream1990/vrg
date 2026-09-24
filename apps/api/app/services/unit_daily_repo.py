"""Repository báo cáo tiêu thụ–tồn kho theo ngày (unit_daily_report) + chỉ tiêu kế hoạch thu mua.

2 loại báo cáo ('purchase' / 'consumption'), số liệu jsonb theo (ngày, đơn vị). Đơn vị tự nhập
của mình; chuyên viên có quyền `unit_daily` xem/sửa mọi đơn vị — realtime theo mốc updated_at.

Khối 3 (`stock_signed_undelivered`, đã ký HĐ chưa giao) KHÔNG nằm trong payload — xem `contracts_on`.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from sqlalchemy import text

from app.core.db import ensure_schema, session_scope
from app.core.market_meta import PURCHASE_SOURCE_UNIT as UNIT_SRC
from app.services import audit_repo, unit_daily_fields

logger = logging.getLogger("vrg.unit_daily")

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
    _sync_group_inventory(kind, as_of, updated_by)


def _sync_group_inventory(kind: str, as_of: str, by: str | None) -> None:
    """Đơn vị vừa nộp/sửa biểu Tồn kho → cập nhật chuỗi tồn kho TẬP ĐOÀN của tuần tương ứng.

    Chỉ chạy khi chuyên viên đã bật công tắc (`inventory_auto.enabled`). Lỗi ở đây tuyệt đối không
    được làm hỏng thao tác lưu của đơn vị — số của họ đã ghi xong, tổng Tập đoàn tính lại lúc nào
    cũng được (nút "Đồng bộ tuần này" / "Tính lại N tuần" ở màn Tồn kho Tập đoàn).
    """
    if kind != "consumption":
        return
    from app.services import inventory_auto

    try:
        inventory_auto.sync_for_date(as_of, by=by)
    except Exception as exc:                       # noqa: BLE001 - không chặn luồng nhập liệu
        logger.warning("Không cập nhật được tồn kho Tập đoàn cho %s: %s", as_of, exc)


_BULK_NO_PURCHASE = text("""
    INSERT INTO unit_daily_report (as_of, company, kind, payload, updated_by, updated_at)
    VALUES (CAST(:as_of AS date), :company, 'purchase',
            '{"no_purchase": true}'::jsonb, :updated_by, now())
    ON CONFLICT (as_of, company, kind) DO UPDATE
        SET payload = unit_daily_report.payload || '{"no_purchase": true}'::jsonb,
            updated_by = EXCLUDED.updated_by, updated_at = now()
""")


def bulk_mark_no_purchase(cells: list[dict[str, str]], updated_by: str | None,
                          note: str | None = None) -> int:
    """Đánh dấu "không tổ chức thu mua" cho HÀNG LOẠT ô còn trống (admin dọn ngày đơn vị bỏ nộp).

    Router chỉ đưa vào đây các ô ĐANG TRỐNG (`unit_report_status.missing_cells`). Ô đã có bản ghi
    rỗng thì GỘP cờ vào payload cũ (`||`) chứ không ghi đè — bản ghi có thể đang giữ dữ liệu khác,
    ghi đè là mất. Một giao dịch + MỘT dòng nhật ký tóm tắt (ghi từng ô thì một lần
    bấm sinh hàng nghìn dòng, nhật ký không còn đọc được).
    """
    if not cells:
        return 0
    ensure_schema()
    with session_scope() as db:
        db.execute(_BULK_NO_PURCHASE, [{"as_of": c["as_of"], "company": c["company"],
                                        "updated_by": updated_by} for c in cells])
    days = sorted({c["as_of"] for c in cells})
    by_company: dict[str, int] = {}
    for c in cells:
        by_company[c["company"]] = by_company.get(c["company"], 0) + 1
    audit_repo.log("unit_daily", "bulk_no_purchase", f"{days[0]}→{days[-1]}",
                   after={"count": len(cells), "date_from": days[0], "date_to": days[-1],
                          "by_company": by_company},
                   note=note or "Đánh dấu hàng loạt: không tổ chức thu mua")
    return len(cells)


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
    for d in (as_of, to_date):        # số rời khỏi tuần cũ và nhập vào tuần mới → tính lại CẢ HAI
        _sync_group_inventory(kind, d, updated_by)
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
           date_to: str | None = None, limit: int | None = None,
           offset: int = 0) -> dict[str, Any]:
    """Bản ghi CÓ số liệu trong khoảng [date_from, date_to] → `{"entries": [...], "total": n}`.

    Ngày giảm dần. `companies`=None → mọi đơn vị (chuyên viên); có danh sách → chỉ các đơn vị đó.
    Lọc đơn vị làm Ở SQL (trước đây đọc hết mọi đơn vị rồi mới lọc trong Python — tài khoản một
    đơn vị vẫn phải kéo cả Tập đoàn về máy chủ).

    `limit`/`offset` cắt trang: bản ghi Tiêu thụ–Tồn kho mang cả mảng dòng bán + danh sách file nên
    một khoảng 90 ngày đã gần 1 MB, tải hết về trình duyệt là quá nặng cho một bảng vài chục dòng.
    """
    ensure_schema()
    where = ["kind = :k", "as_of >= CAST(:d AS date)", "payload <> '{}'::jsonb"]
    params: dict[str, Any] = {"k": kind, "d": date_from}
    if date_to:
        where.append("as_of <= CAST(:dt AS date)")
        params["dt"] = date_to
    if companies is not None:
        if not companies:
            return {"entries": [], "total": 0}
        where.append("company = ANY(:cs)")
        params["cs"] = list(companies)
    sql = ("SELECT as_of, company, payload, updated_at, updated_by, count(*) OVER () AS total "
           f"FROM unit_daily_report WHERE {' AND '.join(where)} ORDER BY as_of DESC, company")
    if limit:
        sql += " LIMIT :lim OFFSET :off"
        params["lim"], params["off"] = int(limit), max(0, int(offset))
    with session_scope() as db:
        rows = db.execute(text(sql), params).mappings().all()
    out = [{"as_of": str(r["as_of"]), "company": r["company"], "fields": dict(r["payload"] or {}),
            "updated_at": str(r["updated_at"]), "updated_by": r["updated_by"]} for r in rows]
    _attach_contracts_to_list(out, kind)
    return {"entries": out, "total": int(rows[0]["total"]) if rows else 0}


def in_range(kind: str, date_from: str, date_to: str,
             companies: list[str] | None = None,
             attach_contracts: bool = True) -> list[dict[str, Any]]:
    """Các bản ghi CÓ số liệu trong khoảng [date_from, date_to] (ngày tăng dần) — cho báo cáo kỳ.

    `attach_contracts=False` khi người gọi KHÔNG cần khối "đã ký HĐ chưa giao" của TỪNG ngày:
    khối đó phải hỏi hợp đồng một lần cho MỖI ngày trong khoảng (90 ngày = 90 truy vấn), quá đắt
    cho những chỗ chỉ cần cộng vài con số.
    """
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
    if attach_contracts:
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
    """Gắn đơn giá mủ nguyên liệu (link từ 'Giá mủ nguyên liệu') vào từng dòng timeline (chỉ đọc).

    Chỉ áp cho kind='purchase'. Mỗi dòng có `as_of`+`company` → `prices={latex,cup,lace}` đúng ngày
    dòng đó (một khoá cho mỗi loại giá ở `PURCHASE_PRICE_TYPES`).
    """
    if kind != "purchase" or not entries:
        return
    from app.services import price_repo

    cache: dict[str, dict[str, dict[str, float]]] = {}
    for e in entries:
        d = e["as_of"]
        if d not in cache:
            cache[d] = {slot: price_repo.purchase_by_company_on_date(d, pt, UNIT_SRC)
                        for pt, slot in price_repo.PURCHASE_TYPE_SLOT.items()}
        e["prices"] = {slot: by_company.get(e["company"])
                       for slot, by_company in cache[d].items()}


def day_extras(kind: str, as_of: str, units: list[str]) -> dict[str, Any]:
    """Phụ trợ form Thu mua cho 1 ngày: loại tiền mỗi đơn vị + đơn giá thu mua (link, chỉ đọc).

    - currencies: {đơn vị: 'VND'|'LAK'|'KHR'} — ≠VND ⇒ đơn vị nước ngoài, form hiện ô tỷ giá.
    - prices (chỉ kind='purchase'): {đơn vị: {latex, cup, lace}} đơn giá mủ nước/mủ chén/mủ dây
      ĐÚNG NGÀY, lấy từ kho 'Giá mủ nguyên liệu' — hiển thị lại, KHÔNG nhập/lưu trùng.
    """
    from app.services import member_unit_repo, price_repo

    cur = member_unit_repo.currency_by_name()
    fac = member_unit_repo.factory_by_name()
    currencies = {u: cur.get(u, "VND") for u in units}
    factories = {u: fac.get(u, True) for u in units}   # có nhà máy? (Tiêu thụ: ẩn/hiện tồn kho nguyên liệu)
    prices: dict[str, dict[str, float | None]] = {}
    if kind == "purchase":
        by_slot = {slot: price_repo.purchase_by_company_on_date(as_of, pt, UNIT_SRC)
                   for pt, slot in price_repo.PURCHASE_TYPE_SLOT.items()}
        prices = {u: {slot: px.get(u) for slot, px in by_slot.items()} for u in units}
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
            text("SELECT company, plan_exploit_tonnes, plan_tonnes, signed_lt_tonnes, carry_lt_tonnes, "
                 "       carry_spot_tonnes, plan_sales_spot_tonnes, plan_revenue_ty "
                 "FROM unit_purchase_plan WHERE year = :y"),
            {"y": year},
        ).mappings().all()
    keep = set(companies) if companies is not None else None
    return {r["company"]: {"plan_exploit_tonnes": r["plan_exploit_tonnes"],
                           "plan_tonnes": r["plan_tonnes"], "signed_lt_tonnes": r["signed_lt_tonnes"],
                           "carry_lt_tonnes": r["carry_lt_tonnes"], "carry_spot_tonnes": r["carry_spot_tonnes"],
                           "plan_sales_spot_tonnes": r["plan_sales_spot_tonnes"],
                           "plan_revenue_ty": r["plan_revenue_ty"]}
            for r in rows if keep is None or r["company"] in keep}


# Các ô số liệu năm = cột của `unit_purchase_plan` (tên cột lấy từ ĐÂY, không từ input → không chèn SQL).
PLAN_FIELDS: tuple[str, ...] = (
    "plan_exploit_tonnes", "plan_tonnes", "signed_lt_tonnes", "carry_lt_tonnes",
    "carry_spot_tonnes", "plan_sales_spot_tonnes", "plan_revenue_ty",
)


def set_year_plan(year: int, company: str, plan_tonnes: float | None, signed_lt_tonnes: float | None,
                  carry_lt_tonnes: float | None, carry_spot_tonnes: float | None,
                  plan_sales_spot_tonnes: float | None,
                  plan_revenue_ty: float | None,
                  updated_by: str | None, *,
                  plan_exploit_tonnes: float | None = None) -> None:
    """Đặt TRỌN dòng số liệu năm của 1 đơn vị (ghi đè cả 7 ô; None = xoá ô đó).

    Chỉ còn cho script/test dựng số liệu. Endpoint và nhập Excel dùng `save_year_plan` để ô người
    dùng KHÔNG gửi lên thì giữ nguyên.
    """
    save_year_plan(year, company, {
        "plan_exploit_tonnes": plan_exploit_tonnes, "plan_tonnes": plan_tonnes,
        "signed_lt_tonnes": signed_lt_tonnes, "carry_lt_tonnes": carry_lt_tonnes,
        "carry_spot_tonnes": carry_spot_tonnes, "plan_sales_spot_tonnes": plan_sales_spot_tonnes,
        "plan_revenue_ty": plan_revenue_ty}, updated_by)


def save_year_plan(year: int, company: str, values: dict[str, float | None],
                   updated_by: str | None) -> None:
    """Ghi các ô số liệu năm CÓ trong `values` (None = xoá ô đó); ô VẮNG MẶT giữ nguyên số đang lưu.

    Vắng mặt ≠ để trống: body từ bản web cũ (chưa biết ô mới) hay file Excel mẫu cũ (thiếu cột)
    không được âm thầm xoá chỉ tiêu người khác vừa khai (review 24/09/2026).
    """
    cols = [k for k in PLAN_FIELDS if k in values]
    if not cols:
        return
    ensure_schema()
    params = {k: values[k] for k in cols}
    with session_scope() as db:
        before = _plan_snapshot(db, year, company)
        db.execute(
            text("INSERT INTO unit_purchase_plan "
                 f"(year, company, {', '.join(cols)}, updated_by, updated_at) "
                 f"VALUES (:y, :c, {', '.join(':' + k for k in cols)}, :by, now()) "
                 "ON CONFLICT (year, company) DO UPDATE SET "
                 + "".join(f"{k} = EXCLUDED.{k}, " for k in cols)
                 + "updated_by = EXCLUDED.updated_by, updated_at = now()"),
            {"y": year, "c": company, "by": updated_by, **params},
        )
    after = {**(before or dict.fromkeys(PLAN_FIELDS)), **params}
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
        text("SELECT plan_exploit_tonnes, plan_tonnes, signed_lt_tonnes, carry_lt_tonnes, "
             "       carry_spot_tonnes, plan_sales_spot_tonnes, plan_revenue_ty "
             "FROM unit_purchase_plan WHERE year = :y AND company = :c"),
        {"y": year, "c": company}).mappings().first()
    return dict(row) if row else None
