"""Chuỗi số liệu THEO NGÀY lấy thẳng từ biểu đơn vị thành viên đã nhập.

Phục vụ Command Center / Bản tin biến động — nơi cần *diễn biến* chứ không phải bảng lọc như màn
"Thống kê số liệu".

Ở đây là chuỗi **thu mua**: sản lượng + đơn giá mủ nước/mủ chén từng ngày. Chuỗi **tồn kho**
(cơ cấu hợp đồng · chủng loại · khu vực) nằm ở `unit_series_stock.py` và dùng chung khung cửa sổ
ngày (`window`, `days_between`) của module này.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from app.core.market_meta import PURCHASE_SOURCE_UNIT
from app.services import price_repo, unit_daily_repo

#: Cửa sổ hiển thị mặc định / tối đa (ngày). Chuỗi tồn kho hỏi hợp đồng 1 lần cho MỖI ngày nên
#: cửa sổ phải có trần, không để màn hình kéo theo cả năm.
DEFAULT_WINDOW_DAYS = 60
MAX_WINDOW_DAYS = 180


def days_between(date_from: str, date_to: str) -> list[str]:
    a, b = date.fromisoformat(date_from), date.fromisoformat(date_to)
    return [(a + timedelta(days=i)).isoformat() for i in range((b - a).days + 1)]


def window(date_from: str | None, date_to: str | None, *, start_floor: str | None = None,
           default_days: int = DEFAULT_WINDOW_DAYS) -> tuple[str, str]:
    """Khoảng ngày đã kẹp: mặc định `default_days` ngày gần nhất, trần `MAX_WINDOW_DAYS`."""
    from app.core.edit_window import today

    end = date.fromisoformat(date_to) if date_to else today()
    start = date.fromisoformat(date_from) if date_from else end - timedelta(days=default_days - 1)
    if start_floor:
        start = max(start, date.fromisoformat(start_floor))
    start = max(start, end - timedelta(days=MAX_WINDOW_DAYS - 1))
    if start > end:
        start = end
    return start.isoformat(), end.isoformat()


# ── Thu mua: sản lượng + đơn giá theo ngày ─────────────────────────────────────
def _num(v: Any) -> float | None:
    try:
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None


def _stats(values: list[float]) -> dict[str, Any]:
    """Dải giá của một ngày qua các đơn vị: thấp nhất · cao nhất · trung bình · số đơn vị."""
    if not values:
        return {"min": None, "max": None, "avg": None, "units": 0}
    return {"min": min(values), "max": max(values), "avg": sum(values) / len(values),
            "units": len(values)}


def purchase_series(date_from: str, date_to: str) -> dict[str, Any]:
    """Mủ nước & mủ chén theo ngày: sản lượng thu mua (tấn) + dải đơn giá của các đơn vị.

    Giá lấy lớp **đơn vị tự khai** (`vrg_unit`) để cùng nguồn với sản lượng; đơn vị nước ngoài khai
    giá nội tệ thì quy ra VND bằng tỷ giá của chính bản ghi ngày đó (giống `unit_report_rows`).
    Ngày đơn vị có giá nhưng chưa khai sản lượng vẫn được tính vào dải giá — và ngược lại.
    """
    px = price_repo.purchase_prices_in_range(date_from, date_to, PURCHASE_SOURCE_UNIT)
    entries = unit_daily_repo.in_range("purchase", date_from, date_to, attach_contracts=False)

    # {ngày: {loại: {đơn vị: giá}}} và {ngày: {loại: {đơn vị: sản lượng}}}
    prices: dict[str, dict[str, dict[str, float]]] = {}
    qty: dict[str, dict[str, dict[str, float]]] = {}
    for (company, day), slot in px.items():
        for material in ("latex", "cup"):
            v = slot.get(material)
            if v:
                prices.setdefault(day, {}).setdefault(material, {})[company] = v

    for e in entries:
        f, day, company = e["fields"], e["as_of"], e["company"]
        fx_local = _num(f.get("fx_purchase"))
        for material, qty_key, local_key in (("latex", "latex_wet", "price_latex_local"),
                                             ("cup", "coagulum", "price_cup_local")):
            local = _num(f.get(local_key))
            if local and fx_local:      # đơn vị nước ngoài: giá nội tệ × tỷ giá → VND
                prices.setdefault(day, {}).setdefault(material, {})[company] = local * fx_local
            q = _num(f.get(qty_key))
            if q is not None:
                qty.setdefault(day, {}).setdefault(material, {})[company] = q

    rows = []
    for day in days_between(date_from, date_to):
        row: dict[str, Any] = {"as_of": day}
        for material in ("latex", "cup"):
            q = qty.get(day, {}).get(material, {})
            row[material] = {
                **_stats(sorted(prices.get(day, {}).get(material, {}).values())),
                "qty": round(sum(q.values()), 3) if q else None,
                "qty_units": len(q),
            }
        rows.append(row)
    return {"date_from": date_from, "date_to": date_to, "rows": rows}
