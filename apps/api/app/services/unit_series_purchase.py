"""Chuỗi THU MUA mủ nguyên liệu theo ngày (đơn vị thành viên tự khai).

Hai cách nhìn:
- `purchase_series`        — đơn giá (dải thấp nhất–cao nhất giữa các đơn vị) + tổng sản lượng.
- `purchase_volume_series` — sản lượng chia theo **khu vực** hoặc **đơn vị**.
"""

from __future__ import annotations

from typing import Any

from app.core.market_meta import PURCHASE_SOURCE_UNIT
from app.services import price_repo, unit_daily_repo, unit_report_rows
from app.services.unit_series import days_between, num, series_of

#: Loại mủ nguyên liệu → ô sản lượng trong biểu Thu mua và ô đơn giá nội tệ của đơn vị nước ngoài.
MATERIALS: dict[str, tuple[str, str]] = {
    "latex": ("latex_wet", "price_latex_local"),
    "cup": ("coagulum", "price_cup_local"),
    "lace": ("lace", "price_lace_local"),
}

#: Rổ giá "đơn vị khai đều": đơn vị phải có giá ít nhất ngần này phần số ngày trong kỳ.
#: Dải thấp nhất–cao nhất chỉ có nghĩa khi các ngày được so trên CÙNG một rổ đơn vị. Thực tế mủ chén:
#: 17/27 đơn vị khai đều, 8 đơn vị khai lác đác (<10/30 ngày) — hôm có hôm không, và mấy đơn vị đó
#: lại ở vùng giá thấp nên đáy của biểu đồ nhảy dựng đứng đúng những ngày họ nộp, trông như giá lao dốc.
STEADY_RATIO = 0.8

BASKETS = ("steady", "all")


def _steady_units(prices: dict[str, dict[str, dict[str, float]]], material: str) -> set[str]:
    """Các đơn vị khai giá đều đặn cho loại mủ này.

    Ngưỡng so với **đơn vị chăm nhất trong kỳ**, không so với số ngày lịch: kỳ có cuối tuần / ngày
    nghỉ hay kỳ trải dài trước lúc đơn vị bắt đầu nhập thì không đơn vị nào đạt mốc theo ngày lịch,
    rổ sẽ rỗng và biểu đồ mất sạch dải giá.
    """
    counted: dict[str, int] = {}
    for day in prices.values():
        for company in day.get(material, {}):
            counted[company] = counted.get(company, 0) + 1
    if not counted:
        return set()
    need = max(1, round(max(counted.values()) * STEADY_RATIO))
    return {c for c, n in counted.items() if n >= need}


def _stats(values: list[float]) -> dict[str, Any]:
    """Dải giá của một ngày qua các đơn vị: thấp nhất · cao nhất · trung bình · số đơn vị."""
    if not values:
        return {"min": None, "max": None, "avg": None, "units": 0}
    return {"min": min(values), "max": max(values), "avg": sum(values) / len(values),
            "units": len(values)}


def purchase_series(date_from: str, date_to: str, basket: str = "steady") -> dict[str, Any]:
    """Mủ nước & mủ chén theo ngày: sản lượng thu mua (tấn) + dải đơn giá của các đơn vị.

    Giá lấy lớp **đơn vị tự khai** (`vrg_unit`) để cùng nguồn với sản lượng; đơn vị nước ngoài khai
    giá nội tệ thì quy ra VND bằng tỷ giá của chính bản ghi ngày đó (giống `unit_report_rows`).
    Ngày đơn vị có giá nhưng chưa khai sản lượng vẫn được tính vào dải giá — và ngược lại.

    `basket="steady"` (mặc định): dải giá chỉ tính trên **đơn vị khai đều** → các ngày so được với
    nhau. `basket="all"` lấy mọi đơn vị (đúng hơn về phạm vi, nhưng đáy/đỉnh nhảy theo việc hôm nay
    ai nộp). **Sản lượng LUÔN là tổng của mọi đơn vị** — đó là con số cộng, không phải thống kê phân
    tán, lọc bớt là báo thiếu hàng. Giá trị 0 / không có số bị bỏ qua ở cả hai chế độ.
    """
    px = price_repo.purchase_prices_in_range(date_from, date_to, PURCHASE_SOURCE_UNIT)
    entries = unit_daily_repo.in_range("purchase", date_from, date_to, attach_contracts=False)

    # {ngày: {loại: {đơn vị: giá}}} và {ngày: {loại: {đơn vị: sản lượng}}}
    prices: dict[str, dict[str, dict[str, float]]] = {}
    qty: dict[str, dict[str, dict[str, float]]] = {}
    for (company, day), slot in px.items():
        for material in MATERIALS:
            v = slot.get(material)
            if v:
                prices.setdefault(day, {}).setdefault(material, {})[company] = v

    for e in entries:
        f, day, company = e["fields"], e["as_of"], e["company"]
        fx_local = num(f.get("fx_purchase"))
        for material, (qty_key, local_key) in MATERIALS.items():
            local = num(f.get(local_key))
            if local and fx_local:      # đơn vị nước ngoài: giá nội tệ × tỷ giá → VND
                prices.setdefault(day, {}).setdefault(material, {})[company] = local * fx_local
            q = num(f.get(qty_key))
            if q is not None:
                qty.setdefault(day, {}).setdefault(material, {})[company] = q

    days = days_between(date_from, date_to)
    basket = basket if basket in BASKETS else "steady"
    steady = {m: _steady_units(prices, m) for m in MATERIALS}

    rows = []
    for day in days:
        row: dict[str, Any] = {"as_of": day}
        for material in MATERIALS:
            px_day = prices.get(day, {}).get(material, {})
            if basket == "steady":
                px_day = {c: v for c, v in px_day.items() if c in steady[material]}
            # Sản lượng 0 = có tổ chức mua nhưng không mua được → KHÔNG phải một mức sản lượng,
            # bỏ qua như ô trống (yêu cầu 20/08: chuỗi không được giật vì số rỗng/bằng 0).
            q = {c: v for c, v in qty.get(day, {}).get(material, {}).items() if v}
            total = round(sum(q.values()), 3) if q else None
            stats = _stats(sorted(px_day.values()))
            row[material] = {**stats, "qty": total, "qty_units": len(q)}
        rows.append(row)

    # Ngày không có gì (cả 2 loại mủ đều trống) không được vẽ thành khoảng trống giữa biểu đồ.
    rows = [r for r in rows if any(r[m]["units"] or r[m]["qty"] for m in MATERIALS)]
    return {"date_from": date_from, "date_to": date_to, "basket": basket,
            "basket_units": {m: len(steady[m]) for m in MATERIALS},
            "rows": rows}


# ── Sản lượng thu mua chia theo khu vực / đơn vị ──────────────────────────────
GROUPS = ("region", "company")
NO_REGION = "Chưa gán khu vực"


def purchase_volume_series(date_from: str, date_to: str, material: str = "latex",
                           group_by: str = "region") -> dict[str, Any]:
    """Sản lượng thu mua từng ngày, chia theo khu vực hoặc theo đơn vị (tấn).

    Sản lượng 0 (có tổ chức mua nhưng không mua được) bị bỏ qua như ô trống — cùng quy tắc với
    `purchase_series`, để cột không tụt xuống 0 vì một đơn vị khai "hôm nay không mua được".
    """
    material = material if material in MATERIALS else "latex"
    group_by = group_by if group_by in GROUPS else "region"
    qty_key = MATERIALS[material][0]
    meta = unit_report_rows.unit_meta()
    entries = unit_daily_repo.in_range("purchase", date_from, date_to, attach_contracts=False)

    per_day: dict[str, dict[str, float]] = {}
    totals: dict[str, float] = {}
    for e in entries:
        qty = num(e["fields"].get(qty_key))
        if not qty:
            continue
        company = e["company"]
        key = company if group_by == "company" else (
            (meta.get(company) or {}).get("region") or NO_REGION)
        slot = per_day.setdefault(e["as_of"], {})
        slot[key] = slot.get(key, 0.0) + qty
        totals[key] = totals.get(key, 0.0) + qty

    rows = [{"as_of": day, "total": round(sum(per_day[day].values()), 3),
             "values": {k: round(v, 3) for k, v in per_day[day].items()}}
            for day in days_between(date_from, date_to) if per_day.get(day)]
    return {"date_from": date_from, "date_to": date_to, "material": material,
            "group_by": group_by, "series": series_of(rows, totals), "rows": rows}
