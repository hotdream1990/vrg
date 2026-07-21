"""Tổng hợp số liệu NGÀY → báo cáo theo KỲ (tuần / tháng / năm / khoảng tự chọn).

Bám mẫu "Chỉ tiêu Biểu (1)-Tuần" (Tiêu thụ–Tồn kho) và "Chỉ tiêu Biểu (2)-Tuần" (Thu mua).
Quy tắc trích xuất theo đúng cột "Công thức" của mẫu:

- **cộng dồn**  → sản lượng, doanh thu: CỘNG các ngày trong kỳ.
- **thời điểm** → tồn kho: lấy bản ghi NGÀY CUỐI CÙNG có số liệu trong kỳ (KHÔNG cộng dồn).
- **bình quân** → giá: bình quân GIA QUYỀN theo sản lượng (không phải trung bình cộng).
- **% kế hoạch** → sản lượng thu mua trong kỳ ÷ kế hoạch năm × 100.

Tiền lưu BASE = đồng (VND); service trả về đúng đơn vị của mẫu (tấn · tỷ đồng · triệu đ/tấn).
"""

from __future__ import annotations

from typing import Any

from app.core.market_meta import UNIT_STOCK_GRADES
from app.services import member_unit_repo, price_repo, unit_daily_repo
from app.services.unit_daily_fields import SALE_TABLES

TY = 1_000_000_000      # 1 tỷ đồng
TRIEU = 1_000_000       # 1 triệu đồng

# Chủng loại tồn kho — tách theo từng loại như bảng Giá sàn (khớp GRADES ở web).
GRADES: list[str] = list(UNIT_STOCK_GRADES)


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


def _latest(entries: list[dict]) -> dict:
    """Bản ghi NGÀY CUỐI trong kỳ (dùng cho chỉ tiêu 'thời điểm' như tồn kho)."""
    return max(entries, key=lambda e: e["as_of"])["fields"] if entries else {}


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

        if f.get("no_purchase") is True:
            no_days += 1
        day_px = prices.get((e["company"], e["as_of"]), {})
        for slot, qty_key in (("latex", "latex_wet"), ("cup", "coagulum")):
            px, qty = _num(day_px.get(slot)), _num(f.get(qty_key))
            if px is not None and qty:
                wsum[slot] += px * qty
                wqty[slot] += qty

    # Tiêu thụ mủ thu mua đã chuyển sang biểu Tiêu thụ → cộng dồn từ bản ghi bên đó.
    for e in sold or []:
        f = e["fields"]
        _add(acc, "consumption", f.get("purchased_sold_qty"))
        _add(acc, "revenue", f.get("purchased_sold_revenue"))
        _add(acc, "finished_qty", f.get("finished_sold_qty"))

    total = acc.get("latex_wet", 0.0) + acc.get("coagulum", 0.0)
    revenue = acc.get("revenue")
    consumption = acc.get("consumption")
    plan_tonnes = _num(plan.get("plan_tonnes"))
    return {
        "latex_wet": acc.get("latex_wet"),
        "coagulum": acc.get("coagulum"),
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
def _consumption_rows(entries: list[dict], plan: dict) -> dict[str, Any]:
    acc: dict[str, float] = {}
    for e in entries:
        f = e["fields"]
        _add(acc, "revenue", f.get("revenue"))
        # Mủ THU MUA (`sales`) và mủ KHAI THÁC (`sales_own`) nhập tách riêng nhưng CỘNG CHUNG vào tổng.
        for key in SALE_TABLES:
            for ln in f.get(key) or []:
                k = f"{ln.get('contract') or 'long_term'}_{ln.get('channel') or 'export'}"
                _add(acc, k, ln.get("qty"))

    lt_e, lt_d = acc.get("long_term_export", 0.0), acc.get("long_term_domestic", 0.0)
    sp_e, sp_d = acc.get("spot_export", 0.0), acc.get("spot_domestic", 0.0)
    total = lt_e + lt_d + sp_e + sp_d
    revenue = acc.get("revenue")

    # Tồn kho = THỜI ĐIỂM: lấy ngày cuối có số liệu trong kỳ (KHÔNG cộng dồn các ngày).
    last = _latest(entries)
    tonnes = lambda rows: sum((_num(r.get("qty")) or 0.0) for r in rows)  # noqa: E731
    not_wh = last.get("stock_not_warehoused") or []      # khối 1: chế biến chưa nhập kho
    wh = last.get("stock_warehoused") or []              # khối 2: đã nhập kho
    signed = last.get("stock_signed_undelivered") or []  # khối 3: đã ký HĐ chưa giao
    # Khối 3 là CAM KẾT giao hàng (ký trước, sản xuất sau) — KHÔNG nằm trong tồn kho thành phẩm,
    # nên KHÔNG trừ ra. Mục 11 = mục 13 = khối 1 + khối 2; mục 12 = khối 3 báo riêng.
    by_grade = {g: 0.0 for g in GRADES}
    for r in [*not_wh, *wh]:
        g = r.get("grade")
        if g in by_grade:
            by_grade[g] += _num(r.get("qty")) or 0.0
    t = lambda v: v or None  # số liệu đã ở TẤN — chỉ đổi 0 thành None  # noqa: E731

    stock_finished = tonnes(not_wh) + tonnes(wh)
    stock_hd = tonnes(signed)          # số độc lập, không trừ khỏi tồn kho
    stock_no_hd = stock_finished
    return {
        "signed_lt_tonnes": _num(plan.get("signed_lt_tonnes")),
        "lt_export": lt_e or None, "lt_domestic": lt_d or None,
        "lt_total": (lt_e + lt_d) or None,
        "spot_export": sp_e or None, "spot_domestic": sp_d or None,
        "spot_total": (sp_e + sp_d) or None,
        "total_consumption": total or None,
        "export_total": (lt_e + sp_e) or None,
        "domestic_total": (lt_d + sp_d) or None,
        "revenue_ty": (revenue / TY) if revenue is not None else None,
        "avg_sell_price": (r / TRIEU if (r := _ratio(revenue, total)) is not None else None),
        "stock_finished": t(stock_finished),
        "stock_finished_hd": t(stock_hd),
        "stock_no_hd": t(stock_no_hd),
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
    prices = (price_repo.purchase_prices_in_range(date_from, date_to)
              if kind == "purchase" else {})
    # Biểu Thu mua cần số tiêu thụ mủ thu mua — nay nằm ở bản ghi 'consumption'.
    sold_by_company = (_by_company(unit_daily_repo.in_range("consumption", date_from, date_to, companies))
                       if kind == "purchase" else {})

    rows = []
    for u in units:
        name = u["name"]
        ent = grouped.get(name, [])
        plan = plans.get(name, {})
        data = (_purchase_rows(ent, prices, plan, sold_by_company.get(name, []))
                if kind == "purchase" else _consumption_rows(ent, plan))
        rows.append({
            "company": name, "region": u.get("region"),
            "days": len(ent), "last_day": max((e["as_of"] for e in ent), default=None),
            **data,
        })
    return {"kind": kind, "date_from": date_from, "date_to": date_to,
            "grades": GRADES, "rows": rows}
