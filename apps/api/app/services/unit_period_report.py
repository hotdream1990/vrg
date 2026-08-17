"""Tổng hợp số liệu NGÀY → báo cáo theo KỲ (tuần / tháng / năm / khoảng tự chọn).

Bám mẫu "Chỉ tiêu Biểu (1)-Tuần" (Tiêu thụ–Tồn kho) và "Chỉ tiêu Biểu (2)-Tuần" (Thu mua).
Quy tắc trích xuất theo đúng cột "Công thức" của mẫu:

- **cộng dồn**  → sản lượng, doanh thu: CỘNG các ngày trong kỳ.
- **thời điểm** → tồn kho: lấy bản ghi NGÀY CUỐI CÙNG **có nhập tồn** trong kỳ (KHÔNG cộng dồn),
  trả kèm `stock_as_of` vì ngày này có thể sớm hơn ngày cuối kỳ (đơn vị chưa cập nhật tồn).
- **bình quân** → giá: bình quân GIA QUYỀN theo sản lượng (không phải trung bình cộng).
- **% kế hoạch** → sản lượng thu mua trong kỳ ÷ kế hoạch năm × 100.

Tiền lưu BASE = đồng (VND); service trả về đúng đơn vị của mẫu (tấn · tỷ đồng · triệu đ/tấn).
"""

from __future__ import annotations

from typing import Any

from app.core.market_meta import PURCHASE_SOURCE_UNIT as UNIT_SRC, UNIT_GRADES
from app.services import (
    legacy_data_notice, member_unit_repo, price_repo, sales_contract_report, unit_daily_repo,
    unit_report_rows,
)

TY = 1_000_000_000      # 1 tỷ đồng
TRIEU = 1_000_000       # 1 triệu đồng

# Chủng loại tồn kho — tách theo từng loại như bảng Giá sàn (khớp GRADES ở web).
GRADES: list[str] = list(UNIT_GRADES)


def _num(v: Any) -> float | None:
    try:
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None


def _add(acc: dict[str, float], key: str, v: Any) -> None:
    """Cộng dồn (bỏ qua giá trị trống)."""
    f = _num(v)
    if f is not None:
        acc[key] = acc.get(key, 0.0) + f


def _ratio(num: float | None, den: float | None) -> float | None:
    return None if not den or num is None else num / den


def _by_company(rows: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for r in rows:
        out.setdefault(r["company"], []).append(r)
    return out


def _latest_stock(entries: list[dict]) -> tuple[dict, str | None]:
    """Bản ghi CÓ số liệu tồn gần nhất trong kỳ + ĐÚNG ngày của bản ghi đó.

    KHÔNG lấy bản ghi ngày cuối vô điều kiện: đơn vị thường nhập dòng bán trước và để trống khối
    tồn kho, nên bản ghi cuối kỳ hay có tồn rỗng → báo cáo sẽ hiểu nhầm thành "hết hàng" (tồn = 0)
    thay vì "chưa cập nhật tồn". Dùng chung quy tắc `has_stock` với màn Thống kê tồn kho để hai
    màn luôn khớp; trả kèm ngày để người xem biết số thuộc ngày nào (không mượn số ngày khác).
    """
    with_stock = [e for e in entries if unit_report_rows.has_stock(e["fields"])]
    if not with_stock:
        return {}, None
    last = max(with_stock, key=lambda e: e["as_of"])
    return last["fields"], last["as_of"]


# ── Biểu (2): Thu mua ──────────────────────────────────────────────────────────
def _purchase_rows(entries: list[dict], prices: dict, plan: dict,
                   sold: list[dict] | None = None) -> dict[str, Any]:
    acc: dict[str, float] = {}
    no_days = 0        # số ngày đơn vị KHÔNG tổ chức thu mua (khác ngày có mua nhưng được 0 tấn)
    # bình quân gia quyền: Σ(giá ngày × sản lượng ngày) ÷ Σ(sản lượng ngày)
    wsum = {"latex": 0.0, "cup": 0.0}
    wqty = {"latex": 0.0, "cup": 0.0}
    for e in entries:
        f = e["fields"]
        _add(acc, "latex_wet", f.get("latex_wet"))
        _add(acc, "coagulum", f.get("coagulum"))
        # Thu mua thành phẩm nhập theo CHỦNG LOẠI (bảng nhiều dòng) → cộng số lượng các dòng.
        for ln in f.get("finished") or []:
            _add(acc, "finished_qty", ln.get("qty"))

        if f.get("no_purchase") is True:
            no_days += 1
        day_px = prices.get((e["company"], e["as_of"]), {})
        for slot, qty_key in (("latex", "latex_wet"), ("cup", "coagulum")):
            px, qty = _num(day_px.get(slot)), _num(f.get(qty_key))
            if px and qty:
                wsum[slot] += px * qty
                wqty[slot] += qty

    # Tiêu thụ mủ thu mua đã chuyển sang biểu Tiêu thụ → cộng dồn từ bản ghi bên đó.
    for e in sold or []:
        f = e["fields"]
        _add(acc, "consumption", f.get("purchased_sold_qty"))
        _add(acc, "revenue", f.get("purchased_sold_revenue"))
        _add(acc, "finished_sold_qty", f.get("finished_sold_qty"))

    total = acc.get("latex_wet", 0.0) + acc.get("coagulum", 0.0)
    revenue = acc.get("revenue")
    consumption = acc.get("consumption")
    plan_tonnes = _num(plan.get("plan_tonnes"))
    return {
        "latex_wet": acc.get("latex_wet"),
        "coagulum": acc.get("coagulum"),
        # Thu mua thành phẩm (biểu Thu mua) và tiêu thụ thành phẩm (biểu Tiêu thụ) là HAI chỉ tiêu
        # khác nhau — trước đây cột "thu mua thành phẩm" lấy nhầm số tiêu thụ và không được trả về.
        "finished_qty": acc.get("finished_qty"),
        "finished_sold_qty": acc.get("finished_sold_qty"),
        "total_purchase": total or None,
        "price_latex_avg": _ratio(wsum["latex"], wqty["latex"]),   # đồng/độ TSC
        "price_cup_avg": _ratio(wsum["cup"], wqty["cup"]),
        "plan_tonnes": plan_tonnes,
        "pct_plan": (total / plan_tonnes * 100) if plan_tonnes else None,
        "consumption": consumption,
        "no_purchase_days": no_days or None,
        "revenue_ty": (revenue / TY) if revenue is not None else None,
        # giá bán bình quân = doanh thu ÷ sản lượng tiêu thụ (triệu đ/tấn)
        "avg_sell_price": (r / TRIEU if (r := _ratio(revenue, consumption)) is not None else None),
    }


# ── Biểu (1): Tiêu thụ – Tồn kho ───────────────────────────────────────────────
def _consumption_rows(entries: list[dict], plan: dict, signed: dict[str, Any] | None = None,
                      contract: dict[str, Any] | None = None) -> dict[str, Any]:
    # ── Tiêu thụ CHỈ lấy từ HỢP ĐỒNG (chốt 02/08/2026) ────────────────────────────────────────
    # Hai mảng `sales`/`sales_own` cũ KHÔNG còn được cộng vào báo cáo: chừng nào chưa chạy script
    # chuyển đổi thì chúng chỉ là dữ liệu tra cứu. Trộn hai cơ chế làm số lộn xộn (loại hợp đồng,
    # hình thức, mốc ghi nhận, cách tính doanh thu đều khác nhau) — xem `scripts/migrate-sales-contracts.py`.
    contract = contract or {}
    has_contract = bool(contract.get("deliveries"))
    c_qty = contract.get("qty", 0.0)
    c_revenue = contract.get("revenue")     # None nếu CÓ lần giao thiếu tỷ giá — KHÔNG đoán bằng 0
    by_channel = contract.get("by_channel") or {}
    c_export = by_channel.get("export", 0.0)
    c_domestic = by_channel.get("domestic", 0.0)
    c_internal = by_channel.get("internal", 0.0)
    # Chỉ tiêu dài hạn/chuyến lấy từ `contract_type` của hợp đồng mẹ. Lần giao chưa khai loại nằm
    # ở khoá "" — KHÔNG dồn vào một loại nào, nếu không hai chỉ tiêu này sai.
    by_type = contract.get("by_type") or {}
    lt_total = by_type.get("long_term", 0.0)
    spot_total = by_type.get("spot", 0.0)
    tc = contract.get("by_type_channel") or {}
    lt_e, lt_d = tc.get("long_term|export", 0.0), tc.get("long_term|domestic", 0.0)
    sp_e, sp_d = tc.get("spot|export", 0.0), tc.get("spot|domestic", 0.0)

    total = c_qty
    revenue = None if (has_contract and c_revenue is None) else (c_revenue if has_contract else None)

    # Tồn kho = THỜI ĐIỂM: lấy lần chốt tồn GẦN NHẤT trong kỳ (KHÔNG cộng dồn các ngày).
    last, stock_as_of = _latest_stock(entries)
    tonnes = lambda rows: sum((_num(r.get("qty")) or 0.0) for r in rows)  # noqa: E731
    not_wh = last.get("stock_not_warehoused") or []      # khối 1: chế biến chưa nhập kho
    wh = last.get("stock_warehoused") or []              # khối 2: đã nhập kho
    # Khối 3 (đã ký HĐ) là bản ghi có vòng đời riêng → lấy các HĐ CÒN TỒN ở NGÀY CUỐI KỲ (nguồn
    # `sales_contract` + `unit_stock_contract` cũ, xem `unit_daily_repo.contracts_on`), không phụ
    # thuộc đơn vị có nhập số liệu ngày đó hay không.
    signed = signed or {"qty": 0.0, "by_grade": {}, "items": []}
    # Khối 3 là CAM KẾT giao hàng (ký trước, sản xuất sau) — KHÔNG nằm trong tồn kho thành phẩm:
    # không cộng vào, cũng không trừ ra. Tồn kho thành phẩm = khối 1 + khối 2; khối 3 báo RIÊNG.
    by_grade = {g: 0.0 for g in GRADES}
    for r in [*not_wh, *wh]:
        g = r.get("grade")
        if g in by_grade:
            by_grade[g] += _num(r.get("qty")) or 0.0
    t = lambda v: v or None  # số liệu đã ở TẤN — chỉ đổi 0 thành None  # noqa: E731

    stock_finished = tonnes(not_wh) + tonnes(wh)
    # Phần NẰM TRONG tồn kho thành phẩm đã có hợp đồng nhưng chưa giao → chỉ báo, KHÔNG cộng
    # thêm vào tồn kho (cộng nữa là tính trùng) và cũng không trừ ra.
    stock_hd = signed.get("qty") or 0.0
    return {
        "signed_lt_tonnes": _num(plan.get("signed_lt_tonnes")),
        # Kế hoạch TIÊU THỤ chỉ đặt cho HĐ CHUYẾN → % thực hiện so với tiêu thụ của riêng loại
        # hợp đồng đó, KHÔNG so với tổng tiêu thụ (so tổng là luôn vượt kế hoạch một cách giả tạo).
        "plan_sales_spot_tonnes": _num(plan.get("plan_sales_spot_tonnes")),
        "pct_plan_sales_spot": ((spot_total / p_sales * 100)
                                if (p_sales := _num(plan.get("plan_sales_spot_tonnes"))) else None),
        "lt_export": lt_e or None, "lt_domestic": lt_d or None,
        "lt_total": lt_total or None,
        "spot_export": sp_e or None, "spot_domestic": sp_d or None,
        "spot_total": spot_total or None,
        "total_consumption": total or None,
        "export_total": c_export or None,
        "domestic_total": c_domestic or None,
        "internal_total": c_internal or None,
        "revenue_ty": (revenue / TY) if revenue is not None else None,
        "avg_sell_price": (r / TRIEU if (r := _ratio(revenue, total)) is not None else None),
        # Ngày của ảnh chụp tồn kho — có thể SỚM HƠN ngày cuối kỳ (đơn vị chưa cập nhật tồn).
        "stock_as_of": stock_as_of,
        "stock_finished": t(stock_finished),
        "stock_finished_hd": t(stock_hd),
        "stock_not_warehoused": t(tonnes(not_wh)),
        "stock_warehoused": t(tonnes(wh)),
        "stock_by_grade": {g: t(v) for g, v in by_grade.items()},
        "stock_material": t(_num(last.get("stock_material")) or 0.0),
        "carry_lt_tonnes": _num(plan.get("carry_lt_tonnes")),
        "carry_spot_tonnes": _num(plan.get("carry_spot_tonnes")),
    }


def period_report(kind: str, date_from: str, date_to: str,
                  companies: list[str] | None = None) -> dict[str, Any]:
    """Báo cáo kỳ cho 1 loại biểu — mỗi đơn vị 1 dòng (kèm Khu vực), theo đúng chỉ tiêu của mẫu."""
    year = int(date_to[:4])
    entries = unit_daily_repo.in_range(kind, date_from, date_to, companies)
    grouped = _by_company(entries)
    plans = unit_daily_repo.year_plan(year, companies)
    units = member_unit_repo.list_units(include_inactive=False)
    if companies is not None:
        keep = set(companies)
        units = [u for u in units if u["name"] in keep]
    prices = (price_repo.purchase_prices_in_range(date_from, date_to, UNIT_SRC)
              if kind == "purchase" else {})
    # Biểu Thu mua cần số tiêu thụ mủ thu mua — nay nằm ở bản ghi 'consumption'.
    sold_by_company = (_by_company(unit_daily_repo.in_range("consumption", date_from, date_to, companies))
                       if kind == "purchase" else {})
    # Tồn kho đã ký HĐ = chỉ tiêu THỜI ĐIỂM: các hợp đồng còn tồn ở NGÀY CUỐI KỲ (sales_contract
    # + unit_stock_contract cũ — xem unit_daily_repo.contracts_on).
    signed_at_close = (unit_daily_repo.contracts_on(date_to, companies)
                       if kind == "consumption" else {})
    # Tiêu thụ từ HỢP ĐỒNG — nguồn DUY NHẤT của biểu Tiêu thụ (chốt 02/08/2026). Hai mảng
    # `sales`/`sales_own` cũ KHÔNG được cộng thêm vào, xem `_consumption_rows`.
    contract_consumption = (sales_contract_report.consumption(date_from, date_to, companies)
                            if kind == "consumption" else {})

    rows = []
    for u in units:
        name = u["name"]
        ent = grouped.get(name, [])
        plan = plans.get(name, {})
        data = (_purchase_rows(ent, prices, plan, sold_by_company.get(name, []))
                if kind == "purchase"
                else _consumption_rows(ent, plan, signed_at_close.get(name),
                                       contract_consumption.get(name)))
        rows.append({
            "company": name, "region": u.get("region"),
            "days": len(ent), "last_day": max((e["as_of"] for e in ent), default=None),
            **data,
        })
    # Biểu tiêu thụ chỉ đọc hợp đồng → kỳ nào còn dữ liệu cũ chưa chuyển đổi phải nói rõ, nếu không
    # bảng hiện 0 tấn và người đọc hiểu là đơn vị không bán gì.
    warnings = (legacy_data_notice.warnings(date_from, date_to, companies)
                if kind == "consumption" else [])
    return {"kind": kind, "date_from": date_from, "date_to": date_to,
            "grades": GRADES, "rows": rows, "warnings": warnings}
